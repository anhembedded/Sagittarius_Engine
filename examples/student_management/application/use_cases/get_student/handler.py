from examples.student_management.application.exceptions import StudentNotFoundError
from examples.student_management.application.ports.student_repository import (
    IStudentRepository,
)
from examples.student_management.application.use_cases.get_student.command import (
    GetStudentQuery,
)
from examples.student_management.domain.student import Student, StudentId


class GetStudentHandler:
    def __init__(self, repo: IStudentRepository) -> None:
        self._repo = repo

    def execute(self, dto: GetStudentQuery) -> Student:
        student = self._repo.get(StudentId(dto.student_id))
        if student is None:
            raise StudentNotFoundError(dto.student_id)
        return student
