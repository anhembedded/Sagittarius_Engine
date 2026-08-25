"""Tests for `EventRegistry` (EPIC-008B) — the auto-populated catalog
`BaseEvent` subclasses and the engine's own string-only lifecycle events
register themselves into, replacing a hand-maintained enum or document.
See `sagittarius_engine/domain/event_registry.py`'s module docstring for why
those two alternatives were rejected.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from sagittarius_engine.domain import BaseEvent, EventRegistry


@pytest.fixture
def isolated_registry():
    """Opt-in, not autouse: a test that defines its own throwaway event
    classes takes this fixture to get a clean registry and leave nothing
    behind for the next test. A test asserting on the *real* engine's
    already-registered events (`test_real_engine_events_stay_registered`
    below) must NOT take it — those events registered once, the first time
    their module was ever imported in this process (almost certainly during
    test collection, well before any fixture ran), and re-importing an
    already-cached module is a no-op that would not repopulate a cleared
    registry. `.agents/rules/testing.md`'s isolation discipline is about not
    leaking a test's *own* state into the next test, not about pretending
    real, permanent module-level registrations can be un-happened."""
    snapshot = dict(EventRegistry._entries)
    EventRegistry.clear()
    yield
    EventRegistry.clear()
    EventRegistry._entries.update(snapshot)


def test_dataclass_baseevent_subclass_registers_itself(isolated_registry):
    @dataclass
    class _Widget(BaseEvent):
        symbol: str

    entry = EventRegistry.get(_Widget.event_name)

    assert entry is not None
    assert entry.event_class is _Widget
    assert entry.payload_fields == ("symbol",)


def test_manual_init_baseevent_subclass_registers_itself(isolated_registry):
    class _Manual(BaseEvent):
        event_name = "manual.registered"

        def __init__(self, payload: str) -> None:
            super().__init__()
            self.payload = payload

    entry = EventRegistry.get("manual.registered")

    assert entry is not None
    assert entry.event_class is _Manual
    # Not a dataclass — no payload fields are derivable, and that is the
    # documented limitation, not a bug: EventRegistry reads `__dataclass_fields__`
    # lazily and has no other reliable source for a hand-written __init__'s
    # attributes.
    assert entry.payload_fields == ()


def test_register_named_is_how_string_only_events_get_catalogued(isolated_registry):
    """The shape `kernel/events.py`/`runtime/*/events.py` use for events
    that predate `BaseEvent` and are addressed by a bare string on the bus,
    not a class."""

    @dataclass
    class _LifecycleEvent:
        detail: str

    EventRegistry.register_named(
        "engine.lifecycle.something", _LifecycleEvent, module="tests.domain.fake"
    )

    entry = EventRegistry.get("engine.lifecycle.something")

    assert entry is not None
    assert entry.event_class is _LifecycleEvent
    assert entry.module == "tests.domain.fake"
    assert entry.payload_fields == ("detail",)


def test_register_named_without_a_payload_class(isolated_registry):
    """`"app.booted"`'s shape — the payload is the `App` instance itself,
    not a purpose-built event type."""
    EventRegistry.register_named("app.booted", None, module="tests.domain.fake")

    entry = EventRegistry.get("app.booted")

    assert entry is not None
    assert entry.event_class is None
    assert entry.qualname == "—"
    assert entry.payload_fields == ()


def test_all_returns_entries_sorted_by_event_name(isolated_registry):
    @dataclass
    class _Zebra(BaseEvent):
        pass

    @dataclass
    class _Apple(BaseEvent):
        pass

    names = [e.event_name for e in EventRegistry.all()]

    assert names == sorted(names)
    assert _Apple.event_name in names
    assert _Zebra.event_name in names


def test_get_returns_none_for_an_unregistered_event_name(isolated_registry):
    assert EventRegistry.get("nothing.registered.this.name") is None


def test_clear_empties_the_registry(isolated_registry):
    @dataclass
    class _Ephemeral(BaseEvent):
        pass

    assert EventRegistry.get(_Ephemeral.event_name) is not None

    EventRegistry.clear()

    assert EventRegistry.get(_Ephemeral.event_name) is None
    assert EventRegistry.all() == ()


def test_real_engine_events_stay_registered():
    """No `isolated_registry` fixture here on purpose (see its docstring):
    these are real, permanent module-level registrations, not throwaway test
    classes, so there is nothing to clean up afterward. The explicit imports
    below are each safe with an un-cleared registry regardless of whether
    pytest already imported that module elsewhere in the session — either
    this is the first import (registration happens now) or a cache hit
    (already registered from before); both leave the assertions true."""
    import sagittarius_engine.extensions.health.health_module  # noqa: F401
    import sagittarius_engine.kernel.bootstrap  # noqa: F401
    import sagittarius_engine.kernel.events  # noqa: F401
    import sagittarius_engine.runtime.tasks.events  # noqa: F401

    assert EventRegistry.get("health.updated") is not None
    assert EventRegistry.get("app.booted") is not None
    assert EventRegistry.get("extension.initializing") is not None
    assert EventRegistry.get("runtime.tasks.failed") is not None


def test_two_event_classes_sharing_a_name_warn_instead_of_vanishing_silently(
    isolated_registry, caplog
):
    """`event_name` defaults to `__qualname__`, so a bare class name reused in
    two modules resolves to one registry key and the later registration wins.
    That is allowed — but it must not be *silent*, because the loser also
    disappears from the generated `EVENT_CATALOG.md`, and a catalog that
    quietly omits an event defeats the reason a registry replaced a
    hand-written document in the first place."""

    # Registration happens in `__init_subclass__`, i.e. at `class` execution —
    # so the collision has to be produced by *defining* the second class inside
    # the capture block. Re-registering an already-created class afterwards
    # would compare it against itself and stay (correctly) silent.
    @dataclass
    class Progress(BaseEvent):
        pct: float

    first = Progress
    EventRegistry.register_named(first.event_name, first, module="app.alpha")

    with caplog.at_level("WARNING"):

        @dataclass
        class Progress(BaseEvent):  # noqa: F811 — the collision is the point
            pct: float

        second = Progress

    assert "Progress" in caplog.text
    assert "app.alpha" in caplog.text, "the warning must name who is being replaced"
    assert "EVENT_CATALOG.md" in caplog.text, (
        "the warning must say what is actually lost, not just that a name repeated"
    )
    # Both classes are declared inside this function, so the auto-assigned
    # `event_name` is the full `__qualname__` (`...<locals>.Progress`), not the
    # bare class name — that shared key is precisely what makes them collide.
    assert first.event_name == second.event_name
    # Last-write-wins is the documented behaviour; the warning is the fix,
    # not a change of outcome.
    assert EventRegistry.get(second.event_name).event_class is second


def test_registering_the_same_class_twice_is_not_a_collision(isolated_registry, caplog):
    """A module reload or a repeated import re-runs registration with the very
    same class object. Warning there would train readers to ignore the
    warning, so it stays silent."""

    @dataclass
    class Reimported(BaseEvent):
        value: int

    EventRegistry.register(Reimported)
    with caplog.at_level("WARNING"):
        EventRegistry.register(Reimported)

    assert caplog.text == ""


def test_register_named_also_warns_when_it_shadows_an_existing_name(
    isolated_registry, caplog
):
    """The string-only lifecycle path shares the same keyspace, so it can
    shadow a `BaseEvent` subclass just as easily."""

    @dataclass
    class Booted(BaseEvent):
        event_name = "app.booted"

    EventRegistry.register(Booted)
    with caplog.at_level("WARNING"):
        EventRegistry.register_named("app.booted", None, module="some.other.module")

    assert "app.booted" in caplog.text
