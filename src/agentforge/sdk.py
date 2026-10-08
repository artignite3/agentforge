"""Small synchronous SDK; submission is async on the server, waiting is optional."""

import time
from typing import Any, Literal

import httpx
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from agentforge.domain import TERMINAL, Agent, RunCreate, Status
from agentforge.models import uid


class _ClientSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="AGENTFORGE_", env_file=".env", extra="ignore", hide_input_in_errors=True
    )
    api_key: SecretStr = SecretStr("")


def api_key_from_environment() -> str:
    """Load client credentials without requiring the server's database configuration."""
    key = _ClientSettings().api_key.get_secret_value()
    if len(key) < 32:
        raise ValueError("Set AGENTFORGE_API_KEY or generate .env before running the client")
    return key


class AgentForge:
    def __init__(self, api_key: str, base_url: str = "http://localhost:8000"):
        self.http = httpx.Client(
            base_url=base_url,
            headers={"Authorization": "Bearer " + api_key},
            timeout=10,
            follow_redirects=False,
            trust_env=False,
        )

    def close(self) -> None:
        self.http.close()

    def __enter__(self) -> "AgentForge":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def _request(
        self, method: str, path: str, body: dict[str, Any] | None = None, key: str | None = None
    ) -> dict[str, Any]:
        response = self.http.request(
            method, path, json=body, headers={"Idempotency-Key": key} if key else None
        )
        response.raise_for_status()
        result: dict[str, Any] = response.json()
        return result

    def register(self, agent: Agent) -> dict[str, Any]:
        return self._request("POST", "/v1/agents", agent.model_dump())

    def run(
        self,
        agent: Agent,
        task: str,
        fixture: Literal["mean", "clamp"] = "mean",
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        registered = self.register(agent)
        spec = RunCreate(agent_id=registered["id"], task=task, fixture=fixture)
        return self._request("POST", "/v1/runs", spec.model_dump(), idempotency_key or uid())

    def get(self, run_id: str) -> dict[str, Any]:
        return self._request("GET", f"/v1/runs/{run_id}")

    def wait(self, run_id: str, timeout: float = 180, poll_interval: float = 1) -> dict[str, Any]:
        if timeout <= 0 or poll_interval <= 0:
            raise ValueError("Timeout and poll interval must be positive")
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            run = self.get(run_id)
            if Status(run["status"]) in TERMINAL:
                return run
            time.sleep(min(poll_interval, max(0, deadline - time.monotonic())))
        raise TimeoutError(
            "SDK wait deadline reached; the server run is still independently managed"
        )

    def cancel(self, run_id: str) -> dict[str, Any]:
        return self._request("POST", f"/v1/runs/{run_id}/cancel", {})

    def trace(self, run_id: str) -> dict[str, Any]:
        return self._request("GET", f"/v1/runs/{run_id}/trace")

    def retry(self, run_id: str, idempotency_key: str | None = None) -> dict[str, Any]:
        return self._request("POST", f"/v1/runs/{run_id}/retry", {}, idempotency_key or uid())
