"""`SignalsPresenter` — `EPIC-007E` §3 / `EPIC-007F`, extended by
`EPIC-008F`'s per-dead-letter `id`/`agoSeconds` and per-machine
`attemptedCount`/`declaredStates`/nested `transitions` (with a real
`reason` on each rejected one).

Same `Mock` container + real `MemoryEventBus` fixture
`test_container_presenter.py`/`test_tasks_presenter.py` established -- no
`QApplication`, no real websocket, no QML."""

from __future__ import annotations

import os
from unittest.mock import Mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")

from sagittarius_engine.extensions.audit.contracts import (  # noqa: E402
    DeadLetterEntry,
    SignalsState,
    StateMachineState,
    StateMachineTransition,
    StateSnapshot,
)
from sagittarius_engine.infrastructure.event_bus.memory_event_bus import (  # noqa: E402
    MemoryEventBus,
)
from sagittarius_engine.interfaces import (  # noqa: E402
    IConfig,
    IDispatcher,
    IEventBus,
    ILogger,
)
from tools.state_console.domain.events import SnapshotReceived  # noqa: E402
from tools.state_console.presentation.signals.signals_presenter import (  # noqa: E402
    SignalsPresenter,
)


@pytest.fixture
def container_with_bus():
    bus = MemoryEventBus()
    config = Mock()
    config.get.return_value = False
    config.get_all.return_value = {}

    def resolve(interface):
        return {
            IEventBus: bus,
            ILogger: Mock(),
            IDispatcher: Mock(),
            IConfig: config,
        }[interface]

    container = Mock()
    container.resolve.side_effect = resolve
    return container, bus


@pytest.fixture
def presenter(container_with_bus):
    container, bus = container_with_bus
    p = SignalsPresenter(Mock(), container)
    try:
        yield p, bus
    finally:
        p.dispose()


def test_dead_letters_carry_a_positional_id_and_a_real_age(presenter):
    p, bus = presenter
    bus.emit(
        SnapshotReceived(
            StateSnapshot(
                t=10_000_000_000,
                signals=SignalsState(
                    dead_letters=(
                        DeadLetterEntry(event_name="e", parked_at_ns=7_000_000_000),
                    )
                ),
            )
        )
    )

    (entry,) = p.view_model.deadLetters
    assert entry["id"] == "dl-0"
    assert entry["agoSeconds"] == pytest.approx(3.0)


def test_dead_letter_ids_are_positional_across_multiple_entries(presenter):
    p, bus = presenter
    bus.emit(
        SnapshotReceived(
            StateSnapshot(
                signals=SignalsState(
                    dead_letters=(
                        DeadLetterEntry(event_name="a"),
                        DeadLetterEntry(event_name="b"),
                    )
                )
            )
        )
    )

    ids = [e["id"] for e in p.view_model.deadLetters]
    assert ids == ["dl-0", "dl-1"]


def test_a_state_machine_carries_attempted_count_and_declared_states(presenter):
    p, bus = presenter
    bus.emit(
        SnapshotReceived(
            StateSnapshot(
                signals=SignalsState(
                    state_machines=(
                        StateMachineState(
                            name="Door",
                            current_state="OPEN",
                            rejected_count=1,
                            attempted_count=3,
                            declared_states=("CLOSED", "OPEN", "LOCKED"),
                        ),
                    )
                )
            )
        )
    )

    (machine,) = p.view_model.stateMachines
    assert machine["attemptedCount"] == 3
    assert machine["declaredStates"] == ["CLOSED", "OPEN", "LOCKED"]


def test_a_machines_transitions_are_nested_newest_first_with_a_real_age_and_reason(
    presenter,
):
    p, bus = presenter
    bus.emit(
        SnapshotReceived(
            StateSnapshot(
                t=10_000_000_000,
                signals=SignalsState(
                    state_machines=(
                        StateMachineState(
                            name="Door",
                            transitions=(
                                StateMachineTransition(
                                    from_state="CLOSED",
                                    to_state="OPEN",
                                    at_ns=8_000_000_000,
                                ),
                                StateMachineTransition(
                                    from_state="OPEN",
                                    to_state="LOCKED",
                                    rejected=True,
                                    reason="Invalid transition from 'OPEN' to 'LOCKED'.",
                                    at_ns=9_000_000_000,
                                ),
                            ),
                        ),
                    )
                ),
            )
        )
    )

    (machine,) = p.view_model.stateMachines
    # Newest-last on the wire (StateMachineTransition's own docstring) ->
    # newest-first here (reference/handoff.md §7.6's own ordering).
    first, second = machine["transitions"]
    assert first["toState"] == "LOCKED"
    assert first["rejected"] is True
    assert first["reason"] == "Invalid transition from 'OPEN' to 'LOCKED'."
    assert first["ageSeconds"] == pytest.approx(1.0)
    assert second["toState"] == "OPEN"
    assert second["rejected"] is False
    assert second["reason"] == ""


def test_absent_signals_leaves_the_view_model_untouched(presenter):
    p, bus = presenter
    bus.emit(SnapshotReceived(StateSnapshot(signals=None)))

    assert p.view_model.deadLetters == []
    assert p.view_model.stateMachines == []
