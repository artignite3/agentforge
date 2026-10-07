"""Private trusted Docker gateway. Never expose this service or socket publicly."""

import asyncio
import base64
import contextlib
import json
import secrets
import threading
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import docker
from docker.errors import DockerException
from docker.types import LogConfig
from fastapi import FastAPI, HTTPException, Request
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from agentforge.domain import ToolRequest, ToolResult
from agentforge.security import BodyLimit


class SandboxSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AGENTFORGE_", env_file=".env", extra="ignore")
    sandbox_key: SecretStr = Field(default=SecretStr(""), min_length=32)
    tool_image: str = "agentforge-tool:local"


def container_options(request: ToolRequest, image: str) -> dict[str, Any]:
    """All resource/privilege controls are operator-owned; inputs cannot override them."""
    payload = base64.b64encode(request.model_dump_json().encode()).decode()
    return {
        "image": image,
        "command": ["python", "-I", "/runner.py", payload],
        "name": "af-tool-" + request.operation_id,
        "detach": True,
        "user": "10001:10001",
        "read_only": True,
        "network_disabled": True,
        "cap_drop": ["ALL"],
        "security_opt": ["no-new-privileges:true"],
        "mem_limit": "128m",
        "memswap_limit": "128m",
        "nano_cpus": 500_000_000,
        "pids_limit": 32,
        "tmpfs": {
            "/workspace": "rw,noexec,nosuid,nodev,size=2m,uid=10001,gid=10001,mode=700",
            "/tmp": "rw,noexec,nosuid,nodev,size=8m,mode=1777",  # nosec B108
        },
        "working_dir": "/workspace",
        "environment": {"PYTHONDONTWRITEBYTECODE": "1", "PYTHONUNBUFFERED": "1"},
        "labels": {"agentforge.sandbox": "true", "agentforge.expires": str(time.time() + 30)},
        "log_config": LogConfig(type="json-file", config={"max-size": "64k", "max-file": "1"}),
    }


class DockerExecutor:
    def __init__(self, image: str):
        self.image = image
        self.slots = threading.BoundedSemaphore(2)

    def execute(self, request: ToolRequest) -> ToolResult:
        if not self.slots.acquire(blocking=False):
            raise HTTPException(429, "Sandbox capacity reached")
        client = None
        container = None
        started = time.monotonic()
        try:
            client = docker.from_env(timeout=3)
            container = client.containers.run(**container_options(request, self.image))
            deadline = started + 12
            while time.monotonic() < deadline:
                container.reload()
                output = container.logs(stdout=True, stderr=True)
                if len(output) > 48000:
                    return ToolResult(
                        exit_code=137,
                        duration_ms=int((time.monotonic() - started) * 1000),
                        timeout_reason="OutputLimit",
                    )
                if container.status in {"exited", "dead"}:
                    if container.attrs["State"]["ExitCode"] != 0:
                        raise HTTPException(502, "Tool container failed")
                    try:
                        return ToolResult.model_validate(json.loads(output))
                    except ValueError as exc:
                        raise HTTPException(502, "Invalid tool result") from exc
                time.sleep(0.1)
            return ToolResult(
                exit_code=124,
                duration_ms=int((time.monotonic() - started) * 1000),
                timeout_reason="ContainerDeadline",
            )
        except DockerException as exc:
            raise HTTPException(503, "Docker unavailable or tool image missing") from exc
        finally:
            if container is not None:
                with contextlib.suppress(DockerException):
                    container.remove(force=True)
            if client is not None:
                client.close()
            self.slots.release()

    def reap(self) -> None:
        """Recover orphaned containers after gateway crashes; only our labelled resources."""
        with contextlib.suppress(DockerException):
            client = docker.from_env(timeout=3)
            try:
                for container in client.containers.list(
                    all=True, filters={"label": "agentforge.sandbox=true"}
                ):
                    expires = float(container.labels.get("agentforge.expires", "inf"))
                    if (container.name or "").startswith("af-tool-") and expires < time.time():
                        container.remove(force=True)
            finally:
                client.close()


def create_app() -> FastAPI:
    config = SandboxSettings()
    executor = DockerExecutor(config.tool_image)

    async def reaper() -> None:
        while True:
            await asyncio.to_thread(executor.reap)
            await asyncio.sleep(10)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        task = asyncio.create_task(reaper())
        yield
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

    app = FastAPI(
        title="AgentForge private sandbox", lifespan=lifespan, docs_url=None, openapi_url=None
    )
    app.add_middleware(BodyLimit, limit=65536)

    @app.get("/health")
    def health() -> dict[str, str]:
        try:
            client = docker.from_env(timeout=3)
            try:
                client.ping()
                client.images.get(config.tool_image)
            finally:
                client.close()
        except DockerException as exc:
            raise HTTPException(503, "Sandbox not ready") from exc
        return {"status": "ready"}

    @app.post("/execute")
    def execute(payload: ToolRequest, request: Request) -> ToolResult:
        supplied = request.headers.get("Authorization", "")
        if not secrets.compare_digest(
            supplied.encode(), ("Bearer " + config.sandbox_key.get_secret_value()).encode()
        ):
            raise HTTPException(401, "Invalid gateway key")
        return executor.execute(payload)

    return app
