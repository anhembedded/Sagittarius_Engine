from examples.student_management.application.ports.student_repository import (
    IStudentRepository,
)
from examples.student_management.application.use_cases.list_students_by_enrollment_date.command import (
    ListStudentsByEnrollmentDateQuery,
)
from examples.student_management.domain.student import Student


class ListStudentsByEnrollmentDateHandler:
    def __init__(self, repo: IStudentRepository) -> None:
        self._repo = repo

    def execute(self, dto: ListStudentsByEnrollmentDateQuery) -> list[Student]:
        return self._repo.list_by_enrollment_date(dto.from_dt, dto.to_dt)
