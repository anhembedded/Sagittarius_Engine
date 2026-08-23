from datetime import datetime

import pytest

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
from examples.student_management.application.use_cases.get_student.command import (
    GetStudentQuery,
)
from examples.student_management.application.use_cases.get_student.handler import (
    GetStudentHandler,
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
from examples.student_management.application.use_cases.search_students.command import (
    SearchStudentsQuery,
)
from examples.student_management.application.use_cases.search_students.handler import (
    SearchStudentsHandler,
)
from examples.student_management.application.use_cases.update_student.command import (
    UpdateStudentCommand,
)
from examples.student_management.application.use_cases.update_student.handler import (
    UpdateStudentHandler,
)
from examples.student_management.domain.events import (
    StudentEnrolled,
    StudentRemoved,
    StudentUpdated,
)
from examples.student_management.domain.student import Email, Student
from examples.student_management.tests.application.fake_repository import (
    FakeStudentRepository,
)
from sagittarius_engine.infrastructure.event_bus.memory_event_bus import MemoryEventBus


@pytest.fixture
def repo() -> FakeStudentRepository:
    return FakeStudentRepository()


@pytest.fixture
def event_bus() -> MemoryEventBus:
    return MemoryEventBus()


def test_enroll_student_adds_and_emits_event(repo, event_bus):
    received = []
    event_bus.on(StudentEnrolled, received.append)

    handler = EnrollStudentHandler(repo, event_bus)
    student = handler.execute(
        EnrollStudentCommand(
            full_name="Alice Nguyen", email="alice@example.com", major="CS", gpa=3.7
        )
    )

    assert repo.get(student.id) is student
    assert len(received) == 1
    assert received[0].student_id == student.id.value


def test_update_student_changes_fields_and_emits_event(repo, event_bus):
    student = EnrollStudentHandler(repo, event_bus).execute(
        EnrollStudentCommand(
            full_name="Bob Tran", email="bob@example.com", major="Math", gpa=3.0
        )
    )
    received = []
    event_bus.on(StudentUpdated, received.append)

    updated = UpdateStudentHandler(repo, event_bus).execute(
        UpdateStudentCommand(student_id=student.id.value, gpa=3.5)
    )

    assert updated.gpa == 3.5
    assert updated.full_name == "Bob Tran"
    assert received[0].changed_fields == ("gpa",)


def test_update_student_raises_when_missing(repo, event_bus):
    with pytest.raises(StudentNotFoundError):
        UpdateStudentHandler(repo, event_bus).execute(
            UpdateStudentCommand(student_id="does-not-exist", gpa=3.5)
        )


def test_remove_student_deletes_and_emits_event(repo, event_bus):
    student = EnrollStudentHandler(repo, event_bus).execute(
        EnrollStudentCommand(
            full_name="Cara Le", email="cara@example.com", major="CS", gpa=3.2
        )
    )
    received = []
    event_bus.on(StudentRemoved, received.append)

    RemoveStudentHandler(repo, event_bus).execute(
        RemoveStudentCommand(student_id=student.id.value)
    )

    assert repo.get(student.id) is None
    assert received[0].student_id == student.id.value


def test_remove_student_raises_when_missing(repo, event_bus):
    with pytest.raises(StudentNotFoundError):
        RemoveStudentHandler(repo, event_bus).execute(
            RemoveStudentCommand(student_id="does-not-exist")
        )


def test_get_student_raises_when_missing(repo):
    with pytest.raises(StudentNotFoundError):
        GetStudentHandler(repo).execute(GetStudentQuery(student_id="does-not-exist"))


def test_list_students_returns_all(repo, event_bus):
    EnrollStudentHandler(repo, event_bus).execute(
        EnrollStudentCommand(full_name="A", email="a@x.com", major="CS", gpa=3.0)
    )
    EnrollStudentHandler(repo, event_bus).execute(
        EnrollStudentCommand(full_name="B", email="b@x.com", major="Math", gpa=3.5)
    )

    result = ListStudentsHandler(repo).execute(ListStudentsQuery())

    assert len(result) == 2


def test_list_students_by_enrollment_date_filters_inclusive_range(repo):
    early = Student.enroll("Early", Email("early@x.com"), "CS", 3.0)
    early.enrolled_at = datetime(2026, 1, 1)
    mid = Student.enroll("Mid", Email("mid@x.com"), "CS", 3.0)
    mid.enrolled_at = datetime(2026, 6, 1)
    late = Student.enroll("Late", Email("late@x.com"), "CS", 3.0)
    late.enrolled_at = datetime(2026, 12, 1)
    for s in (early, mid, late):
        repo.add(s)

    result = ListStudentsByEnrollmentDateHandler(repo).execute(
        ListStudentsByEnrollmentDateQuery(
            from_dt=datetime(2026, 2, 1), to_dt=datetime(2026, 7, 1)
        )
    )

    assert [s.full_name for s in result] == ["Mid"]


def test_list_students_by_enrollment_date_open_ended_bounds(repo):
    early = Student.enroll("Early", Email("early@x.com"), "CS", 3.0)
    early.enrolled_at = datetime(2026, 1, 1)
    late = Student.enroll("Late", Email("late@x.com"), "CS", 3.0)
    late.enrolled_at = datetime(2026, 12, 1)
    repo.add(early)
    repo.add(late)

    only_after_june = ListStudentsByEnrollmentDateHandler(repo).execute(
        ListStudentsByEnrollmentDateQuery(from_dt=datetime(2026, 6, 1), to_dt=None)
    )
    assert [s.full_name for s in only_after_june] == ["Late"]

    no_bounds = ListStudentsByEnrollmentDateHandler(repo).execute(
        ListStudentsByEnrollmentDateQuery(from_dt=None, to_dt=None)
    )
    assert len(no_bounds) == 2


def test_search_students_by_name_is_case_insensitive(repo, event_bus):
    EnrollStudentHandler(repo, event_bus).execute(
        EnrollStudentCommand(
            full_name="Alice Nguyen", email="a@x.com", major="CS", gpa=3.0
        )
    )
    EnrollStudentHandler(repo, event_bus).execute(
        EnrollStudentCommand(
            full_name="Bob Tran", email="b@x.com", major="Math", gpa=3.5
        )
    )

    result = SearchStudentsHandler(repo).execute(
        SearchStudentsQuery(name_contains="alice")
    )

    assert len(result) == 1
    assert result[0].full_name == "Alice Nguyen"


def test_generate_roster_report_computes_stats(repo, event_bus):
    EnrollStudentHandler(repo, event_bus).execute(
        EnrollStudentCommand(full_name="A", email="a@x.com", major="CS", gpa=3.0)
    )
    EnrollStudentHandler(repo, event_bus).execute(
        EnrollStudentCommand(full_name="B", email="b@x.com", major="CS", gpa=4.0)
    )
    EnrollStudentHandler(repo, event_bus).execute(
        EnrollStudentCommand(full_name="C", email="c@x.com", major="Math", gpa=3.5)
    )

    report = GenerateRosterReportHandler(repo).execute(GenerateRosterReportQuery())

    assert report.total_students == 3
    assert report.average_gpa == pytest.approx((3.0 + 4.0 + 3.5) / 3)
    assert report.students_by_major == {"CS": 2, "Math": 1}


def test_generate_roster_report_handles_empty_roster(repo):
    report = GenerateRosterReportHandler(repo).execute(GenerateRosterReportQuery())

    assert report.total_students == 0
    assert report.average_gpa == 0.0
    assert report.students_by_major == {}
