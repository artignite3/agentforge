import httpx

from agentforge import Agent, AgentForge
from agentforge.sdk import api_key_from_environment


def test_sdk_idempotency_and_wait_use_real_contract():
    submitted = []
    statuses = iter(["RUNNING", "COMPLETED"])

    def handle(request):
        if request.url.path == "/v1/agents":
            return httpx.Response(201, json={"id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"})
        if request.method == "POST":
            submitted.append(request.headers["Idempotency-Key"])
            return httpx.Response(202, json={"id": "run", "status": "QUEUED"})
        return httpx.Response(
            200, json={"id": "run", "status": next(statuses), "output": "verified"}
        )

    with AgentForge("test-key") as client:
        client.http.close()
        client.http = httpx.Client(base_url="http://test", transport=httpx.MockTransport(handle))
        run = client.run(Agent(), "Repair the fixture", idempotency_key="stable-submission")
        result = client.wait(run["id"], timeout=1, poll_interval=0.001)
    assert submitted == ["stable-submission"]
    assert result["status"] == "COMPLETED"


def test_client_configuration_independent_of_server(monkeypatch):
    monkeypatch.setenv("AGENTFORGE_ENVIRONMENT", "production")
    monkeypatch.setenv("AGENTFORGE_API_KEY", "client-only-key-" + "x" * 40)
    monkeypatch.delenv("AGENTFORGE_DATABASE_URL", raising=False)
    monkeypatch.delenv("AGENTFORGE_REDIS_URL", raising=False)
    assert api_key_from_environment() == "client-only-key-" + "x" * 40
