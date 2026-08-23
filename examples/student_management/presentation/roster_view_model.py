from PySide6.QtCore import Property, Signal, Slot

from sagittarius_engine.extensions.pyside_mvc import BaseQmlViewModel


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

    enrollRequested = Signal(str, str, str, float)
    removeRequested = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._students: list[dict] = []
        self._total_students = 0
        self._average_gpa = 0.0
        self._compact_mode = False

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

    def set_students(self, students: list[dict]) -> None:
        self._students = students
        self.studentsChanged.emit()

    def set_stats(self, total_students: int, average_gpa: float) -> None:
        self._total_students = total_students
        self._average_gpa = average_gpa
        self.statsChanged.emit()

    @Slot(str, str, str, float)
    def requestEnroll(self, full_name: str, email: str, major: str, gpa: float) -> None:
        self.enrollRequested.emit(full_name, email, major, gpa)

    @Slot(str)
    def requestRemove(self, student_id: str) -> None:
        self.removeRequested.emit(student_id)
