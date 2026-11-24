"""Credentials: roles, revocation, expiry, rotation, and audit attribution."""

import json
import logging
import time

import httpx
import pytest
from pydantic import SecretStr
from sqlalchemy import update
from starlette.requests import Request

from agentforge.api import create_app
from agentforge.models import Credential
from agentforge.security import client_ip, key_hash
from agentforge.store import StoreError


def client_for(settings, store):
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app(settings, store)), base_url="http://test"
    )


def bearer(key):
    return {"Authorization": "Bearer " + key}


async def test_roles_are_enforced_per_endpoint(settings, store):
    admin = bearer(settings.api_key.get_secret_value())
    async with client_for(settings, store) as client:
        created = await client.post(
            "/v1/keys", json={"label": "viewer", "role": "read"}, headers=admin
        )
        assert created.status_code == 201
        reader = bearer(created.json()["key"])
        assert (await client.get("/v1/runs", headers=reader)).status_code == 200
        assert (await client.post("/v1/agents", json={}, headers=reader)).status_code == 403
        assert (await client.get("/v1/keys", headers=reader)).status_code == 403
        submit = await client.post(
            "/v1/keys", json={"label": "ci", "role": "submit"}, headers=admin
        )
        submitter = bearer(submit.json()["key"])
        assert (await client.post("/v1/agents", json={}, headers=submitter)).status_code == 201
        assert (
            await client.post("/v1/keys", json={"label": "x", "role": "admin"}, headers=submitter)
        ).status_code == 403


async def test_plaintext_key_is_shown_once_and_never_listed(settings, store):
    admin = bearer(settings.api_key.get_secret_value())
    async with client_for(settings, store) as client:
        created = (
            await client.post("/v1/keys", json={"label": "a", "role": "read"}, headers=admin)
        ).json()
        assert created["key"].startswith("afk_") and "key_hash" not in created
        listed = (await client.get("/v1/keys", headers=admin)).json()
        text = json.dumps(listed)
        assert created["key"] not in text and key_hash(created["key"]) not in text
        assert {row["label"] for row in listed} == {"bootstrap", "a"}


async def test_revoked_and_expired_keys_are_rejected(settings, store, owner):
    admin = bearer(settings.api_key.get_secret_value())
    async with client_for(settings, store) as client:
        created = (
            await client.post("/v1/keys", json={"label": "temp", "role": "read"}, headers=admin)
        ).json()
        key = bearer(created["key"])
        assert (await client.get("/v1/runs", headers=key)).status_code == 200
        revoked = await client.post(f"/v1/keys/{created['id']}/revoke", headers=admin)
        assert revoked.json()["revoked_at"] is not None
        assert (await client.get("/v1/runs", headers=key)).status_code == 401
    record, plaintext = await store.create_credential(owner, "short", "read", time.time() + 60)
    async with store.sessions.begin() as session:
        await session.execute(
            update(Credential)
            .where(Credential.id == record["id"])
            .values(expires_at=time.time() - 1)
        )
    async with client_for(settings, store) as client:
        assert (await client.get("/v1/runs", headers=bearer(plaintext))).status_code == 401


async def test_bootstrap_key_cannot_be_revoked_through_the_api(settings, store, owner):
    bootstrap = next(c for c in await store.list_credentials(owner) if c["bootstrap"])
    with pytest.raises(StoreError, match="Rotate the bootstrap key"):
        await store.revoke_credential(owner, bootstrap["id"])


async def test_bootstrap_rotation_keeps_ownership_and_revokes_old_key(settings, store, owner):
    from agentforge.domain import Agent

    agent = await store.create_agent(owner, Agent())
    new_key = "rotated-operator-key-" + "z" * 32
    assert await store.bootstrap_credential(new_key) == owner
    assert (await store.get_agent(owner, agent["id"]))["id"] == agent["id"]
    assert await store.principal(key_hash(settings.api_key.get_secret_value())) is None
    rotated = await store.principal(key_hash(new_key))
    assert rotated is not None and rotated.owner == owner and rotated.role == "admin"
    # Restarting with the same key is idempotent.
    assert await store.bootstrap_credential(new_key) == owner


async def test_audit_attribution_and_route_templated_logs(settings, store, caplog):
    admin = bearer(settings.api_key.get_secret_value())
    caplog.set_level(logging.INFO, logger="agentforge")
    async with client_for(settings, store) as client:
        agent = (await client.post("/v1/agents", json={}, headers=admin)).json()
        run = (
            await client.post(
                "/v1/runs",
                json={"agent_id": agent["id"]},
                headers={**admin, "Idempotency-Key": "audit"},
            )
        ).json()
        await client.post(f"/v1/runs/{run['id']}/cancel", headers=admin)
        events = (await client.get(f"/v1/runs/{run['id']}/events", headers=admin)).json()
    actor = (await store.principal(key_hash(settings.api_key.get_secret_value()))).credential_id
    assert events[0]["data"]["actor"] == actor
    assert events[-1]["kind"] == "run.cancelled" and events[-1]["data"]["actor"] == actor
    records = [
        json.loads(r.getMessage()) for r in caplog.records if "request.completed" in r.getMessage()
    ]
    cancel = next(r for r in records if r["route"] == "/v1/runs/{run_id}/cancel")
    assert cancel["actor"] == actor and cancel["method"] == "POST"
    assert all(run["id"] not in json.dumps(r) for r in records)
    assert all(settings.api_key.get_secret_value() not in json.dumps(r) for r in records)


def request_with(peer, forwarded=None):
    headers = [(b"x-forwarded-for", forwarded.encode())] if forwarded else []
    return Request({"type": "http", "client": (peer, 1234), "headers": headers})


def test_client_ip_trusts_only_configured_proxy_hops():
    # Caddy records the client; nginx appends Caddy's address; the API sees nginx.
    assert client_ip(request_with("10.0.0.3", "203.0.113.9, 10.0.0.2"), 2) == "203.0.113.9"
    # A client-supplied prefix cannot win: only the configured hop counts.
    assert client_ip(request_with("10.0.0.3", "1.1.1.1, 203.0.113.9, 10.0.0.2"), 2) == "203.0.113.9"
    assert client_ip(request_with("10.0.0.3", "203.0.113.9, 10.0.0.2"), 0) == "10.0.0.3"
    assert client_ip(request_with("10.0.0.3", "10.0.0.2"), 2) == "10.0.0.3"
    assert client_ip(request_with("10.0.0.3", "not-an-ip, 10.0.0.2"), 2) == "10.0.0.3"


async def test_short_or_missing_bootstrap_key_is_rejected_at_startup(settings, store):
    settings.api_key = SecretStr("short")
    with pytest.raises(ValueError, match="AGENTFORGE_API_KEY"):
        create_app(settings, store)
