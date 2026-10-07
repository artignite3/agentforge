import asyncio
import os
import time

import pytest
from sqlalchemy import update

from agentforge.domain import Action, Agent, Generation, RunCreate, ToolResult
from agentforge.models import Run
from agentforge.providers import ProviderError, Router
from agentforge.runtime import Runtime
from agentforge.sandbox import DockerExecutor


class StubTools:
    """Unit test double only; real Docker tests below cover code execution."""

    async def execute(self, request):
        failed = "(len(values) + 1)" in request.files.get(
            "stats.py", ""
        ) or "min(low" in request.files.get("stats.py", "")
        exit_code = 1 if request.action.operation == "run_tests" and failed else 0
        return ToolResult(
            exit_code=exit_code, duration_ms=1, stderr="FAILED" if exit_code else "OK"
        )


class DockerTools:
    async def execute(self, request):
        return await asyncio.to_thread(DockerExecutor("agentforge-tool:local").execute, request)


async def submit(store, owner, **options):
    agent = await store.create_agent(owner, Agent(**options))
    return await store.create_run(owner, RunCreate(agent_id=agent["id"]), "runtime-test", "request")


async def test_complete_runtime_and_atomic_trace(store, settings, owner):
    run = await submit(store, owner)
    runtime = Runtime(store, Router(settings), StubTools())
    await runtime.execute(*(await store.claim()))
    final = await store.get_run(owner, run["id"])
    trace = await store.trace(owner, run["id"])
    assert final["status"] == "COMPLETED"
    assert final["checkpoint_seq"] == 9
    assert trace["checkpoint"]["payload"]["tests_passed"] is True
    assert [s["kind"] for s in trace["steps"]] == ["model", "tool"] * 4 + ["model"]
    assert (await store.events(owner, run["id"]))[-1]["kind"] == "run.completed"


async def test_worker_dies_after_four_committed_steps(store, settings, owner):
    run = await submit(store, owner)
    runtime = Runtime(store, Router(settings), StubTools())
    original = store.finish_step

    async def crash_after_four(*args, **kwargs):
        await original(*args, **kwargs)
        current = await store.get_run(owner, run["id"])
        if current["checkpoint_seq"] == 4:
            raise asyncio.CancelledError()

    store.finish_step = crash_after_four
    with pytest.raises(asyncio.CancelledError):
        await runtime.execute(*(await store.claim()))
    store.finish_step = original
    async with store.sessions.begin() as session:
        await session.execute(
            update(Run).where(Run.id == run["id"]).values(lease_until=time.time() - 1)
        )
    await runtime.execute(*(await store.claim()))
    trace = await store.trace(owner, run["id"])
    assert trace["run"]["status"] == "COMPLETED"
    assert trace["run"]["recoveries"] == 1
    assert len(trace["steps"]) == 9  # No already-committed operations repeated.


async def test_model_cannot_finish_without_verification(store, settings, owner):
    class PrematurePlanner:
        async def generate(self, prompt, context):
            return Generation(
                action=Action(operation="finish", explanation="trust me"),
                input_tokens=0,
                output_tokens=0,
            )

    await submit(store, owner)
    router = Router(settings)
    router.providers["demo"] = PrematurePlanner()
    run_id, token = await store.claim()
    await Runtime(store, router, StubTools()).execute(run_id, token)
    result = await store.get_run(owner, run_id)
    assert result["status"] == "FAILED"
    assert result["error_type"] == "VerificationRequired"


async def test_timeout_and_retryable_provider_failure(store, settings, owner):
    class BrokenPlanner:
        async def generate(self, prompt, context):
            raise ProviderError("ProviderUnavailable")

    run = await submit(store, owner)
    router = Router(settings)
    router.providers["demo"] = BrokenPlanner()
    run_id, token = await store.claim()
    await Runtime(store, router, StubTools()).execute(run_id, token)
    assert (await store.get_run(owner, run_id))["status"] == "RETRYING"
    async with store.sessions.begin() as session:
        await session.execute(
            update(Run).where(Run.id == run_id).values(deadline=time.time() - 1, available_at=0)
        )
    assert await store.claim() is None
    assert (await store.get_run(owner, run["id"]))["status"] == "TIMED_OUT"


async def test_cancellation_during_tool_fences_result_and_cancels_wait(store, settings, owner):
    class SlowTools:
        def __init__(self):
            self.started = asyncio.Event()
            self.cancelled = asyncio.Event()

        async def execute(self, request):
            self.started.set()
            try:
                await asyncio.Event().wait()
            finally:
                self.cancelled.set()

    run = await submit(store, owner)
    tools = SlowTools()
    task = asyncio.create_task(
        Runtime(store, Router(settings), tools).execute(*(await store.claim()))
    )
    await asyncio.wait_for(tools.started.wait(), timeout=5)
    await store.cancel(owner, run["id"])
    await asyncio.wait_for(task, timeout=3)
    assert tools.cancelled.is_set()
    trace = await store.trace(owner, run["id"])
    assert trace["run"]["status"] == "CANCELLED"
    assert trace["run"]["checkpoint_seq"] == 1
    assert trace["steps"][-1]["status"] == "CANCELLED"


@pytest.mark.docker
@pytest.mark.skipif(os.getenv("RUN_DOCKER_TESTS") != "1", reason="Set RUN_DOCKER_TESTS=1")
async def test_real_full_runtime(store, settings, owner):
    run = await submit(store, owner)
    await Runtime(store, Router(settings), DockerTools()).execute(*(await store.claim()))
    trace = await store.trace(owner, run["id"])
    assert trace["run"]["status"] == "COMPLETED"
    tools = [s for s in trace["steps"] if s["kind"] == "tool"]
    assert tools[1]["detail"]["exit_code"] == 1
    assert "FAILED" in tools[1]["detail"]["stderr"]
    assert tools[-1]["detail"]["exit_code"] == 0
    assert "OK" in tools[-1]["detail"]["stderr"]
