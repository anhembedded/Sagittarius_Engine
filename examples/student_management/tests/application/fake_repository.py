from datetime import datetime

from examples.student_management.application.ports.student_repository import (
    IStudentRepository,
)
from examples.student_management.domain.student import Student, StudentId


class FakeStudentRepository(IStudentRepository):
    def __init__(self) -> None:
        self._store: dict[str, Student] = {}

    def add(self, student: Student) -> None:
        self._store[student.id.value] = student

    def get(self, student_id: StudentId) -> Student | None:
        return self._store.get(student_id.value)

    def list_all(self) -> list[Student]:
        return list(self._store.values())

    def update(self, student: Student) -> None:
        self._store[student.id.value] = student

    def delete(self, student_id: StudentId) -> None:
        self._store.pop(student_id.value, None)

    def search_by_name(self, name_contains: str) -> list[Student]:
        needle = name_contains.lower()
        return [s for s in self._store.values() if needle in s.full_name.lower()]

    def list_by_enrollment_date(
        self, from_dt: datetime | None, to_dt: datetime | None
    ) -> list[Student]:
        return [
            s
            for s in self._store.values()
            if (from_dt is None or s.enrolled_at >= from_dt)
            and (to_dt is None or s.enrolled_at <= to_dt)
        ]
