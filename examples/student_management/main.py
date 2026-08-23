import argparse
import sys
from pathlib import Path

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
from examples.student_management.infrastructure.persistence.extension import (
    StudentManagementExtension,
)
from sagittarius_engine.extensions.logger.logger_module import LoggerExtension
from sagittarius_engine.extensions.persistence.database_module import DatabaseExtension
from sagittarius_engine.extensions.persistence.transaction_middleware import (
    TransactionMiddleware,
)
from sagittarius_engine.infrastructure.config.config_manager import ConfigManager
from sagittarius_engine.infrastructure.container.std_container import StdLibContainer
from sagittarius_engine.infrastructure.event_bus.memory_event_bus import MemoryEventBus
from sagittarius_engine.interfaces import IConfig, IEventBus
from sagittarius_engine.kernel import App
from sagittarius_engine.middleware.logging_middleware import LoggingMiddleware

PACKAGE_DIR = Path(__file__).resolve().parent
DEFAULT_DB_PATH = PACKAGE_DIR / "data" / "student_management.db"


def build_app(db_url: str | None = None) -> App:
    """
    @brief Wires and boots the app. See docs/bootstrap.md and
    docs/module_registration.md for why things happen in this exact order.
    """
    config = ConfigManager().load_json(str(PACKAGE_DIR / "config.json"))
    config.load_env(prefix="STUDENT_MGMT_")
    # database.url is computed here, not left in config.json: a relative path
    # in a static JSON file resolves against the process's CWD, not this
    # package's own location. See docs/config_loading.md.
    config.set("database.url", db_url or f"sqlite:///{DEFAULT_DB_PATH}")

    container = StdLibContainer()
    event_bus = MemoryEventBus()
    # App(container, event_bus) does NOT register either into the container —
    # only `app.event_bus`/context.event_bus reach them. Extensions and
    # handlers that need to `container.resolve(IEventBus)` /
    # `container.resolve(IConfig)` need these two lines. See docs/bootstrap.md.
    container.singleton(IConfig, config)
    container.singleton(IEventBus, event_bus)

    app = App(container, event_bus)
    # Order matters and is not declaratively enforced anywhere: DatabaseExtension
    # must register ISession before StudentManagementExtension resolves it.
    # See docs/module_registration.md.
    app.use(LoggerExtension())
    app.use(DatabaseExtension())
    app.use(StudentManagementExtension())
    # Outermost-first: Logging should see the whole operation (including
    # commit/rollback), Transaction should wrap only the handler itself.
    app.use_middleware(LoggingMiddleware(container))
    app.use_middleware(TransactionMiddleware(container))
    app.boot()
    return app


def _print_student(student) -> None:
    print(
        f"{student.id.value}  {student.full_name:<24} {student.email.value:<28} "
        f"{student.major:<12} GPA {student.gpa}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="student_management")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("enroll")
    p.add_argument("full_name")
    p.add_argument("email")
    p.add_argument("major")
    p.add_argument("gpa", type=float)

    p = sub.add_parser("update")
    p.add_argument("student_id")
    p.add_argument("--full-name")
    p.add_argument("--email")
    p.add_argument("--major")
    p.add_argument("--gpa", type=float)

    p = sub.add_parser("remove")
    p.add_argument("student_id")

    p = sub.add_parser("get")
    p.add_argument("student_id")

    sub.add_parser("list")

    p = sub.add_parser("search")
    p.add_argument("name_contains")

    sub.add_parser("report")

    args = parser.parse_args(argv)
    app = build_app()
    try:
        if args.command == "enroll":
            student = app.dispatch(
                EnrollStudentHandler,
                EnrollStudentCommand(args.full_name, args.email, args.major, args.gpa),
            )
            _print_student(student)
        elif args.command == "update":
            student = app.dispatch(
                UpdateStudentHandler,
                UpdateStudentCommand(
                    args.student_id, args.full_name, args.email, args.major, args.gpa
                ),
            )
            _print_student(student)
        elif args.command == "remove":
            app.dispatch(RemoveStudentHandler, RemoveStudentCommand(args.student_id))
            print(f"Removed {args.student_id}")
        elif args.command == "get":
            student = app.dispatch(GetStudentHandler, GetStudentQuery(args.student_id))
            _print_student(student)
        elif args.command == "list":
            for student in app.dispatch(ListStudentsHandler, ListStudentsQuery()):
                _print_student(student)
        elif args.command == "search":
            for student in app.dispatch(
                SearchStudentsHandler, SearchStudentsQuery(args.name_contains)
            ):
                _print_student(student)
        elif args.command == "report":
            report = app.dispatch(
                GenerateRosterReportHandler, GenerateRosterReportQuery()
            )
            print(f"Total students: {report.total_students}")
            print(f"Average GPA:    {report.average_gpa}")
            print(f"By major:       {report.students_by_major}")
    except StudentNotFoundError as e:
        print(f"Student not found: {e}", file=sys.stderr)
        return 1
    finally:
        app.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
