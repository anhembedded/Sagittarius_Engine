from abc import ABC, abstractmethod

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
