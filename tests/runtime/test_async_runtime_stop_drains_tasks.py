"""
`BUG-017` — `AsyncRuntime.stop()` lets cancelled tasks finish their cleanup.

`stop()` used to stop the loop first and only then cancel what was still
pending, so a task cancelled after its loop had stopped never ran again: its
`finally` was dropped and the interpreter reported `Task was destroyed but it
is pending!`. The reference consumer met it as an unclosed `aiohttp` session
when the app stopped with a websocket stream live.
"""

import asyncio
import time

from sagittarius_engine.infrastructure.container.std_container import StdLibContainer
from sagittarius_engine.infrastructure.event_bus.memory_event_bus import MemoryEventBus
from sagittarius_engine.kernel.app import App


def _app() -> App:
    app = App(StdLibContainer(), MemoryEventBus())
    app.context.async_runtime.start()
    return app


def _wait_until(condition, timeout: float = 2.0) -> None:
    deadline = time.monotonic() + timeout
    while not condition():
        assert time.monotonic() < deadline, "condition not met in time"
        time.sleep(0.01)


def test_stop_runs_the_finally_of_a_task_cancelled_just_before_it():
    """
    [Unit Test - UT]
    A spawned stream is cancelled by its owner, then the runtime stops at once:
    the stream's `finally`, which awaits a close, still completes.
    """
    app = _app()
    started: list[str] = []
    cleaned: list[str] = []

    async def stream() -> None:
        started.append("running")
        try:
            await asyncio.sleep(3600)
        finally:
            await asyncio.sleep(0)
            cleaned.append("closed")

    handle = app.context.tasks.spawn(stream(), name="stream")
    _wait_until(lambda: started == ["running"])

    handle.cancel()
    app.context.async_runtime.stop()

    assert cleaned == ["closed"]


def test_stop_cancels_a_running_task_and_runs_its_finally():
    """
    [Unit Test - UT]
    A task nobody cancelled is cancelled by `stop()` itself, and its awaited
    cleanup completes before the loop closes.
    """
    app = _app()
    started: list[str] = []
    cleaned: list[str] = []

    async def stream() -> None:
        started.append("running")
        try:
            await asyncio.sleep(3600)
        finally:
            await asyncio.sleep(0)
            cleaned.append("closed")

    app.context.tasks.spawn(stream(), name="stream")
    _wait_until(lambda: started == ["running"])

    app.context.async_runtime.stop()

    assert cleaned == ["closed"]


def test_stop_does_not_wait_past_its_timeout_for_a_task_that_ignores_cancel():
    """
    [Unit Test - UT]
    A task that swallows its cancellation cannot hold `stop()` beyond the
    timeout it was given.
    """
    app = _app()
    started: list[str] = []

    async def stubborn() -> None:
        started.append("running")
        while True:
            try:
                await asyncio.sleep(3600)
            except asyncio.CancelledError:
                continue

    app.context.tasks.spawn(stubborn(), name="stubborn")
    _wait_until(lambda: started == ["running"])

    began = time.monotonic()
    app.context.async_runtime.stop(timeout=0.3)

    assert time.monotonic() - began < 2.0
