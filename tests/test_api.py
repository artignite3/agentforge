import httpx

from agentforge.api import create_app


async def test_auth_validation_idempotency_cancel(settings, store):
    app = create_app(settings, store)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        assert (await client.get("/v1/runs")).status_code == 401
        client.headers["Authorization"] = "Bearer " + settings.api_key.get_secret_value()
        agent = (await client.post("/v1/agents", json={})).json()
        assert "id" in agent
        headers = {"Idempotency-Key": "one"}
        request = {"agent_id": agent["id"]}
        first = await client.post("/v1/runs", json=request, headers=headers)
        assert first.status_code == 202, first.text
        duplicate = await client.post("/v1/runs", json=request, headers=headers)
        assert duplicate.json()["id"] == first.json()["id"]
        mismatch = await client.post(
            "/v1/runs", json={**request, "task": "different"}, headers=headers
        )
        assert mismatch.status_code == 409
        run_id = first.json()["id"]
        cancelled = await client.post(f"/v1/runs/{run_id}/cancel")
        assert cancelled.json()["status"] == "CANCELLED"
        assert (await client.get(f"/v1/runs/{run_id}/events")).json()[-1]["kind"] == "run.cancelled"
        assert (await client.post("/v1/agents", json={"timeout": -1})).status_code == 422
        assert (await client.post("/v1/agents", content=b"x" * 70000)).status_code == 413
        assert (await client.get("/ready")).status_code == 200


async def test_rate_limit_and_cors(settings, store):
    settings.rate_limit = 1
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app(settings, store)), base_url="http://test"
    ) as client:
        client.headers["Authorization"] = "Bearer " + settings.api_key.get_secret_value()
        first = await client.get("/v1/runs", headers={"Origin": "https://evil.invalid"})
        assert "access-control-allow-origin" not in first.headers
        assert (await client.get("/v1/runs")).status_code == 429
