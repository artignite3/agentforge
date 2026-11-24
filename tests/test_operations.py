"""Worker heartbeats, system status, metrics, retention, healthcheck, and migrations."""

import os
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

import httpx
from sqlalchemy import select, update

from agentforge.api import create_app
from agentforge.domain import Agent, RunCreate
from agentforge.models import Checkpoint, Run
from agentforge.worker import check

ROOT = Path(__file__).resolve().parents[1]


def admin_client(settings, store):
    client = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app(settings, store)), base_url="http://test"
    )
    client.headers["Authorization"] = "Bearer " + settings.api_key.get_secret_value()
    return client


async def test_system_status_comes_from_fresh_worker_heartbeats(settings, store):
    async with admin_client(settings, store) as client:
        idle = (await client.get("/v1/system")).json()
        assert idle["workers_alive"] == 0 and idle["sandbox_ready"] is False
        assert {p["health"] for p in idle["providers"]} == {"no_worker"}
        providers = [
            {"provider": "gemini", "model": "m", "configured": True, "health": "not_probed"}
        ]
        await store.record_worker("w1", time.time(), None, True, providers)
        live = (await client.get("/v1/system")).json()
        assert live["workers_alive"] == 1 and live["sandbox_ready"] is True
        assert live["principal"] == {"label": "bootstrap", "role": "admin"}
        assert (await client.get("/v1/providers")).json() == providers


async def test_metrics_report_queue_worker_and_spend(settings, store, owner):
    agent = await store.create_agent(owner, Agent())
    await store.create_run(owner, RunCreate(agent_id=agent["id"]), "m1", "r")
    await store.record_worker("w1", time.time(), None, True, [])
    async with admin_client(settings, store) as client:
        body = (await client.get("/metrics")).text
    assert 'agentforge_runs{status="QUEUED"} 1.0' in body
    assert "agentforge_oldest_queued_age_seconds" in body
    assert "agentforge_worker_heartbeat_age_seconds" in body
    assert "agentforge_spend_today_microusd 0.0" in body


async def test_prune_keeps_latest_checkpoint_and_active_runs(store, owner):
    agent = await store.create_agent(owner, Agent())
    done = await store.create_run(owner, RunCreate(agent_id=agent["id"]), "old", "r")
    active = await store.create_run(owner, RunCreate(agent_id=agent["id"]), "active", "r")
    run_id, token = await store.claim()
    _, _, payload = await store.context(run_id, token)
    for _ in range(2):
        step = await store.start_step(run_id, token, "model")
        await store.finish_step(run_id, token, step["id"], payload, {}, 1)
    await store.cancel(owner, done["id"])
    async with store.sessions.begin() as session:
        await session.execute(
            update(Run).where(Run.id == done["id"]).values(updated_at=time.time() - 40 * 86400)
        )
    assert await store.prune(30, dry_run=True) == {"checkpoints": 2, "runs": 0}
    assert await store.prune(30) == {"checkpoints": 2, "runs": 0}
    async with store.sessions() as session:
        kept = list(
            await session.scalars(
                select(Checkpoint.sequence).where(Checkpoint.run_id == done["id"])
            )
        )
    assert kept == [2]
    trace = await store.trace(owner, done["id"])
    assert trace["checkpoint"]["sequence"] == 2  # The trace's final source survives.
    assert await store.prune(30, run_days=30) == {"checkpoints": 0, "runs": 1}
    assert (await store.get_run(owner, active["id"]))["status"] == "QUEUED"
    assert [r["id"] for r in await store.list_runs(owner)] == [active["id"]]


def test_worker_healthcheck_reflects_heartbeat_age(tmp_path):
    heartbeat = tmp_path / "beat"
    assert check(heartbeat) == 1
    heartbeat.touch()
    assert check(heartbeat) == 0
    old = time.time() - 120
    os.utime(heartbeat, (old, old))
    assert check(heartbeat) == 1


def test_migration_backfills_existing_owner_as_bootstrap_admin(tmp_path):
    database = tmp_path / "migrate.db"
    env = {
        **os.environ,
        "AGENTFORGE_DATABASE_URL": f"sqlite+aiosqlite:///{database.as_posix()}",
        "AGENTFORGE_ENVIRONMENT": "test",
    }

    def alembic(*args):
        subprocess.run(
            [sys.executable, "-m", "alembic", *args],
            cwd=ROOT,
            env=env,
            check=True,
            capture_output=True,
        )

    alembic("upgrade", "1ef9fd4d71fb")
    with sqlite3.connect(database) as connection:
        connection.execute(
            "INSERT INTO api_keys (id, label, created_at) VALUES (?, 'operator', 0)", ("a" * 64,)
        )
    alembic("upgrade", "head")
    with sqlite3.connect(database) as connection:
        rows = connection.execute(
            "SELECT owner_id, key_hash, role, bootstrap, revoked_at FROM credentials"
        ).fetchall()
    assert rows == [("a" * 64, "a" * 64, "admin", 1, None)]
    alembic("downgrade", "1ef9fd4d71fb")
