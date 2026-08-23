from examples.student_management.application.ports.student_repository import (
    IStudentRepository,
)
from examples.student_management.application.use_cases.list_students.command import (
    ListStudentsQuery,
)
from examples.student_management.domain.student import Student


class ListStudentsHandler:
    def __init__(self, repo: IStudentRepository) -> None:
        self._repo = repo

    def execute(self, dto: ListStudentsQuery) -> list[Student]:
        return self._repo.list_all()
