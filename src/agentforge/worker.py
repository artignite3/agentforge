import asyncio
import contextlib
import logging
import signal

from agentforge.config import get_settings
from agentforge.providers import Router
from agentforge.runtime import RemoteTools, Runtime
from agentforge.store import LeaseLost, Store
from agentforge.telemetry import log


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    settings = get_settings()
    store = Store(settings)
    runtime = Runtime(
        store,
        Router(settings),
        RemoteTools(settings.sandbox_url, settings.sandbox_key.get_secret_value()),
    )
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
        await store.engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
