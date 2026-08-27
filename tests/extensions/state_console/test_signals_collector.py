"""`SignalsCollector` — `EPIC-007F`. Narrow: a plain object standing in for
a bus (`get_dlq()`/`max_retries`) is enough, the same fixture-lightness
`LifecycleCollector`'s own tests rely on."""

from __future__ import annotations

from enum import Enum, auto
from types import SimpleNamespace

from sagittarius_engine.extensions.audit.contracts import UiThreadHealth
from sagittarius_engine.extensions.fsm.state_machine import BaseStateMachine
from sagittarius_engine.extensions.state_console.collectors.signals import (
    SignalsCollector,
)
from sagittarius_engine.extensions.state_console.state_machine_watcher import (
    _StateMachineWatcher,
)


class _Door(Enum):
    CLOSED = auto()
    OPEN = auto()


def _fake_bus(rows, max_retries=1):
    return SimpleNamespace(get_dlq=lambda: rows, max_retries=max_retries)


def test_an_unwatched_collector_reports_everything_empty():
    collector = SignalsCollector([], {}, [])
    signals = collector.collect()

    assert signals.dead_letters == ()
    assert signals.state_machines == ()
    assert signals.ui_thread is None


def test_dlq_rows_from_a_watched_bus_are_translated():
    bus = _fake_bus(
        [("e", {"x": 1}, lambda d: None, ValueError("boom"), 5)], max_retries=2
    )
    collector = SignalsCollector([bus], {}, [])

    (entry,) = collector.collect().dead_letters
    assert entry.event_name == "e"
    assert entry.exception_type == "ValueError"
    assert entry.retries == 2
    assert entry.parked_at_ns == 5


def test_multiple_watched_buses_are_flattened_together():
    bus_a = _fake_bus([("a", None, lambda d: None, ValueError(), 1)])
    bus_b = _fake_bus([("b", None, lambda d: None, KeyError(), 2)])
    collector = SignalsCollector([bus_a, bus_b], {}, [])

    names = {e.event_name for e in collector.collect().dead_letters}
    assert names == {"a", "b"}


def test_watched_state_machines_are_collected_by_name():
    door = BaseStateMachine(_Door.CLOSED)
    door.add_transition(_Door.CLOSED, _Door.OPEN)
    watcher = _StateMachineWatcher("Door", door)
    door.transition_to(_Door.OPEN)

    collector = SignalsCollector([], {"Door": watcher}, [])

    (state,) = collector.collect().state_machines
    assert state.name == "Door"
    assert state.current_state == "OPEN"


def test_ui_thread_health_is_absent_when_no_source_registered():
    collector = SignalsCollector([], {}, [])
    assert collector.collect().ui_thread is None


def test_ui_thread_health_calls_the_registered_source():
    health = UiThreadHealth(freeze_count=2, worst_freeze_ms=100.0)
    sources = [lambda: health]
    collector = SignalsCollector([], {}, sources)

    assert collector.collect().ui_thread == health


def test_a_later_registered_source_replaces_the_earlier_one():
    """Matches `StateConsoleExtension.watch_ui_thread_health()`'s own
    "a second call replaces the source" contract -- the collector always
    uses whatever is last in the (live) list it was handed."""
    sources: list = [lambda: UiThreadHealth(freeze_count=1)]
    collector = SignalsCollector([], {}, sources)
    assert collector.collect().ui_thread == UiThreadHealth(freeze_count=1)

    sources[:] = [lambda: UiThreadHealth(freeze_count=9)]
    assert collector.collect().ui_thread == UiThreadHealth(freeze_count=9)


def test_mutating_the_live_containers_after_construction_is_visible():
    """`StateConsoleExtension` hands this collector the SAME list/dict it
    owns, deliberately, so a `watch_*()` call made after the collector was
    built (a common ordering in practice -- see that extension's own
    comment) is still picked up."""
    dlq_buses: list = []
    watchers: dict = {}
    collector = SignalsCollector(dlq_buses, watchers, [])
    assert collector.collect().dead_letters == ()
    assert collector.collect().state_machines == ()

    dlq_buses.append(_fake_bus([("late", None, lambda d: None, ValueError(), 1)]))
    door = BaseStateMachine(_Door.CLOSED)
    watchers["LateDoor"] = _StateMachineWatcher("LateDoor", door)

    signals = collector.collect()
    assert signals.dead_letters[0].event_name == "late"
    assert signals.state_machines[0].name == "LateDoor"
