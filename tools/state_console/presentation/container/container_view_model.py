"""`ContainerViewModel` — `EPIC-007E` §3, "Container": registrations,
lifetimes, what is built, unbound dependencies, cycles.

@details Unbound dependencies and cycles are `WiringInspector` C1-C3/cycle
findings, not part of `ContainerState` (`EPIC-007A`) — `StateSnapshot` has
no `findings` collector wired yet (`EPIC-007C`'s own documented gap). This
screen shows what the snapshot actually carries: registrations, lifetimes,
and instantiation state.
"""

from __future__ import annotations

from PySide6.QtCore import Property, Signal

from sagittarius_engine.extensions.pyside_mvc import BaseQmlViewModel
from tools.state_console.presentation.overview.overview_view_model import (
    NOT_ATTACHED,
)


class ContainerViewModel(BaseQmlViewModel):
    connectionStateChanged = Signal()
    detachReasonChanged = Signal()
    registrationsChanged = Signal()
    openScopesChanged = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._connection_state = NOT_ATTACHED
        self._detach_reason = ""
        self._registrations: list[dict] = []
        self._open_scopes = 0

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

    def _get_registrations(self) -> list:
        return self._registrations

    registrations = Property(
        "QVariantList",  # type: ignore[arg-type]
        _get_registrations,
        notify=registrationsChanged,
    )

    def _get_open_scopes(self) -> int:
        return self._open_scopes

    openScopes = Property(int, _get_open_scopes, notify=openScopesChanged)

    def set_container_state(self, registrations: list[dict], open_scopes: int) -> None:
        self._registrations = registrations
        self._open_scopes = open_scopes
        self.registrationsChanged.emit()
        self.openScopesChanged.emit()
