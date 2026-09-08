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
        signals = event.snapshot.signals
        if signals is None:
            return

        self.view_model.set_dead_letters(
            [
                {
                    "eventName": d.event_name,
                    "handler": d.handler,
                    "exceptionType": d.exception_type,
                    "exceptionMessage": d.exception_message,
                    "payloadRepr": d.payload_repr,
                    "retries": d.retries,
                }
                for d in signals.dead_letters
            ]
        )

        machines = [
            {
                "name": m.name,
                "currentState": m.current_state,
                "rejectedCount": m.rejected_count,
            }
            for m in signals.state_machines
        ]
        transitions = [
            {
                "machine": m.name,
                "fromState": t.from_state,
                "toState": t.to_state,
                "event": t.event,
                "rejected": t.rejected,
            }
            for m in signals.state_machines
            for t in m.transitions
        ]
        self.view_model.set_state_machines(machines, transitions)

        if signals.ui_thread is not None:
            self.view_model.set_ui_thread_health(
                signals.ui_thread.freeze_count,
                signals.ui_thread.worst_freeze_ms,
                signals.ui_thread.off_thread_mutation_count,
            )
        else:
            self.view_model.clear_ui_thread_health()
