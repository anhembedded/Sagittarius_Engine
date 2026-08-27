"""`_StateMachineWatcher` — `EPIC-007F` §3. Narrow, no booted app needed,
matching `LifecycleCollector`'s own precedent ("a two-line fixture can test
this without booting an application")."""

from __future__ import annotations

from enum import Enum, auto

import pytest

from sagittarius_engine.extensions.fsm.declarative_state_machine import (
    DeclarativeStateMachine,
)
from sagittarius_engine.extensions.fsm.exceptions import InvalidStateTransitionError
from sagittarius_engine.extensions.fsm.state_machine import BaseStateMachine
from sagittarius_engine.extensions.state_console.state_machine_watcher import (
    _MAX_TRANSITIONS,
    _StateMachineWatcher,
)


class _Door(Enum):
    CLOSED = auto()
    OPEN = auto()
    LOCKED = auto()


class _DoorEvent(Enum):
    OPEN = auto()
    CLOSE = auto()


def _door() -> BaseStateMachine:
    door = BaseStateMachine(_Door.CLOSED)
    door.add_transition(_Door.CLOSED, _Door.OPEN)
    door.add_transition(_Door.OPEN, _Door.CLOSED)
    return door


def test_a_successful_transition_is_recorded_via_the_global_callback():
    door = _door()
    watcher = _StateMachineWatcher("Door", door)

    door.transition_to(_Door.OPEN)

    state = watcher.collect()
    assert state.name == "Door"
    assert state.current_state == "OPEN"
    assert state.rejected_count == 0
    assert len(state.transitions) == 1
    assert state.transitions[0].from_state == "CLOSED"
    assert state.transitions[0].to_state == "OPEN"
    assert state.transitions[0].rejected is False


def test_a_rejected_transition_is_recorded_and_still_raises():
    door = _door()
    watcher = _StateMachineWatcher("Door", door)

    with pytest.raises(InvalidStateTransitionError):
        door.transition_to(_Door.LOCKED)  # CLOSED -> LOCKED is not wired

    state = watcher.collect()
    assert state.rejected_count == 1
    assert state.current_state == "CLOSED"  # the machine's own state is unchanged
    (transition,) = state.transitions
    assert transition.rejected is True
    assert transition.from_state == "CLOSED"
    assert transition.to_state == "LOCKED"


def test_the_apps_own_exception_handling_is_unaffected():
    """The watcher must not swallow or alter the exception -- a caller that
    already catches `InvalidStateTransitionError` sees exactly the same
    thing whether or not a console is attached."""
    door = _door()
    _StateMachineWatcher("Door", door)

    try:
        door.transition_to(_Door.LOCKED)
        raised = None
    except InvalidStateTransitionError as exc:
        raised = exc

    assert raised is not None
    assert raised.from_state == "CLOSED"
    assert raised.to_state == "LOCKED"


def test_accepted_and_rejected_transitions_interleave_in_order():
    door = _door()
    watcher = _StateMachineWatcher("Door", door)

    door.transition_to(_Door.OPEN)
    with pytest.raises(InvalidStateTransitionError):
        door.transition_to(_Door.LOCKED)
    door.transition_to(_Door.CLOSED)

    state = watcher.collect()
    assert [t.rejected for t in state.transitions] == [False, True, False]
    assert state.rejected_count == 1


def test_transitions_are_bounded_and_drop_the_oldest():
    door = _door()
    watcher = _StateMachineWatcher("Door", door)

    for i in range(_MAX_TRANSITIONS + 10):
        door.transition_to(_Door.OPEN if i % 2 == 0 else _Door.CLOSED)

    state = watcher.collect()
    assert len(state.transitions) == _MAX_TRANSITIONS


def test_a_declarative_state_machines_dispatch_is_watched_too():
    """`dispatch()` is `DeclarativeStateMachine`'s own entry point -- a
    plain `BaseStateMachine` has no `dispatch` at all, so the watcher must
    wrap whichever methods the machine actually exposes."""
    machine = DeclarativeStateMachine(_Door.CLOSED)
    machine.add_event_transition(_Door.CLOSED, _DoorEvent.OPEN, _Door.OPEN)
    watcher = _StateMachineWatcher("Door", machine)

    machine.dispatch(_DoorEvent.OPEN)
    with pytest.raises(InvalidStateTransitionError):
        machine.dispatch(_DoorEvent.OPEN)  # OPEN has no outgoing OPEN event

    state = watcher.collect()
    assert state.current_state == "OPEN"
    assert state.rejected_count == 1
    assert any(t.event == "OPEN" and t.rejected for t in state.transitions)


def test_watching_two_machines_keeps_their_logs_independent():
    door_a = _door()
    door_b = _door()
    watcher_a = _StateMachineWatcher("A", door_a)
    watcher_b = _StateMachineWatcher("B", door_b)

    door_a.transition_to(_Door.OPEN)

    assert len(watcher_a.collect().transitions) == 1
    assert len(watcher_b.collect().transitions) == 0
