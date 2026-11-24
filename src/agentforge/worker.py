import argparse
import asyncio
import contextlib
import logging
import signal
import sys
import time
from pathlib import Path

import httpx

from agentforge.config import Settings, get_settings, require_secret
from agentforge.models import uid
from agentforge.providers import Router
from agentforge.runtime import RemoteTools, Runtime
from agentforge.store import LeaseLost, Store
from agentforge.telemetry import log

HEARTBEAT_SECONDS = 5
# Touched on every successful database heartbeat; the container healthcheck reads its age.
HEARTBEAT_FILE = Path("/tmp/agentforge-worker-heartbeat")  # nosec B108
STALE_AFTER_SECONDS = 30


async def sandbox_ready(settings: Settings) -> bool:
    try:
        async with httpx.AsyncClient(timeout=3, trust_env=False) as client:
            return (await client.get(settings.sandbox_url + "/health")).status_code == 200
    except httpx.HTTPError:
        return False


class Heartbeat:
    """Publishes liveness, the current run, sandbox readiness, and the provider catalog."""

    def __init__(self, store: Store, settings: Settings, router: Router):
        self.store, self.settings, self.router = store, settings, router
        self.worker_id, self.started = uid(), time.time()
        self.run_id: str | None = None

    async def beat(self) -> None:
        await self.store.record_worker(
            self.worker_id,
            self.started,
            self.run_id,
            await sandbox_ready(self.settings),
            self.router.catalog(),
        )
        with contextlib.suppress(OSError):
            await asyncio.to_thread(HEARTBEAT_FILE.touch)

    async def forever(self) -> None:
        while True:
            try:
                await self.beat()
            except Exception as exc:
                log(
                    "worker",
                    "heartbeat.failed",
                    worker_id=self.worker_id,
                    error_type=type(exc).__name__,
                )
            await asyncio.sleep(HEARTBEAT_SECONDS)


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    settings = get_settings()
    sandbox_key = require_secret(settings.sandbox_key, "AGENTFORGE_SANDBOX_KEY")
    store = Store(settings)
    router = Router(settings)
    runtime = Runtime(store, router, RemoteTools(settings.sandbox_url, sandbox_key))
    heartbeat = Heartbeat(store, settings, router)
    beating = asyncio.create_task(heartbeat.forever())
    log("worker", "worker.started", worker_id=heartbeat.worker_id)
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError):
            loop.add_signal_handler(sig, stop.set)
    active: asyncio.Task[None] | None = None
    try:
        while not stop.is_set():
            try:
                claimed = await store.claim()
                if claimed:
                    heartbeat.run_id = claimed[0]
                    active = asyncio.create_task(runtime.execute(*claimed))
                    shutdown = asyncio.create_task(stop.wait())
                    done, _ = await asyncio.wait(
                        {active, shutdown}, return_when=asyncio.FIRST_COMPLETED
                    )
                    shutdown.cancel()
                    interrupted = active not in done
                    if interrupted:
                        active.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await active
                    active = None
                    heartbeat.run_id = None
                    if interrupted:
                        # Graceful stop: requeue immediately instead of waiting for lease
                        # expiry, and do not consume one of the run's crash recoveries.
                        with contextlib.suppress(LeaseLost):
                            await store.release(*claimed)
                        log("worker", "run.released", run_id=claimed[0])
                else:
                    await asyncio.sleep(settings.poll_seconds)
            except Exception as exc:
                # A DB outage must not busy-loop, expose credentials, or bypass fencing.
                log("worker", "iteration.failed", error_type=type(exc).__name__)
                await asyncio.sleep(2)
    finally:
        if active:
            active.cancel()
        beating.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await beating
        log("worker", "worker.stopped", worker_id=heartbeat.worker_id)
        await store.engine.dispose()


def check(path: Path = HEARTBEAT_FILE, stale_after: float = STALE_AFTER_SECONDS) -> int:
    """Container healthcheck: healthy only if the worker heartbeat reached the database."""
    try:
        age = time.time() - path.stat().st_mtime
    except OSError:
        return 1
    return 0 if age <= stale_after else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AgentForge queue worker")
    parser.add_argument("--check", action="store_true", help="Exit 0 if the heartbeat is fresh")
    if parser.parse_args().check:
        sys.exit(check())
    asyncio.run(main())
