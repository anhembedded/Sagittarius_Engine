"""`OverviewViewModel` — `EPIC-007E` §3, the Overview screen combined with
§4's not-attached state.

Data only, no application logic — `OverviewPresenter` owns every decision;
this class exposes state as Qt Properties/Signals, the same division of
labour `RosterViewModel`'s own docstring states.
"""

from __future__ import annotations

from PySide6.QtCore import Property, Signal

from sagittarius_engine.extensions.pyside_mvc import BaseQmlViewModel

#: EPIC-007E §4's three states, as QML-bindable strings.
NOT_ATTACHED = "not_attached"
ATTACHED_IDLE = "attached_idle"
ATTACHED_READING = "attached_reading"


class OverviewViewModel(BaseQmlViewModel):
    connectionStateChanged = Signal()
    detachReasonChanged = Signal()
    lifecycleChanged = Signal()
    threadPoolsChanged = Signal()
    snapshotAgeSecondsChanged = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._connection_state = NOT_ATTACHED
        self._detach_reason = ""
        self._lifecycle_state = ""
        self._extensions_registered = 0
        self._extensions_initialized = 0
        self._thread_pools: list[dict] = []
        self._snapshot_age_seconds = -1.0

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

    def _get_lifecycle_state(self) -> str:
        return self._lifecycle_state

    lifecycleState = Property(str, _get_lifecycle_state, notify=lifecycleChanged)

    def _get_extensions_registered(self) -> int:
        return self._extensions_registered

    extensionsRegistered = Property(
        int, _get_extensions_registered, notify=lifecycleChanged
    )

    def _get_extensions_initialized(self) -> int:
        return self._extensions_initialized

    extensionsInitialized = Property(
        int, _get_extensions_initialized, notify=lifecycleChanged
    )

    def set_lifecycle(self, state: str, registered: int, initialized: int) -> None:
        self._lifecycle_state = state
        self._extensions_registered = registered
        self._extensions_initialized = initialized
        self.lifecycleChanged.emit()

    def _get_thread_pools(self) -> list:
        return self._thread_pools

    # "QVariantList" -- PySide6's own idiom for exposing a Python list to
    # QML, same as RosterViewModel.students.
    threadPools = Property("QVariantList", _get_thread_pools, notify=threadPoolsChanged)  # type: ignore[arg-type]

    def set_thread_pools(self, pools: list[dict]) -> None:
        self._thread_pools = pools
        self.threadPoolsChanged.emit()

    def _get_snapshot_age_seconds(self) -> float:
        return self._snapshot_age_seconds

    snapshotAgeSeconds = Property(
        float, _get_snapshot_age_seconds, notify=snapshotAgeSecondsChanged
    )

    def set_snapshot_age_seconds(self, value: float) -> None:
        self._snapshot_age_seconds = value
        self.snapshotAgeSecondsChanged.emit()
