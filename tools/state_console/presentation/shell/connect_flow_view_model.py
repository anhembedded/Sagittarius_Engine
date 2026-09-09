"""`ConnectFlowViewModel` — `EPIC-008B` §3.

Data only, no application logic — `ShellPresenter` owns every decision
(when the flow opens, what `recents` holds, what happens on submit). QML
calls `requestConnect`/`requestCancel`, which only `.emit()` the
corresponding Signal, the same division of labour every other ViewModel in
this tool already follows.
"""

from __future__ import annotations

from PySide6.QtCore import Property, Signal, Slot

from sagittarius_engine.extensions.pyside_mvc import BaseQmlViewModel


class ConnectFlowViewModel(BaseQmlViewModel):
    changingTargetChanged = Signal()
    currentTargetChanged = Signal()
    recentsChanged = Signal()

    connectRequested = Signal(str)
    cancelRequested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._changing_target = False
        self._current_target = ""
        self._recents: list[dict] = []

    def _get_changing_target(self) -> bool:
        return self._changing_target

    def set_changing_target(self, value: bool) -> None:
        if value != self._changing_target:
            self._changing_target = value
            self.changingTargetChanged.emit()

    #: True when opened via the band's "change…" link while already
    #: attached (`reference/handoff.md` §5's "Currently attached to
    #: `<addr>`..." copy); False when opened cold, via "Attach…".
    changingTarget = Property(bool, _get_changing_target, notify=changingTargetChanged)

    def _get_current_target(self) -> str:
        return self._current_target

    def set_current_target(self, value: str) -> None:
        if value != self._current_target:
            self._current_target = value
            self.currentTargetChanged.emit()

    currentTarget = Property(str, _get_current_target, notify=currentTargetChanged)

    def _get_recents(self) -> list:
        return self._recents

    # "QVariantList" -- same idiom OverviewViewModel.threadPools already uses.
    recents = Property("QVariantList", _get_recents, notify=recentsChanged)  # type: ignore[arg-type]

    def set_recents(self, recents: list[dict]) -> None:
        self._recents = recents
        self.recentsChanged.emit()

    @Slot(str)
    def requestConnect(self, address: str) -> None:
        self.connectRequested.emit(address)

    @Slot()
    def requestCancel(self) -> None:
        self.cancelRequested.emit()
