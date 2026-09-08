"""`SignalsViewModel` — `EPIC-007E` §3 / `EPIC-007F`: the dead-letter queue
and state-machine panels.

Data only, no application logic — `SignalsPresenter` owns every decision;
this class exposes state as Qt Properties/Signals, the same division of
labour `OverviewViewModel`'s own docstring states.
"""

from __future__ import annotations

from PySide6.QtCore import Property, Signal

from sagittarius_engine.extensions.pyside_mvc import BaseQmlViewModel
from tools.state_console.presentation.overview.overview_view_model import (
    NOT_ATTACHED,
)

#: `EPIC-007F` §2.2 — the control is visible and disabled, with the reason
#: stated on screen, rather than hidden or silently wired: "a queue you can
#: see and not act on is half a feature, and hiding the control hides the
#: fact that a remedy exists." Wiring it needs ADR-003 (`EPIC-007` §6).
REPROCESS_DISABLED_REASON = (
    "Write actions are off — reprocessing re-emits into the live application "
    "from this socket. See EPIC-007 §6 / ADR-003."
)


class SignalsViewModel(BaseQmlViewModel):
    connectionStateChanged = Signal()
    detachReasonChanged = Signal()
    deadLettersChanged = Signal()
    stateMachinesChanged = Signal()
    transitionsChanged = Signal()
    uiThreadChanged = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._connection_state = NOT_ATTACHED
        self._detach_reason = ""
        self._dead_letters: list[dict] = []
        self._state_machines: list[dict] = []
        self._transitions: list[dict] = []
        self._has_ui_thread = False
        self._freeze_count = 0
        self._worst_freeze_ms = 0.0
        self._off_thread_mutation_count = 0

    def _get_connection_state(self) -> str:
        return self._connection_state

    def set_connection_state(self, value: str) -> None:
        if value != self._connection_state:
            self._connection_state = value
            self.connectionStateChanged.emit()

    connectionState = Property(
        str, _get_connection_state, notify=connectionStateChanged
    )

    def _get_detach_reason(self) -> str:
        return self._detach_reason

    def set_detach_reason(self, value: str) -> None:
        if value != self._detach_reason:
            self._detach_reason = value
            self.detachReasonChanged.emit()

    detachReason = Property(str, _get_detach_reason, notify=detachReasonChanged)

    def _get_reprocess_disabled_reason(self) -> str:
        return REPROCESS_DISABLED_REASON

    reprocessDisabledReason = Property(
        str, _get_reprocess_disabled_reason, constant=True
    )

    def _get_dead_letters(self) -> list:
        return self._dead_letters

    deadLetters = Property(
        "QVariantList",  # type: ignore[arg-type]
        _get_dead_letters,
        notify=deadLettersChanged,
    )

    def set_dead_letters(self, entries: list[dict]) -> None:
        self._dead_letters = entries
        self.deadLettersChanged.emit()

    def _get_state_machines(self) -> list:
        return self._state_machines

    stateMachines = Property(
        "QVariantList",  # type: ignore[arg-type]
        _get_state_machines,
        notify=stateMachinesChanged,
    )

    def _get_transitions(self) -> list:
        return self._transitions

    transitions = Property(
        "QVariantList",  # type: ignore[arg-type]
        _get_transitions,
        notify=transitionsChanged,
    )

    def set_state_machines(self, machines: list[dict], transitions: list[dict]) -> None:
        self._state_machines = machines
        self._transitions = transitions
        self.stateMachinesChanged.emit()
        self.transitionsChanged.emit()

    def _get_has_ui_thread(self) -> bool:
        return self._has_ui_thread

    hasUiThreadHealth = Property(bool, _get_has_ui_thread, notify=uiThreadChanged)

    def _get_freeze_count(self) -> int:
        return self._freeze_count

    freezeCount = Property(int, _get_freeze_count, notify=uiThreadChanged)

    def _get_worst_freeze_ms(self) -> float:
        return self._worst_freeze_ms

    worstFreezeMs = Property(float, _get_worst_freeze_ms, notify=uiThreadChanged)

    def _get_off_thread_mutation_count(self) -> int:
        return self._off_thread_mutation_count

    offThreadMutationCount = Property(
        int, _get_off_thread_mutation_count, notify=uiThreadChanged
    )

    def set_ui_thread_health(
        self, freeze_count: int, worst_freeze_ms: float, off_thread_mutation_count: int
    ) -> None:
        self._has_ui_thread = True
        self._freeze_count = freeze_count
        self._worst_freeze_ms = worst_freeze_ms
        self._off_thread_mutation_count = off_thread_mutation_count
        self.uiThreadChanged.emit()

    def clear_ui_thread_health(self) -> None:
        if self._has_ui_thread:
            self._has_ui_thread = False
            self._freeze_count = 0
            self._worst_freeze_ms = 0.0
            self._off_thread_mutation_count = 0
            self.uiThreadChanged.emit()
