from examples.student_management.application.ports.student_repository import (
    IStudentRepository,
)
from examples.student_management.application.use_cases.search_students.command import (
    SearchStudentsQuery,
)
from examples.student_management.domain.student import Student


class SearchStudentsHandler:
    def __init__(self, repo: IStudentRepository) -> None:
        self._repo = repo

    def execute(self, dto: SearchStudentsQuery) -> list[Student]:
        return self._repo.search_by_name(dto.name_contains)
