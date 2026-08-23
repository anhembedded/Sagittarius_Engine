from examples.student_management.application.exceptions import StudentNotFoundError
from examples.student_management.application.ports.student_repository import (
    IStudentRepository,
)
from examples.student_management.application.use_cases.update_student.command import (
    UpdateStudentCommand,
)
from examples.student_management.domain.events import StudentUpdated
from examples.student_management.domain.student import Email, Student, StudentId
from sagittarius_engine.interfaces import IEventBus


class UpdateStudentHandler:
    def __init__(self, repo: IStudentRepository, event_bus: IEventBus) -> None:
        self._repo = repo
        self._event_bus = event_bus

    def execute(self, dto: UpdateStudentCommand) -> Student:
        student = self._repo.get(StudentId(dto.student_id))
        if student is None:
            raise StudentNotFoundError(dto.student_id)

        changed = [
            name
            for name, value in (
                ("full_name", dto.full_name),
                ("email", dto.email),
                ("major", dto.major),
                ("gpa", dto.gpa),
            )
            if value is not None
        ]
        updated = student.with_updates(
            full_name=dto.full_name,
            email=Email(dto.email) if dto.email is not None else None,
            major=dto.major,
            gpa=dto.gpa,
        )
        self._repo.update(updated)
        if changed:
            self._event_bus.emit(
                StudentUpdated(student_id=dto.student_id, changed_fields=tuple(changed))
            )
        return updated
