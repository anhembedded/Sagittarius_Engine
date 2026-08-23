from examples.student_management.application.exceptions import StudentNotFoundError
from examples.student_management.application.use_cases.enroll_student.command import (
    EnrollStudentCommand,
)
from examples.student_management.application.use_cases.enroll_student.handler import (
    EnrollStudentHandler,
)
from examples.student_management.application.use_cases.generate_roster_report.command import (
    GenerateRosterReportQuery,
)
from examples.student_management.application.use_cases.generate_roster_report.handler import (
    GenerateRosterReportHandler,
)
from examples.student_management.application.use_cases.list_students.command import (
    ListStudentsQuery,
)
from examples.student_management.application.use_cases.list_students.handler import (
    ListStudentsHandler,
)
from examples.student_management.application.use_cases.remove_student.command import (
    RemoveStudentCommand,
)
from examples.student_management.application.use_cases.remove_student.handler import (
    RemoveStudentHandler,
)
from examples.student_management.domain.events import (
    StudentEnrolled,
    StudentRemoved,
    StudentUpdated,
)
from examples.student_management.presentation.roster_view_model import RosterViewModel
from sagittarius_engine.extensions.pyside_mvc import BasePresenter
from sagittarius_engine.interfaces.i_container import IContainer


class RosterPresenter(BasePresenter):
    """
    @brief Wires RosterView/RosterViewModel to the application layer.

    @details No FSM (INITIAL_STATE left None, per BasePresenter's own
    opt-in design) — a roster screen with no lifecycle states to
    transition between has no honest use for one. See
    MODULE_COVERAGE.md's `fsm` row for the same reasoning.

    Refresh is event-driven, not called manually after every dispatch: a
    successful enroll/update/remove emits a domain event, and this
    presenter refreshes the whole roster in response — real use of the
    event bus to decouple "data changed" from "who changed it," not
    exercised for coverage's sake.
    """

    def __init__(self, view, container: IContainer) -> None:
        super().__init__(view, container)
        self.view_model = RosterViewModel()
        self.view.set_view_model(self.view_model)
        self.view.load_qml("RosterScreen.qml")

        self._connect_ui_signals()
        self._connect_engine_events()
        self.refresh()

    def _connect_ui_signals(self) -> None:
        self.view_model.enrollRequested.connect(self._on_enroll_requested)
        self.view_model.removeRequested.connect(self._on_remove_requested)

    def _connect_engine_events(self) -> None:
        self.event_bus.on(StudentEnrolled, self._on_roster_changed)
        self.event_bus.on(StudentUpdated, self._on_roster_changed)
        self.event_bus.on(StudentRemoved, self._on_roster_changed)

    def _on_roster_changed(self, _event) -> None:
        self.refresh()

    def _on_enroll_requested(
        self, full_name: str, email: str, major: str, gpa: float
    ) -> None:
        try:
            self.dispatcher.dispatch(
                EnrollStudentHandler, EnrollStudentCommand(full_name, email, major, gpa)
            )
        except ValueError as e:
            self.logger.error(f"Enroll failed: {e}")

    def _on_remove_requested(self, student_id: str) -> None:
        try:
            self.dispatcher.dispatch(RemoveStudentHandler, RemoveStudentCommand(student_id))
        except StudentNotFoundError as e:
            self.logger.error(f"Remove failed: {e}")

    def refresh(self) -> None:
        students = self.dispatcher.dispatch(ListStudentsHandler, ListStudentsQuery())
        rows = [
            {
                "id": s.id.value,
                "fullName": s.full_name,
                "email": s.email.value,
                "major": s.major,
                "gpa": s.gpa,
            }
            for s in students
        ]
        self.view_model.set_students(rows)

        report = self.dispatcher.dispatch(
            GenerateRosterReportHandler, GenerateRosterReportQuery()
        )
        self.view_model.set_stats(report.total_students, report.average_gpa)
