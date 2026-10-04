"""
`BUG-017` — `AsyncRuntime.stop()` lets cancelled tasks finish their cleanup.

`stop()` used to stop the loop first and only then cancel what was still
pending, so a task cancelled after its loop had stopped never ran again: its
`finally` was dropped and the interpreter reported `Task was destroyed but it
is pending!`. The reference consumer met it as an unclosed `aiohttp` session
when the app stopped with a websocket stream live.

The drain is bounded by `stop()`'s own `timeout`, which is one deadline for the
whole call (the PR #227 review): `App.stop()` gives the step exactly that long,
so a drain that used it all would leave the loop running behind a lifecycle
that already reads stopped.
"""

import asyncio
import logging
import time

import pytest

from sagittarius_engine.infrastructure.container.std_container import StdLibContainer
from sagittarius_engine.infrastructure.event_bus.memory_event_bus import MemoryEventBus
from sagittarius_engine.kernel.app import App

#: A cleanup that does real work, like closing a connection: longer than the
#: few loop iterations a zero-timeout wait would give it for free.
_CLEANUP_S = 0.05
#: Scheduling slack on top of a timeout, for the bounds below.
_SLACK_S = 0.25


def _app() -> App:
    app = App(StdLibContainer(), MemoryEventBus())
    app.context.async_runtime.start()
    return app


def _wait_until(condition, timeout: float = 2.0) -> None:
    deadline = time.monotonic() + timeout
    while not condition():
        assert time.monotonic() < deadline, "condition not met in time"
        time.sleep(0.01)


def _spawn_stream(app: App, started: list[str], cleaned: list[str]):
    async def stream() -> None:
        started.append("running")
        try:
            await asyncio.sleep(3600)
        finally:
            await asyncio.sleep(_CLEANUP_S)
            cleaned.append("closed")

    handle = app.context.tasks.spawn(stream(), name="stream")
    _wait_until(lambda: started == ["running"])
    return handle


def _spawn_stubborn(app: App) -> None:
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


def test_stop_runs_the_finally_of_a_task_cancelled_just_before_it():
    """
    [Unit Test - UT]
    A spawned stream is cancelled by its owner, then the runtime stops at once:
    the stream's `finally`, which awaits a close, still completes.
    """
    app = _app()
    started: list[str] = []
    cleaned: list[str] = []
    handle = _spawn_stream(app, started, cleaned)

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
    _spawn_stream(app, started, cleaned)

    app.context.async_runtime.stop()

    assert cleaned == ["closed"]


def test_stop_names_a_task_that_ignores_cancel_and_returns_within_its_timeout(
    caplog: pytest.LogCaptureFixture,
):
    """
    [Unit Test - UT]
    A task that swallows its cancellation cannot hold `stop()` past its
    timeout, and the WARNING names it by the name it was spawned with.
    """
    app = _app()
    _spawn_stubborn(app)
    timeout = 0.4

    began = time.monotonic()
    with caplog.at_level(logging.WARNING):
        app.context.async_runtime.stop(timeout=timeout)
    elapsed = time.monotonic() - began

    assert elapsed < timeout + _SLACK_S
    assert app.context.async_runtime.loop is None
    assert any("stubborn" in record.getMessage() for record in caplog.records)


def test_app_stop_leaves_the_loop_closed_when_a_task_ignores_cancel():
    """
    [Unit Test - UT]
    `App.stop()` gives the async-runtime step `step_timeout`. A task that never
    finishes cancelling must not use that whole budget in the drain: the loop
    is closed when `App.stop()` returns and reports the app stopped.
    """
    app = _app()
    _spawn_stubborn(app)

    app.stop(step_timeout=0.5)

    assert app.context.lifecycle.is_stopped
    assert app.context.async_runtime.loop is None


def test_stop_called_from_the_loop_thread_does_not_wait_on_its_own_loop():
    """
    [Unit Test - UT]
    `stop()` called from a coroutine on the loop skips the drain: waiting there
    would block the very loop the drain needs, for its whole budget.
    """
    app = _app()
    runtime = app.context.async_runtime

    async def stop_from_inside() -> float:
        began = time.monotonic()
        try:
            runtime.stop(timeout=1.0)
        except RuntimeError:
            pass  # joining its own thread is refused, as before BUG-017
        return time.monotonic() - began

    elapsed = runtime.run_coroutine(stop_from_inside()).result(timeout=3.0)

    assert elapsed < 0.2
    _wait_until(lambda: not runtime.loop.is_running())
    runtime.stop(timeout=0.3)
