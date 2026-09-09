from __future__ import annotations

from typing import Any

from sagittarius_engine.extensions.pyside_mvc import BasePresenter
from tools.state_console.domain.events import (
    ConsoleAttached,
    ConsoleDetached,
    SnapshotReceived,
)
from tools.state_console.presentation.overview.overview_view_model import (
    ATTACHED_IDLE,
    ATTACHED_READING,
    NOT_ATTACHED,
)
from tools.state_console.presentation.signals.signals_view_model import (
    SignalsViewModel,
)


class SignalsPresenter(BasePresenter):
    def __init__(self, view: Any, container: Any) -> None:
        super().__init__(view, container)
        self.view_model = SignalsViewModel()
        self.view.bind(self.view_model)
        self._connect_engine_events()

    def _connect_engine_events(self) -> None:
        self.subscribe(ConsoleAttached, self._on_attached)
        self.subscribe(ConsoleDetached, self._on_detached)
        self.subscribe(SnapshotReceived, self._on_snapshot)

    def _on_attached(self, _event: ConsoleAttached) -> None:
        self.view_model.set_connection_state(ATTACHED_IDLE)

    def _on_detached(self, event: ConsoleDetached) -> None:
        self.view_model.set_connection_state(NOT_ATTACHED)
        self.view_model.set_detach_reason(event.reason)

    def _on_snapshot(self, event: SnapshotReceived) -> None:
        self.view_model.set_connection_state(ATTACHED_READING)
        snapshot = event.snapshot
        signals = snapshot.signals
        if signals is None:
            return

        now_ns = snapshot.t
        self.view_model.set_dead_letters(
            [
                {
                    # A positional label ("dl-0", "dl-1", ...), not a
                    # fabricated business identifier -- this engine assigns
                    # no id to a parked event; the ordinal position is the
                    # only real, honest "id" a card in this list can carry.
                    "id": f"dl-{index}",
                    "eventName": d.event_name,
                    "handler": d.handler,
                    "exceptionType": d.exception_type,
                    "exceptionMessage": d.exception_message,
                    "payloadRepr": d.payload_repr,
                    "retries": d.retries,
                    # `parked_at_ns` is the same monotonic clock as
                    # `StateSnapshot.t` (its own docstring) -- a real elapsed
                    # duration, not a re-derived guess.
                    "agoSeconds": (now_ns - d.parked_at_ns) / 1_000_000_000,
                }
                for index, d in enumerate(signals.dead_letters)
            ]
        )

        self.view_model.set_state_machines(
            [self._state_machine_row(m, now_ns) for m in signals.state_machines]
        )

        if signals.ui_thread is not None:
            self.view_model.set_ui_thread_health(
                signals.ui_thread.freeze_count,
                signals.ui_thread.worst_freeze_ms,
                signals.ui_thread.off_thread_mutation_count,
            )
        else:
            self.view_model.clear_ui_thread_health()

    @staticmethod
    def _state_machine_row(machine: Any, now_ns: int) -> dict:
        return {
            "name": machine.name,
            "currentState": machine.current_state,
            "rejectedCount": machine.rejected_count,
            "attemptedCount": machine.attempted_count,
            "declaredStates": list(machine.declared_states),
            # Newest-first for the transition log -- `machine.transitions`
            # itself is newest-*last* (its own docstring, a plain append
            # log); `reference/handoff.md` §7.6 wants the log read newest
            # first, so the reversal happens once here rather than in QML.
            "transitions": [
                {
                    "fromState": t.from_state,
                    "toState": t.to_state,
                    "event": t.event,
                    "rejected": t.rejected,
                    "reason": t.reason,
                    "ageSeconds": (now_ns - t.at_ns) / 1_000_000_000,
                }
                for t in reversed(machine.transitions)
            ],
        }
