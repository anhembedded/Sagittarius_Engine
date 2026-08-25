"""Tests for the `HealthCheckRequested` → `HealthUpdatedEvent` request/response
pair (`EPIC-008E`).

The defect this closes: `HealthExtension.boot()` publishes exactly once, during
`app.boot()`, so any subscriber created afterwards — every lazily-built
presenter — never hears it. A screen therefore had no way to ask "how is the
system right now?" without fabricating the event itself.
"""

from __future__ import annotations

from typing import Any

import pytest

from sagittarius_engine.extensions.health.health_check_query import (
    HealthCheckDTO,
    HealthCheckQuery,
)
from sagittarius_engine.extensions.health.health_check_requested import (
    HealthCheckRequested,
)
from sagittarius_engine.extensions.health.health_module import HealthExtension
from sagittarius_engine.extensions.health.health_updated_event import HealthUpdatedEvent
from sagittarius_engine.infrastructure.event_bus.memory_event_bus import MemoryEventBus


class _CountingQuery(HealthCheckQuery):
    """Returns a different payload on each call, so a test can tell a freshly
    measured result from a replayed snapshot.

    Keeps `HealthCheckQuery.execute`'s exact signature — overriding it with a
    narrower one is an LSP break that `mypy` rejects, and the whole point of
    subclassing here (rather than duck-typing) is to stay substitutable."""

    def __init__(self) -> None:
        self.calls = 0

    def execute(self, input_dto: HealthCheckDTO | None = None) -> dict[str, Any]:
        self.calls += 1
        return {"status": "healthy", "components": {"db": f"ok-{self.calls}"}}


class _Container:
    def __init__(self, query: HealthCheckQuery) -> None:
        self._query = query
        self.bound: list[type] = []

    def bind(self, interface: type, implementation: type) -> None:
        self.bound.append(interface)

    def resolve(self, interface: type) -> Any:
        return self._query


class _Context:
    def __init__(self, container: _Container, event_bus: MemoryEventBus | None) -> None:
        self.container = container
        self.event_bus = event_bus
        self.logger = None


@pytest.fixture
def booted():
    """A booted `HealthExtension` plus the pieces a test needs to assert on."""
    query = _CountingQuery()
    bus = MemoryEventBus()
    context = _Context(_Container(query), bus)

    received: list[HealthUpdatedEvent] = []
    bus.on(HealthUpdatedEvent.event_name, received.append)

    extension = HealthExtension()
    extension.boot(context)
    return query, bus, received


def test_boot_still_reports_once(booted):
    """`EPIC-008E` adds the request path; it must not remove the boot-time
    report, which consumers outside this repository already rely on."""
    query, _bus, received = booted

    assert query.calls == 1
    assert len(received) == 1


def test_requesting_a_check_publishes_exactly_one_fresh_result(booted):
    query, bus, received = booted
    received.clear()

    bus.emit(HealthCheckRequested())

    assert len(received) == 1, "one request must produce exactly one response"
    assert query.calls == 2, "the query must be re-run, not replayed from boot"
    # The counting query changes its payload every call, so this asserts the
    # subscriber got the *new* measurement rather than boot's snapshot — the
    # exact thing the rejected sticky-bus design could not have given.
    assert received[0].status["components"]["db"] == "ok-2"


def test_each_request_re_measures(booted):
    """A screen re-opened three times gets three current answers."""
    query, bus, received = booted
    received.clear()

    for _ in range(3):
        bus.emit(HealthCheckRequested())

    assert len(received) == 3
    assert query.calls == 4  # 1 at boot + 3 requests
    assert [e.status["components"]["db"] for e in received] == ["ok-2", "ok-3", "ok-4"]


def test_a_failing_health_query_does_not_escape_into_the_bus(booted):
    """The request path runs inside a bus handler. A health check that blows up
    must be logged, not propagated — one broken subscriber may not take down
    the emitter or the other subscribers."""
    query, bus, received = booted
    received.clear()

    def explode() -> dict[str, Any]:
        raise RuntimeError("health probe failed")

    query.execute = explode  # type: ignore[method-assign]

    bus.emit(HealthCheckRequested())

    assert received == [], "no result should be published when the probe fails"


def test_extension_without_an_event_bus_still_boots():
    """`event_bus` is optional on the context Protocol; an app wiring the
    extension without one must not crash at boot, and must not try to
    subscribe."""
    query = _CountingQuery()
    context = _Context(_Container(query), None)

    HealthExtension().boot(context)

    assert query.calls == 1


def test_health_updated_event_is_still_importable_from_health_module():
    """Its module moved in `EPIC-008E`; the old import path is a published API
    that three call sites in the consuming app use."""
    from sagittarius_engine.extensions.health import health_module

    assert health_module.HealthUpdatedEvent is HealthUpdatedEvent
