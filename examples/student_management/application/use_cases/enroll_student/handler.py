from examples.student_management.application.ports.student_repository import (
    IStudentRepository,
)
from examples.student_management.application.use_cases.enroll_student.command import (
    EnrollStudentCommand,
)
from examples.student_management.domain.events import StudentEnrolled
from examples.student_management.domain.student import Email, Student
from sagittarius_engine.interfaces import IEventBus


class EnrollStudentHandler:
    def __init__(self, repo: IStudentRepository, event_bus: IEventBus) -> None:
        self._repo = repo
        self._event_bus = event_bus

    def execute(self, dto: EnrollStudentCommand) -> Student:
        student = Student.enroll(
            full_name=dto.full_name,
            email=Email(dto.email),
            major=dto.major,
            gpa=dto.gpa,
        )
        self._repo.add(student)
        self._event_bus.emit(
            StudentEnrolled(student_id=student.id.value, full_name=student.full_name)
        )
        return student
