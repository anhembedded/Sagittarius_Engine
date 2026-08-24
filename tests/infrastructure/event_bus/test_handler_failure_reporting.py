"""Every `IEventBus` implementation must make a handler's exception visible,
and must not log one line per emitted event at INFO (EPIC-008C).

Why this file exists — the two defects it locks down, both found 2026-08-24
auditing `Sagittarius_Elite_Warrior`'s event flow:

1. **A handler exception could vanish completely.** Every bus guarded its
   error log with `if self.logger:`, and the reference consumer constructs
   `MemoryEventBus()` with no logger at all — so an exception raised inside
   any handler, on any screen, left no trace anywhere. A library that loses
   exceptions by default is defective regardless of how the application is
   wired, so the fix is a non-silent default, not a note telling consumers
   to pass a logger.
2. **`emit()` logged every event at INFO, payload included.** `MarketTickEvent`
   fires once per websocket tick; that is the log flood which froze the UI
   thread in the consuming app's `BUG-042`. Flow tracing belongs at TRACE —
   the level `ILogger` already documents as "too high-frequency even for a
   normal `--dev` run".

The tests are parametrized across every bus that dispatches to handlers, on
purpose: the defect was identical in four separate implementations, which is
what made a shared reporting module the right fix instead of patching the one
bus the bug was reported against.
"""

from __future__ import annotations

import asyncio
import logging
from unittest.mock import MagicMock

import pytest

from sagittarius_engine.infrastructure.event_bus.asyncio_event_bus import (
    AsyncioEventBus,
)
from sagittarius_engine.infrastructure.event_bus.memory_event_bus import MemoryEventBus
from sagittarius_engine.infrastructure.event_bus.resilient_event_bus import (
    ResilientEventBus,
)
from sagittarius_engine.infrastructure.event_bus.thread_pool_event_bus import (
    ThreadPoolEventBus,
)

_EVENT = "some.event"


def _boom(_data: object) -> None:
    raise ValueError("handler exploded")


def _emit_sync(bus, event_name: str = _EVENT, payload: object = None) -> None:
    bus.emit(event_name, payload)


def _make_memory_bus(logger=None):
    return MemoryEventBus(logger=logger)


def _make_resilient_bus(logger=None):
    #: `max_retries=0` — this suite is about whether a failure is *reported*,
    #: not about retry behaviour; retrying would just multiply the records.
    return ResilientEventBus(
        inner_bus=MemoryEventBus(logger=logger), max_retries=0, logger=logger
    )


def _make_thread_pool_bus(logger=None):
    #: `max_workers=1` keeps the single-handler assertions in this file
    #: deterministic; the pool's concurrency is not what is under test here.
    return ThreadPoolEventBus(max_workers=1, logger=logger)


#: Every bus whose `emit()` runs handlers synchronously enough for a test to
#: assert on the result immediately after the call returns.
_SYNC_BUS_FACTORIES = [
    pytest.param(_make_memory_bus, id="MemoryEventBus"),
    pytest.param(_make_resilient_bus, id="ResilientEventBus"),
]


@pytest.mark.parametrize("make_bus", _SYNC_BUS_FACTORIES)
def test_handler_exception_is_reported_even_with_no_logger_injected(make_bus, caplog):
    """The exact shape of the reported bug: a bus built with no logger, a
    handler that raises, and — before this fix — no trace of it anywhere."""
    bus = make_bus(logger=None)
    bus.on(_EVENT, _boom)

    with caplog.at_level(logging.ERROR):
        _emit_sync(bus)

    assert caplog.records, (
        "A handler raised and nothing was logged. A bus constructed without an "
        "explicit logger must still report handler failures."
    )
    assert any("handler exploded" in record.getMessage() for record in caplog.records)


@pytest.mark.parametrize("make_bus", _SYNC_BUS_FACTORIES)
def test_handler_exception_report_includes_a_traceback(make_bus):
    """`str(exception)` alone is not enough to find where a failure came
    from — that shortfall cost the consuming app a misdirected investigation
    (`BOT-061`), which is why `safe_ui_action` carries a full traceback and
    why this must too."""
    logger = MagicMock()
    bus = make_bus(logger=logger)
    bus.on(_EVENT, _boom)

    _emit_sync(bus)

    logger.error.assert_called()
    _, kwargs = logger.error.call_args
    extra = kwargs.get("extra") or {}
    assert "traceback" in extra, (
        f"Handler-failure report carried no traceback; extra={extra!r}"
    )
    assert "ValueError" in extra["traceback"]
    assert "_boom" in extra["traceback"]


@pytest.mark.parametrize("make_bus", _SYNC_BUS_FACTORIES)
def test_emitting_does_not_log_at_info(make_bus):
    """One INFO line per emitted event is the `BUG-042` flood. Flow tracing
    goes to TRACE instead."""
    logger = MagicMock()
    bus = make_bus(logger=logger)
    bus.on(_EVENT, lambda _data: None)

    _emit_sync(bus)

    logger.info.assert_not_called()
    #: Exactly once, not merely "at least once": `ResilientEventBus` used to
    #: write its own dispatch line on top of the inner bus's, so one emit
    #: produced two records saying the same thing with different handler
    #: counts. Tracing belongs to whichever bus actually holds the handlers.
    assert logger.trace.call_count == 1


@pytest.mark.parametrize("make_bus", _SYNC_BUS_FACTORIES)
def test_a_failing_handler_does_not_stop_the_next_one(make_bus):
    """Isolation is the reason the exception is caught at all — one screen's
    broken handler must not take the others down with it. Locked down here so
    a later change cannot quietly turn "report it" into "re-raise it"."""
    logger = MagicMock()
    bus = make_bus(logger=logger)
    seen: list[str] = []

    bus.on(_EVENT, _boom)
    bus.on(_EVENT, lambda _data: seen.append("second"))

    _emit_sync(bus)

    assert seen == ["second"]


def test_thread_pool_bus_reports_handler_exception_with_no_logger(caplog):
    """`ThreadPoolEventBus` runs handlers on an executor, so the assertion
    waits for the future rather than reading straight after `emit()`."""
    bus = _make_thread_pool_bus(logger=None)
    bus.on(_EVENT, _boom)

    with caplog.at_level(logging.ERROR):
        bus.emit(_EVENT, None)
        bus._executor.shutdown(wait=True)

    assert any("handler exploded" in record.getMessage() for record in caplog.records)


def test_asyncio_bus_reports_handler_exception_with_no_logger(caplog):
    bus = AsyncioEventBus()
    bus.on(_EVENT, _boom)

    with caplog.at_level(logging.ERROR):
        asyncio.run(bus.emit(_EVENT, None))

    assert any("handler exploded" in record.getMessage() for record in caplog.records)


def test_asyncio_bus_does_not_log_every_emit_at_info():
    logger = MagicMock()
    bus = AsyncioEventBus(logger=logger)
    bus.on(_EVENT, lambda _data: None)

    asyncio.run(bus.emit(_EVENT, None))

    logger.info.assert_not_called()
    logger.trace.assert_called()
