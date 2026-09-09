"""`ConnectionBandViewModel` — `EPIC-008B` §2.

Data only, no application logic — `ShellPresenter` owns every decision (the
6-state machine, the copy per state, the age ticking); this class exposes
state as Qt Properties/Signals and forwards the two user actions
(`LiveConnectionBand`'s `actionRequested`/`changeTargetRequested`) as Signals
for the Presenter to connect to, the same division of labour
`RosterViewModel`'s own docstring states.
"""

from __future__ import annotations

from PySide6.QtCore import Property, Signal, Slot

from sagittarius_engine.extensions.pyside_mvc import BaseQmlViewModel


class ConnectionBandViewModel(BaseQmlViewModel):
    stateChanged = Signal()
    stateLabelChanged = Signal()
    stateNoteChanged = Signal()
    ageLabelChanged = Signal()
    ageValueChanged = Signal()
    targetTextChanged = Signal()
    actionLabelChanged = Signal()
    heartbeatTicksChanged = Signal()

    actionRequested = Signal()
    changeTargetRequested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._state = "cold"
        self._state_label = ""
        self._state_note = ""
        self._age_label = ""
        self._age_value = ""
        self._target_text = ""
        self._action_label = ""
        self._heartbeat_ticks: list[float] = []

    def _get_state(self) -> str:
        return self._state

    def set_state(self, value: str) -> None:
        if value != self._state:
            self._state = value
            self.stateChanged.emit()

    state = Property(str, _get_state, notify=stateChanged)

    def _get_state_label(self) -> str:
        return self._state_label

    def set_state_label(self, value: str) -> None:
        if value != self._state_label:
            self._state_label = value
            self.stateLabelChanged.emit()

    stateLabel = Property(str, _get_state_label, notify=stateLabelChanged)

    def _get_state_note(self) -> str:
        return self._state_note

    def set_state_note(self, value: str) -> None:
        if value != self._state_note:
            self._state_note = value
            self.stateNoteChanged.emit()

    stateNote = Property(str, _get_state_note, notify=stateNoteChanged)

    def _get_age_label(self) -> str:
        return self._age_label

    def set_age_label(self, value: str) -> None:
        if value != self._age_label:
            self._age_label = value
            self.ageLabelChanged.emit()

    ageLabel = Property(str, _get_age_label, notify=ageLabelChanged)

    def _get_age_value(self) -> str:
        return self._age_value

    def set_age_value(self, value: str) -> None:
        if value != self._age_value:
            self._age_value = value
            self.ageValueChanged.emit()

    ageValue = Property(str, _get_age_value, notify=ageValueChanged)

    def _get_target_text(self) -> str:
        return self._target_text

    def set_target_text(self, value: str) -> None:
        if value != self._target_text:
            self._target_text = value
            self.targetTextChanged.emit()

    targetText = Property(str, _get_target_text, notify=targetTextChanged)

    def _get_action_label(self) -> str:
        return self._action_label

    def set_action_label(self, value: str) -> None:
        if value != self._action_label:
            self._action_label = value
            self.actionLabelChanged.emit()

    actionLabel = Property(str, _get_action_label, notify=actionLabelChanged)

    def _get_heartbeat_ticks(self) -> list:
        return self._heartbeat_ticks

    # "QVariantList" -- same idiom OverviewViewModel.threadPools already uses.
    heartbeatTicks = Property(
        "QVariantList",  # type: ignore[arg-type]
        _get_heartbeat_ticks,
        notify=heartbeatTicksChanged,
    )

    def set_heartbeat_ticks(self, ticks: list[float]) -> None:
        self._heartbeat_ticks = ticks
        self.heartbeatTicksChanged.emit()

    @Slot()
    def requestAction(self) -> None:
        self.actionRequested.emit()

    @Slot()
    def requestChangeTarget(self) -> None:
        self.changeTargetRequested.emit()
