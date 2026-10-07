import httpx
import pytest
from pydantic import ValidationError

from agentforge.api import create_app
from agentforge.config import Settings


async def test_chunked_oversized_request_is_rejected(settings, store):
    async def chunks():
        for _ in range(12):
            yield b"x" * 8192

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app(settings, store)), base_url="http://test"
    ) as client:
        response = await client.post("/v1/agents", content=chunks())
        assert response.status_code == 413


def test_production_config_and_error_redaction():
    kwargs = {"_env_file": None, "api_key": "a" * 40, "sandbox_key": "b" * 40}
    with pytest.raises(ValidationError):
        Settings(**kwargs, cors_origins=["*"])
    with pytest.raises(ValidationError):
        Settings(**kwargs, environment="production")
    sensitive_url = "postgresql+asyncpg://operator:private-password@localhost/db"
    configured = Settings(**kwargs, database_url=sensitive_url)
    assert "private-password" not in repr(configured)
    with pytest.raises(ValidationError) as failure:
        Settings(**kwargs, environment="production", database_url=sensitive_url)
    assert "private-password" not in str(failure.value)


async def test_failed_rate_limiter_does_not_admit_requests(settings, store):
    settings.redis_url = "redis://127.0.0.1:1/0"
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app(settings, store)), base_url="http://test"
    ) as client:
        response = await client.get(
            "/v1/runs", headers={"Authorization": "Bearer " + settings.api_key.get_secret_value()}
        )
        assert response.status_code == 503
        assert response.json()["detail"] == "Rate limiter unavailable"
