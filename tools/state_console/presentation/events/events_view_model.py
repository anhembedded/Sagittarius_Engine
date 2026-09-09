"""`EventsViewModel` — `EPIC-007E` §3, "Events & wiring": the declared ⋈
subscribed join `EventCollector` (`EPIC-007A`/`C`) already computes.

`EPIC-008B` subtask C adds nothing new to this class's own shape (still
just `events`, a list of row dicts) — the restyle (sub-tabs, the WIRING BUG
banner, sortable columns, undeclared-row tinting) is all `EventsScreen.qml`
computing from data `EventsPresenter` already puts in each row (`handlers`,
`declaration`, `nearMatch`)."""

from __future__ import annotations

from PySide6.QtCore import Property, Signal

from sagittarius_engine.extensions.pyside_mvc import BaseQmlViewModel
from tools.state_console.presentation.overview.overview_view_model import (
    NOT_ATTACHED,
)


class EventsViewModel(BaseQmlViewModel):
    connectionStateChanged = Signal()
    detachReasonChanged = Signal()
    eventsChanged = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._connection_state = NOT_ATTACHED
        self._detach_reason = ""
        self._events: list[dict] = []

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

    def _get_events(self) -> list:
        return self._events

    events = Property("QVariantList", _get_events, notify=eventsChanged)  # type: ignore[arg-type]

    def set_events(self, events: list[dict]) -> None:
        self._events = events
        self.eventsChanged.emit()
