from PySide6.QtCore import Property, QObject, Signal, Slot

from sagittarius_engine.extensions.pyside_mvc import BaseQmlViewModel, LogListModel


class RosterViewModel(BaseQmlViewModel):
    """
    @brief QML-facing surface for the roster screen — data only, no
    application logic. RosterPresenter owns every decision; this class
    just exposes state as Qt Properties/Signals and forwards user actions
    as Signals for the Presenter to connect to (BasePresenter's
    "connect view signals to presenter slots" contract).
    """

    studentsChanged = Signal()
    statsChanged = Signal()
    compactModeChanged = Signal()
    dateFilterChanged = Signal()
    autoScrollLogChanged = Signal()

    enrollRequested = Signal(str, str, str, float)
    removeRequested = Signal(str)
    #: Emitted whenever TimeRangeCard reports a change (toggle or either
    #: date field edited) — the Presenter decides whether/how to re-query,
    #: then calls set_date_filter() to reflect the accepted state back.
    dateFilterRequested = Signal(bool, str, str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._students: list[dict] = []
        self._total_students = 0
        self._average_gpa = 0.0
        self._compact_mode = False
        self._use_custom_time = False
        self._from_date_time = ""
        self._to_date_time = ""
        self._auto_scroll_log = True
        self._log_model = LogListModel(self)

    def _get_students(self) -> list:
        return self._students

    # "QVariantList" (a string, not a type) is PySide6's own idiom for
    # exposing a Python list to QML — correct at runtime, but mypy's PySide6
    # stubs only accept a real `type` here.
    students = Property("QVariantList", _get_students, notify=studentsChanged)  # type: ignore[arg-type]

    def _get_total_students(self) -> int:
        return self._total_students

    totalStudents = Property(int, _get_total_students, notify=statsChanged)

    def _get_average_gpa(self) -> float:
        return self._average_gpa

    averageGpa = Property(float, _get_average_gpa, notify=statsChanged)

    def _get_compact_mode(self) -> bool:
        return self._compact_mode

    def _set_compact_mode(self, value: bool) -> None:
        if value != self._compact_mode:
            self._compact_mode = value
            self.compactModeChanged.emit()

    compactMode = Property(
        bool, _get_compact_mode, _set_compact_mode, notify=compactModeChanged
    )

    def _get_use_custom_time(self) -> bool:
        return self._use_custom_time

    useCustomTime = Property(bool, _get_use_custom_time, notify=dateFilterChanged)

    def _get_from_date_time(self) -> str:
        return self._from_date_time

    fromDateTime = Property(str, _get_from_date_time, notify=dateFilterChanged)

    def _get_to_date_time(self) -> str:
        return self._to_date_time

    toDateTime = Property(str, _get_to_date_time, notify=dateFilterChanged)

    def _get_auto_scroll_log(self) -> bool:
        return self._auto_scroll_log

    def _set_auto_scroll_log(self, value: bool) -> None:
        if value != self._auto_scroll_log:
            self._auto_scroll_log = value
            self.autoScrollLogChanged.emit()

    autoScrollLog = Property(
        bool, _get_auto_scroll_log, _set_auto_scroll_log, notify=autoScrollLogChanged
    )

    def _get_log_model(self) -> QObject:
        return self._log_model

    # Constant: the model instance itself never changes, only its rows
    # (which it signals internally via QAbstractListModel's own
    # begin/endInsertRows) — matches LogPanel.qml's own usage docstring.
    logModel = Property(QObject, _get_log_model, constant=True)

    def set_students(self, students: list[dict]) -> None:
        self._students = students
        self.studentsChanged.emit()

    def set_stats(self, total_students: int, average_gpa: float) -> None:
        self._total_students = total_students
        self._average_gpa = average_gpa
        self.statsChanged.emit()

    def set_date_filter(
        self, use_custom_time: bool, from_date_time: str, to_date_time: str
    ) -> None:
        self._use_custom_time = use_custom_time
        self._from_date_time = from_date_time
        self._to_date_time = to_date_time
        self.dateFilterChanged.emit()

    def log(self, message: str, level: str = "info") -> None:
        self._log_model.append(message, level)

    @Slot(str, str, str, float)
    def requestEnroll(self, full_name: str, email: str, major: str, gpa: float) -> None:
        self.enrollRequested.emit(full_name, email, major, gpa)

    @Slot(str)
    def requestRemove(self, student_id: str) -> None:
        self.removeRequested.emit(student_id)

    @Slot(bool)
    def setUseCustomTime(self, value: bool) -> None:
        self.dateFilterRequested.emit(value, self._from_date_time, self._to_date_time)

    @Slot(str)
    def setFromDateTime(self, value: str) -> None:
        self.dateFilterRequested.emit(self._use_custom_time, value, self._to_date_time)

    @Slot(str)
    def setToDateTime(self, value: str) -> None:
        self.dateFilterRequested.emit(
            self._use_custom_time, self._from_date_time, value
        )
