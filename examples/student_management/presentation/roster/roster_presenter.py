from datetime import datetime

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
from examples.student_management.application.use_cases.list_students_by_enrollment_date.command import (
    ListStudentsByEnrollmentDateQuery,
)
from examples.student_management.application.use_cases.list_students_by_enrollment_date.handler import (
    ListStudentsByEnrollmentDateHandler,
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
from examples.student_management.domain.student import Student
from examples.student_management.presentation.roster.roster_view_model import (
    RosterViewModel,
)
from sagittarius_engine.extensions.pyside_mvc import BasePresenter
from sagittarius_engine.interfaces.i_container import IContainer

#: Matches DateTimePicker.qml's own placeholder ("yyyy-MM-dd HH:mm"), which
#: TimeRangeCard sets on both of its nested pickers.
_DATE_TIME_FORMAT = "%Y-%m-%d %H:%M"


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
    exercised for coverage's sake. The same events also feed the Activity
    Log panel (LogPanel) — the log is not a separate write path, it is a
    second subscriber to events the roster refresh already relies on.

    The date-range filter (TimeRangeCard) affects only which rows the
    table shows; the stats card always summarizes the whole roster, not
    the filtered view — two different questions ("how many rows can I
    see right now" vs "how is the roster doing overall").
    """

    def __init__(self, view, container: IContainer) -> None:
        super().__init__(view, container)
        self.view_model = RosterViewModel()
        # IView.bind() -- view may be a RosterView (QML) or a
        # WidgetRosterView (QWidget, TASK-037); this presenter has no
        # opinion on which.
        self.view.bind(self.view_model)

        self._connect_ui_signals()
        self._connect_engine_events()
        self.refresh()

    def _connect_ui_signals(self) -> None:
        self.view_model.enrollRequested.connect(self._on_enroll_requested)
        self.view_model.removeRequested.connect(self._on_remove_requested)
        self.view_model.dateFilterRequested.connect(self._on_date_filter_requested)

    def _connect_engine_events(self) -> None:
        self.event_bus.on(StudentEnrolled, self._on_student_enrolled)
        self.event_bus.on(StudentUpdated, self._on_student_updated)
        self.event_bus.on(StudentRemoved, self._on_student_removed)

    def _on_student_enrolled(self, event: StudentEnrolled) -> None:
        self.view_model.log(
            f"Enrolled {event.full_name} ({event.student_id})", "success"
        )
        self.refresh()

    def _on_student_updated(self, event: StudentUpdated) -> None:
        fields = ", ".join(event.changed_fields) or "no fields"
        self.view_model.log(f"Updated {event.student_id}: {fields}", "info")
        self.refresh()

    def _on_student_removed(self, event: StudentRemoved) -> None:
        self.view_model.log(f"Removed {event.student_id}", "error")
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
            self.dispatcher.dispatch(
                RemoveStudentHandler, RemoveStudentCommand(student_id)
            )
        except StudentNotFoundError as e:
            self.logger.error(f"Remove failed: {e}")

    def _parse_date_time(self, text: str) -> datetime | None:
        text = text.strip()
        if not text:
            return None
        try:
            return datetime.strptime(text, _DATE_TIME_FORMAT)
        except ValueError:
            self.logger.error(
                f"Invalid date/time (expected {_DATE_TIME_FORMAT!r}): {text!r}"
            )
            return None

    def _on_date_filter_requested(
        self, use_custom_time: bool, from_text: str, to_text: str
    ) -> None:
        self.view_model.set_date_filter(use_custom_time, from_text, to_text)
        self._refresh_rows()

    def _fetch_rows_for_current_filter(self) -> list[Student]:
        """@brief Table rows respect whichever filter is currently active on
        the ViewModel — used both when the filter itself changes and when a
        domain event (enroll/update/remove) triggers a refresh, so enrolling
        a student while a date filter is active does not silently discard
        that filter."""
        if not self.view_model.useCustomTime:
            return self.dispatcher.dispatch(ListStudentsHandler, ListStudentsQuery())

        from_dt = self._parse_date_time(self.view_model.fromDateTime)
        to_dt = self._parse_date_time(self.view_model.toDateTime)
        return self.dispatcher.dispatch(
            ListStudentsByEnrollmentDateHandler,
            ListStudentsByEnrollmentDateQuery(from_dt, to_dt),
        )

    @staticmethod
    def _to_rows(students: list[Student]) -> list[dict]:
        return [
            {
                "id": s.id.value,
                "fullName": s.full_name,
                "email": s.email.value,
                "major": s.major,
                "gpa": s.gpa,
                "enrolledAt": s.enrolled_at.strftime(_DATE_TIME_FORMAT),
            }
            for s in students
        ]

    def _refresh_rows(self) -> None:
        self.view_model.set_students(
            self._to_rows(self._fetch_rows_for_current_filter())
        )

    def refresh(self) -> None:
        self._refresh_rows()

        # Stats always summarize the whole roster, independent of the table's
        # active date filter — see class docstring.
        report = self.dispatcher.dispatch(
            GenerateRosterReportHandler, GenerateRosterReportQuery()
        )
        self.view_model.set_stats(report.total_students, report.average_gpa)
