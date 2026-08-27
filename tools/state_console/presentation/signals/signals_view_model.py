"""`SignalsViewModel` — `EPIC-007E` §3, "Signals": the dead-letter queue and
state machines panel `EPIC-007F` builds. `StateSnapshot` carries no field
for either yet, so this screen has nothing to render honestly -- it says so
rather than showing an empty table, the same "not attached" discipline
`EPIC-005` §2's D1 exists to enforce applied to a missing data source
instead of a missing connection."""

from __future__ import annotations

from PySide6.QtCore import Property, Signal

from sagittarius_engine.extensions.pyside_mvc import BaseQmlViewModel
from tools.state_console.presentation.overview.overview_view_model import (
    NOT_ATTACHED,
)


class SignalsViewModel(BaseQmlViewModel):
    connectionStateChanged = Signal()
    detachReasonChanged = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._connection_state = NOT_ATTACHED
        self._detach_reason = ""

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
