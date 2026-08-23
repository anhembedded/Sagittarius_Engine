import tempfile
from pathlib import Path

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
from examples.student_management.application.use_cases.remove_student.command import (
    RemoveStudentCommand,
)
from examples.student_management.application.use_cases.remove_student.handler import (
    RemoveStudentHandler,
)
from examples.student_management.application.use_cases.update_student.command import (
    UpdateStudentCommand,
)
from examples.student_management.application.use_cases.update_student.handler import (
    UpdateStudentHandler,
)
from examples.student_management.main import build_app


@pytest.fixture
def app():
    """
    A real App: StdLibContainer, MemoryEventBus, LoggerExtension,
    DatabaseExtension, StudentManagementExtension, both middlewares — the
    exact same stack main.py's CLI boots, against a throwaway file-based
    SQLite database (see extension.py's docstring for why not ':memory:').
    """
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "test.db"
        application = build_app(db_url=f"sqlite:///{db_path}")
        yield application
        application.stop()


def test_full_stack_enroll_then_get(app):
    student = app.dispatch(
        EnrollStudentHandler,
        EnrollStudentCommand("Alice Nguyen", "alice@example.com", "CS", 3.7),
    )

    fetched = app.dispatch(GetStudentHandler, GetStudentQuery(student.id.value))

    assert fetched.full_name == "Alice Nguyen"
    assert fetched.gpa == 3.7


def test_full_stack_transaction_commits_on_success(app):
    """The TransactionMiddleware must actually commit — a second dispatch,
    which resolves its own session query, must see data added earlier."""
    app.dispatch(
        EnrollStudentHandler,
        EnrollStudentCommand("Bob Tran", "bob@example.com", "Math", 3.0),
    )

    report = app.dispatch(GenerateRosterReportHandler, GenerateRosterReportQuery())

    assert report.total_students == 1


def test_full_stack_update_and_remove(app):
    student = app.dispatch(
        EnrollStudentHandler,
        EnrollStudentCommand("Cara Le", "cara@example.com", "CS", 3.2),
    )

    updated = app.dispatch(
        UpdateStudentHandler,
        UpdateStudentCommand(student.id.value, gpa=3.8),
    )
    assert updated.gpa == 3.8

    app.dispatch(RemoveStudentHandler, RemoveStudentCommand(student.id.value))

    with pytest.raises(StudentNotFoundError):
        app.dispatch(GetStudentHandler, GetStudentQuery(student.id.value))


def test_full_stack_get_missing_raises(app):
    with pytest.raises(StudentNotFoundError):
        app.dispatch(GetStudentHandler, GetStudentQuery("does-not-exist"))
