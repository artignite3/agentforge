import time

import pytest
from sqlalchemy import update

from agentforge.domain import Agent, RunCreate, Status
from agentforge.models import Run
from agentforge.store import LeaseLost, StoreError


async def new_run(store, owner, **options):
    agent = await store.create_agent(owner, Agent(**options))
    return await store.create_run(owner, RunCreate(agent_id=agent["id"]), "test", "request")


async def test_recovery_fences_old_worker_and_retains_budget(store, owner):
    run = await new_run(store, owner)
    run_id, token = await store.claim()
    step = await store.start_step(run_id, token, "model", cost=100, tokens=200)
    async with store.sessions.begin() as session:
        await session.execute(
            update(Run).where(Run.id == run_id).values(lease_until=time.time() - 1)
        )
    recovered_id, new_token = await store.claim()
    assert recovered_id == run_id and token != new_token
    with pytest.raises(LeaseLost):
        await store.finish_run(run_id, token, Status.COMPLETED)
    current, _, checkpoint = await store.context(run_id, new_token)
    assert current["spent_microusd"] == 100
    assert current["checkpoint_seq"] == 0
    trace = await store.trace(owner, run_id)
    assert trace["steps"][0]["status"] == "UNKNOWN"
    assert trace["steps"][0]["id"] == step["id"]
    assert run["id"] == run_id


async def test_budget_and_ownership(store, owner):
    run = await new_run(store, owner, budget_usd=0)
    run_id, token = await store.claim()
    with pytest.raises(StoreError, match="BudgetExhausted"):
        await store.start_step(run_id, token, "model", cost=1)
    with pytest.raises(StoreError, match="not found"):
        await store.get_run("someone-else", run["id"])
    await store.cancel(owner, run_id)
    with pytest.raises(LeaseLost):
        await store.heartbeat(run_id, token)


async def test_checkpoint_is_atomic_and_resume_starts_after_saved_step(store, owner):
    await new_run(store, owner)
    run_id, token = await store.claim()
    _, _, cp = await store.context(run_id, token)
    step = await store.start_step(run_id, token, "model")
    cp["pending_action"] = {"operation": "run_tests", "path": "", "content": "", "explanation": ""}
    await store.finish_step(run_id, token, step["id"], cp, {}, 1)
    async with store.sessions.begin() as session:
        await session.execute(
            update(Run).where(Run.id == run_id).values(lease_until=time.time() - 1)
        )
    _, replacement = await store.claim()
    run, _, recovered = await store.context(run_id, replacement)
    assert run["checkpoint_seq"] == 1
    assert recovered["pending_action"]["operation"] == "run_tests"


async def test_retries_are_bounded(store, owner):
    await new_run(store, owner)
    for attempt in range(1, 4):
        run_id, token = await store.claim()
        step = await store.start_step(run_id, token, "model")
        assert step["attempt"] == attempt
        await store.fail_step(run_id, token, step["id"], "ProviderTransportError", 0, True)
    assert (await store.get_run(owner, run_id))["status"] == "FAILED"
    assert await store.claim() is None
