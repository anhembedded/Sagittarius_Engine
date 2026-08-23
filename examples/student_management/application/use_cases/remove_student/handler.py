from examples.student_management.application.exceptions import StudentNotFoundError
from examples.student_management.application.ports.student_repository import (
    IStudentRepository,
)
from examples.student_management.application.use_cases.remove_student.command import (
    RemoveStudentCommand,
)
from examples.student_management.domain.events import StudentRemoved
from examples.student_management.domain.student import StudentId
from sagittarius_engine.interfaces import IEventBus


class RemoveStudentHandler:
    def __init__(self, repo: IStudentRepository, event_bus: IEventBus) -> None:
        self._repo = repo
        self._event_bus = event_bus

    def execute(self, dto: RemoveStudentCommand) -> None:
        student_id = StudentId(dto.student_id)
        if self._repo.get(student_id) is None:
            raise StudentNotFoundError(dto.student_id)
        self._repo.delete(student_id)
        self._event_bus.emit(StudentRemoved(student_id=dto.student_id))
