import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated, Any
from uuid import UUID

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from agentforge.config import Settings, get_settings
from agentforge.domain import TERMINAL, Agent, RunCreate, Status
from agentforge.models import uid
from agentforge.providers import Router
from agentforge.security import BodyLimit, Limiter, authentication, owner_id
from agentforge.store import Store, StoreError
from agentforge.telemetry import LATENCY, REQUESTS, log


def create_app(settings: Settings | None = None, store: Store | None = None) -> FastAPI:
    config = settings or get_settings()
    database = store or Store(config)
    limiter = Limiter(config)
    authenticate = authentication(config, limiter)
    router = Router(config)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        logging.basicConfig(level=logging.INFO, format="%(message)s")
        # HTTP client libraries otherwise may log request URLs and query parameters.
        logging.getLogger("httpx").setLevel(logging.WARNING)
        await database.register_key(owner_id(config.api_key.get_secret_value()))
        yield
        if limiter.redis:
            await limiter.redis.aclose()
        await database.engine.dispose()

    app = FastAPI(
        title="AgentForge",
        version="0.1.0",
        lifespan=lifespan,
        description="Durable agent jobs with fenced leases and isolated repository tools.",
    )
    app.state.store = database
    app.add_middleware(BodyLimit, limit=config.request_limit)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type", "Idempotency-Key"],
        expose_headers=["X-Request-ID"],
    )

    @app.middleware("http")
    async def correlated(request: Request, call_next: Any) -> Response:
        started = time.monotonic()
        request.state.request_id = uid()
        try:
            response = await call_next(request)
        except Exception as exc:
            log(
                "api",
                "request.failed",
                request_id=request.state.request_id,
                error_type=type(exc).__name__,
            )
            response = JSONResponse(
                {"detail": "Internal service error", "request_id": request.state.request_id},
                status_code=500,
            )
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "no-store"
        elapsed = time.monotonic() - started
        method = (
            request.method
            if request.method in {"GET", "POST", "OPTIONS", "HEAD", "PUT", "PATCH", "DELETE"}
            else "OTHER"
        )
        REQUESTS.labels(method, str(response.status_code)).inc()
        LATENCY.observe(elapsed)
        log(
            "api",
            "request.completed",
            request_id=request.state.request_id,
            duration_ms=round(elapsed * 1000),
            status=response.status_code,
        )
        return response

    @app.exception_handler(StoreError)
    async def store_error(request: Request, exc: StoreError) -> JSONResponse:
        return JSONResponse({"detail": str(exc)}, status_code=exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request: Request, exc: RequestValidationError) -> JSONResponse:
        # Pydantic's default error includes raw input; keep values out of error responses.
        return JSONResponse(
            {
                "detail": [
                    {"loc": list(error["loc"]), "type": error["type"], "msg": error["msg"]}
                    for error in exc.errors()
                ]
            },
            status_code=422,
        )

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "alive"}

    @app.get("/ready")
    async def ready(response: Response) -> dict[str, Any]:
        try:
            await database.ready()
            if limiter.redis:
                await limiter.redis.ping()
            return {
                "status": "ready",
                "database": "connected",
                "rate_limiter": "redis" if limiter.redis else "local-development",
            }
        except Exception:
            response.status_code = 503
            return {"status": "unavailable"}

    @app.get("/v1/system", dependencies=[Depends(authenticate)])
    async def system() -> dict[str, Any]:
        sandbox_ready = False
        try:
            async with httpx.AsyncClient(timeout=4, trust_env=False) as client:
                sandbox_ready = (
                    await client.get(config.sandbox_url + "/health")
                ).status_code == 200
        except httpx.HTTPError:
            pass
        return {
            "environment": config.environment,
            "queue": "postgresql"
            if config.database_url.startswith("postgresql")
            else "sqlite-single-worker",
            "providers": router.catalog(),
            "sandbox": "private Docker gateway",
            "sandbox_ready": sandbox_ready,
            "semantics": "at-least-once execution; fenced checkpoint commits",
        }

    @app.get("/metrics", dependencies=[Depends(authenticate)], include_in_schema=False)
    async def metrics() -> Response:
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    @app.get("/v1/providers", dependencies=[Depends(authenticate)])
    async def providers() -> list[dict[str, Any]]:
        return router.catalog()

    @app.post("/v1/agents", status_code=201)
    async def create_agent(spec: Agent, owner: str = Depends(authenticate)) -> dict[str, Any]:
        return await database.create_agent(owner, spec)

    @app.get("/v1/agents")
    async def agents(owner: str = Depends(authenticate)) -> list[dict[str, Any]]:
        return await database.list_agents(owner)

    @app.get("/v1/agents/{agent_id}")
    async def agent(agent_id: UUID, owner: str = Depends(authenticate)) -> dict[str, Any]:
        return await database.get_agent(owner, str(agent_id))

    @app.post("/v1/runs", status_code=202)
    async def create_run(
        spec: RunCreate,
        request: Request,
        idempotency_key: Annotated[
            str, Header(min_length=1, max_length=128, pattern=r"^[a-zA-Z0-9._:-]+$")
        ],
        owner: str = Depends(authenticate),
    ) -> dict[str, Any]:
        return await database.create_run(owner, spec, idempotency_key, request.state.request_id)

    @app.get("/v1/runs")
    async def runs(
        before: float | None = Query(default=None, ge=0), owner: str = Depends(authenticate)
    ) -> list[dict[str, Any]]:
        return await database.list_runs(owner, before)

    @app.get("/v1/runs/{run_id}")
    async def run(run_id: UUID, owner: str = Depends(authenticate)) -> dict[str, Any]:
        return await database.get_run(owner, str(run_id))

    @app.post("/v1/runs/{run_id}/cancel")
    async def cancel(run_id: UUID, owner: str = Depends(authenticate)) -> dict[str, Any]:
        return await database.cancel(owner, str(run_id))

    @app.post("/v1/runs/{run_id}/retry", status_code=202)
    async def retry(
        run_id: UUID,
        request: Request,
        idempotency_key: Annotated[
            str, Header(min_length=1, max_length=128, pattern=r"^[a-zA-Z0-9._:-]+$")
        ],
        owner: str = Depends(authenticate),
    ) -> dict[str, Any]:
        old = await database.get_run(owner, str(run_id))
        if Status(old["status"]) not in TERMINAL - {Status.COMPLETED}:
            raise HTTPException(409, "Only unsuccessful terminal runs can be retried")
        spec = RunCreate(agent_id=old["agent_id"], task=old["task"], fixture=old["fixture"])
        return await database.create_run(
            owner, spec, idempotency_key, request.state.request_id, str(run_id)
        )

    @app.get("/v1/runs/{run_id}/events")
    async def events(
        run_id: UUID, after: int = Query(default=0, ge=0), owner: str = Depends(authenticate)
    ) -> list[dict[str, Any]]:
        return await database.events(owner, str(run_id), after)

    @app.get("/v1/runs/{run_id}/trace")
    async def trace(run_id: UUID, owner: str = Depends(authenticate)) -> dict[str, Any]:
        return await database.trace(owner, str(run_id))

    return app
