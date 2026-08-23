from abc import ABC, abstractmethod
from datetime import datetime

from examples.student_management.domain.student import Student, StudentId


class IStudentRepository(ABC):
    @abstractmethod
    def add(self, student: Student) -> None: ...

    @abstractmethod
    def get(self, student_id: StudentId) -> Student | None: ...

    @abstractmethod
    def list_all(self) -> list[Student]: ...

    @abstractmethod
    def update(self, student: Student) -> None: ...

    @abstractmethod
    def delete(self, student_id: StudentId) -> None: ...

    @abstractmethod
    def search_by_name(self, name_contains: str) -> list[Student]: ...

    @abstractmethod
    def list_by_enrollment_date(
        self, from_dt: datetime | None, to_dt: datetime | None
    ) -> list[Student]:
        """@brief Students enrolled within [from_dt, to_dt]. Either bound may
        be None for an open-ended range; both None returns everyone."""
        ...
