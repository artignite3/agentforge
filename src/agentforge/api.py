import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated, Any
from uuid import UUID

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from pydantic import Field

from agentforge.config import Settings, get_settings, require_secret
from agentforge.domain import TERMINAL, Agent, RunCreate, Status, StrictModel
from agentforge.models import uid
from agentforge.security import BodyLimit, Limiter, Principal, PrincipalCache, authentication
from agentforge.store import Store, StoreError
from agentforge.telemetry import LATENCY, REQUESTS, log, publish_snapshot

IdempotencyKey = Annotated[str, Header(min_length=1, max_length=128, pattern=r"^[a-zA-Z0-9._:-]+$")]
# A worker heartbeat older than this means no worker is currently serving the queue.
WORKER_FRESH_SECONDS = 30
PROVIDER_NAMES = ("demo", "openai", "gemini")


class KeyCreate(StrictModel):
    label: str = Field(min_length=1, max_length=80, pattern=r"^[a-zA-Z0-9 _.@-]+$")
    role: str = Field(pattern=r"^(read|submit|admin)$")
    expires_in_days: float | None = Field(default=None, gt=0, le=3650, allow_inf_nan=False)


def create_app(settings: Settings | None = None, store: Store | None = None) -> FastAPI:
    config = settings or get_settings()
    bootstrap_key = require_secret(config.api_key, "AGENTFORGE_API_KEY")
    if config.environment == "production" and not config.redis_url:
        raise ValueError("Production requires Redis for distributed rate limiting")
    database = store or Store(config)
    limiter = Limiter(config)
    cache = PrincipalCache()
    require = authentication(config, limiter, database, cache)
    Reader = Annotated[Principal, Depends(require("read"))]
    Submitter = Annotated[Principal, Depends(require("submit"))]
    Admin = Annotated[Principal, Depends(require("admin"))]

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        logging.basicConfig(level=logging.INFO, format="%(message)s")
        # HTTP client libraries otherwise may log request URLs and query parameters.
        logging.getLogger("httpx").setLevel(logging.WARNING)
        await database.bootstrap_credential(bootstrap_key)
        yield
        if limiter.redis:
            await limiter.redis.aclose()
        await database.engine.dispose()

    production = config.environment == "production"
    app = FastAPI(
        title="AgentForge",
        version="0.2.0",
        lifespan=lifespan,
        description="Durable agent jobs with fenced leases and isolated repository tools.",
        # Interactive docs load third-party CDN scripts that the production CSP blocks.
        docs_url=None if production else "/docs",
        redoc_url=None if production else "/redoc",
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
        request.state.actor = None
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
        # Route templates (/v1/runs/{run_id}) keep logs and labels low-cardinality and free
        # of identifiers; unmatched paths are never recorded verbatim.
        route = getattr(request.scope.get("route"), "path", "unmatched")
        REQUESTS.labels(method, str(response.status_code)).inc()
        LATENCY.observe(elapsed)
        log(
            "api",
            "request.completed",
            request_id=request.state.request_id,
            method=method,
            route=route,
            actor=request.state.actor,
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

    async def provider_catalog() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Providers are configured on workers; the API holds no provider credentials."""
        workers = await database.workers(WORKER_FRESH_SECONDS)
        if workers:
            return workers[0]["providers"], workers
        catalog: list[dict[str, Any]] = [
            {
                "provider": name,
                "model": "scripted-repair-v1" if name == "demo" else None,
                "configured": name == "demo",
                "health": "no_worker",
            }
            for name in PROVIDER_NAMES
        ]
        return catalog, workers

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

    @app.get("/v1/system")
    async def system(principal: Reader) -> dict[str, Any]:
        providers, workers = await provider_catalog()
        return {
            "environment": config.environment,
            "queue": "postgresql"
            if config.database_url.startswith("postgresql")
            else "sqlite-single-worker",
            "providers": providers,
            "sandbox": "private Docker gateway",
            "sandbox_ready": any(w["sandbox_ready"] for w in workers),
            "workers_alive": len(workers),
            "semantics": "at-least-once execution; fenced checkpoint commits",
            "principal": {"label": principal.label, "role": principal.role},
        }

    @app.get("/metrics", include_in_schema=False)
    async def metrics(principal: Reader) -> Response:
        publish_snapshot(await database.metrics_snapshot())
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    @app.get("/v1/providers")
    async def providers(principal: Reader) -> list[dict[str, Any]]:
        return (await provider_catalog())[0]

    @app.post("/v1/agents", status_code=201)
    async def create_agent(spec: Agent, principal: Submitter) -> dict[str, Any]:
        return await database.create_agent(principal.owner, spec)

    @app.get("/v1/agents")
    async def agents(principal: Reader) -> list[dict[str, Any]]:
        return await database.list_agents(principal.owner)

    @app.get("/v1/agents/{agent_id}")
    async def agent(agent_id: UUID, principal: Reader) -> dict[str, Any]:
        return await database.get_agent(principal.owner, str(agent_id))

    @app.post("/v1/runs", status_code=202)
    async def create_run(
        spec: RunCreate,
        request: Request,
        idempotency_key: IdempotencyKey,
        principal: Submitter,
    ) -> dict[str, Any]:
        return await database.create_run(
            principal.owner,
            spec,
            idempotency_key,
            request.state.request_id,
            actor=principal.credential_id,
        )

    @app.get("/v1/runs")
    async def runs(
        principal: Reader, before: float | None = Query(default=None, ge=0)
    ) -> list[dict[str, Any]]:
        return await database.list_runs(principal.owner, before)

    @app.get("/v1/runs/{run_id}")
    async def run(run_id: UUID, principal: Reader) -> dict[str, Any]:
        return await database.get_run(principal.owner, str(run_id))

    @app.post("/v1/runs/{run_id}/cancel")
    async def cancel(run_id: UUID, principal: Submitter) -> dict[str, Any]:
        return await database.cancel(principal.owner, str(run_id), actor=principal.credential_id)

    @app.post("/v1/runs/{run_id}/retry", status_code=202)
    async def retry(
        run_id: UUID,
        request: Request,
        idempotency_key: IdempotencyKey,
        principal: Submitter,
    ) -> dict[str, Any]:
        old = await database.get_run(principal.owner, str(run_id))
        if Status(old["status"]) not in TERMINAL - {Status.COMPLETED}:
            raise HTTPException(409, "Only unsuccessful terminal runs can be retried")
        spec = RunCreate(agent_id=old["agent_id"], task=old["task"], fixture=old["fixture"])
        return await database.create_run(
            principal.owner,
            spec,
            idempotency_key,
            request.state.request_id,
            str(run_id),
            actor=principal.credential_id,
        )

    @app.get("/v1/runs/{run_id}/events")
    async def events(
        run_id: UUID, principal: Reader, after: int = Query(default=0, ge=0)
    ) -> list[dict[str, Any]]:
        return await database.events(principal.owner, str(run_id), after)

    @app.get("/v1/runs/{run_id}/trace")
    async def trace(run_id: UUID, principal: Reader) -> dict[str, Any]:
        return await database.trace(principal.owner, str(run_id))

    @app.get("/v1/keys")
    async def keys(principal: Admin) -> list[dict[str, Any]]:
        return await database.list_credentials(principal.owner)

    @app.post("/v1/keys", status_code=201)
    async def create_key(spec: KeyCreate, principal: Admin) -> dict[str, Any]:
        expires = time.time() + spec.expires_in_days * 86400 if spec.expires_in_days else None
        record, key = await database.create_credential(
            principal.owner, spec.label, spec.role, expires, created_by=principal.credential_id
        )
        log("api", "key.created", actor=principal.credential_id, credential_id=record["id"])
        # The plaintext key is returned exactly once and never stored or logged.
        return {**record, "key": key}

    @app.post("/v1/keys/{key_id}/revoke")
    async def revoke_key(key_id: UUID, principal: Admin) -> dict[str, Any]:
        record = await database.revoke_credential(
            principal.owner, str(key_id), revoked_by=principal.credential_id
        )
        cache.clear()  # This process stops accepting the key immediately; others within 5 s.
        log("api", "key.revoked", actor=principal.credential_id, credential_id=record["id"])
        return record

    return app
