"""Small resumable loop: persist intent, invoke one operation, atomically checkpoint."""

import asyncio
import contextlib
import copy
import time
from collections.abc import Awaitable
from typing import Protocol, TypeVar

import httpx

from agentforge.domain import Action, Status, ToolRequest, ToolResult, reserve_cost, retry_delay
from agentforge.providers import ProviderError, Router, prompt_for
from agentforge.store import LeaseLost, Store, StoreError
from agentforge.telemetry import log

T = TypeVar("T")


class ToolExecutor(Protocol):
    async def execute(self, request: ToolRequest) -> ToolResult: ...


class RemoteTools:
    def __init__(self, url: str, key: str):
        self.url, self.key = url, key

    async def execute(self, request: ToolRequest) -> ToolResult:
        try:
            async with httpx.AsyncClient(timeout=18, trust_env=False) as client:
                response = await client.post(
                    self.url + "/execute",
                    headers={"Authorization": "Bearer " + self.key},
                    json=request.model_dump(),
                )
                if response.status_code != 200:
                    raise ProviderError(
                        "SandboxUnavailable",
                        response.status_code >= 500 or response.status_code == 429,
                    )
                return ToolResult.model_validate(response.json())
        except httpx.HTTPError as exc:
            raise ProviderError("SandboxTransportError") from exc


class Runtime:
    def __init__(self, store: Store, router: Router, tools: ToolExecutor):
        self.store, self.router, self.tools = store, router, tools

    async def guarded(self, run_id: str, token: str, awaitable: Awaitable[T]) -> T:
        """Renew/check the lease while an external operation is in flight."""
        task = asyncio.ensure_future(awaitable)
        try:
            while True:
                done, _ = await asyncio.wait({task}, timeout=1)
                await self.store.heartbeat(run_id, token)
                if done:
                    return task.result()
        finally:
            if not task.done():
                task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task

    async def execute(self, run_id: str, token: str) -> None:
        try:
            await self._execute(run_id, token)
        except LeaseLost:
            log("worker", "lease.lost", run_id=run_id)
        except StoreError as exc:
            status = Status.TIMED_OUT if str(exc) == "DeadlineExceeded" else Status.FAILED
            with contextlib.suppress(LeaseLost):
                await self.store.finish_run(run_id, token, status, error=str(exc))

    async def _execute(self, run_id: str, token: str) -> None:
        while True:
            run, agent, snapshot = await self.store.context(run_id, token)
            checkpoint = copy.deepcopy(snapshot)
            if checkpoint["pending_action"] is None:
                prompt = prompt_for(run["task"], agent, checkpoint)
                failures = await self.store.prior_failures(run_id, run["checkpoint_seq"])
                try:
                    route = self.router.select(
                        agent,
                        prompt,
                        round(agent.budget_usd * 1_000_000) - run["spent_microusd"],
                        failures,
                    )
                except ProviderError as exc:
                    await self.store.finish_run(run_id, token, Status.FAILED, error=exc.kind)
                    return
                cost, tokens = route.reserve(prompt)
                step = await self.store.start_step(
                    run_id,
                    token,
                    "model",
                    provider=route.provider,
                    model=route.model,
                    reason=route.reason,
                    cost=cost,
                    tokens=tokens,
                )
                started = time.monotonic()
                try:
                    generation = await self.guarded(
                        run_id,
                        token,
                        self.router.providers[route.provider].generate(prompt, checkpoint),
                    )
                    checkpoint["pending_action"] = generation.action.model_dump()
                    actual_cost = reserve_cost(
                        generation.input_tokens,
                        generation.output_tokens,
                        route.input_rate,
                        route.output_rate,
                    )
                    await self.store.finish_step(
                        run_id,
                        token,
                        step["id"],
                        checkpoint,
                        {
                            "action": generation.action.model_dump(),
                            "input_tokens": generation.input_tokens,
                            "output_tokens": generation.output_tokens,
                        },
                        int((time.monotonic() - started) * 1000),
                        actual_cost,
                        generation.input_tokens + generation.output_tokens,
                    )
                except ProviderError as exc:
                    await self.store.fail_step(
                        run_id,
                        token,
                        step["id"],
                        exc.kind,
                        retry_delay(step["attempt"]),
                        exc.retryable,
                    )
                    return
            else:
                action = Action.model_validate(checkpoint["pending_action"])
                if action.operation == "finish":
                    if checkpoint["tests_passed"]:
                        await self.store.finish_run(
                            run_id, token, Status.COMPLETED, output=action.explanation
                        )
                    else:
                        await self.store.finish_run(
                            run_id, token, Status.FAILED, error="VerificationRequired"
                        )
                    return
                step = await self.store.start_step(run_id, token, "tool")
                started = time.monotonic()
                try:
                    request = ToolRequest(
                        operation_id=step["id"], action=action, files=checkpoint["files"]
                    )
                    result = await self.guarded(run_id, token, self.tools.execute(request))
                    if result.timeout_reason:
                        raise ProviderError("ToolTimeout", False)
                    if action.operation == "write_file" and result.exit_code == 0:
                        checkpoint["files"][action.path] = action.content
                        checkpoint["tests_passed"] = False
                    if action.operation == "run_tests":
                        checkpoint["tests_passed"] = result.exit_code == 0
                    checkpoint["last_result"] = result.model_dump()
                    checkpoint["history"].append(
                        {
                            "operation": action.operation,
                            "path": action.path,
                            "exit_code": result.exit_code,
                        }
                    )
                    checkpoint["pending_action"] = None
                    await self.store.finish_step(
                        run_id,
                        token,
                        step["id"],
                        checkpoint,
                        {"operation": action.operation, "path": action.path, **result.model_dump()},
                        int((time.monotonic() - started) * 1000),
                    )
                except ProviderError as exc:
                    await self.store.fail_step(
                        run_id,
                        token,
                        step["id"],
                        exc.kind,
                        retry_delay(step["attempt"]),
                        exc.retryable,
                    )
                    return
                except ValueError:
                    await self.store.fail_step(
                        run_id, token, step["id"], "InvalidToolArguments", 0, False
                    )
                    return
