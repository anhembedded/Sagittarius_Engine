from datetime import datetime

from examples.student_management.application.ports.student_repository import (
    IStudentRepository,
)
from examples.student_management.domain.student import Email, Student, StudentId
from examples.student_management.infrastructure.persistence.orm_models import (
    StudentRecord,
)
from sagittarius_engine.extensions.persistence.i_session import ISession


def _to_domain(record: StudentRecord) -> Student:
    return Student(
        id=StudentId(record.id),
        full_name=record.full_name,
        email=Email(record.email),
        major=record.major,
        gpa=record.gpa,
        enrolled_at=record.enrolled_at,
    )


def _to_record(student: Student) -> StudentRecord:
    return StudentRecord(
        id=student.id.value,
        full_name=student.full_name,
        email=student.email.value,
        major=student.major,
        gpa=student.gpa,
        enrolled_at=student.enrolled_at,
    )


class SqlAlchemyStudentRepository(IStudentRepository):
    """
    @brief Real persistence for the sample app, via the engine's ISession port.

    @details Commit boundaries are deliberately NOT here — see
    docs/persistence_and_transactions.md. This repository only stages changes
    (add/merge/delete); the engine's TransactionMiddleware commits once per
    dispatched command, or a caller outside the dispatch pipeline (tests,
    scripts) must commit explicitly.
    """

    def __init__(self, session: ISession) -> None:
        self._session = session

    def add(self, student: Student) -> None:
        self._session.add(_to_record(student))

    def get(self, student_id: StudentId) -> Student | None:
        record = self._session.get(StudentRecord, student_id.value)
        return _to_domain(record) if record is not None else None

    def list_all(self) -> list[Student]:
        records = self._session.query(StudentRecord).all()
        return [_to_domain(r) for r in records]

    def update(self, student: Student) -> None:
        self._session.merge(_to_record(student))

    def delete(self, student_id: StudentId) -> None:
        record = self._session.get(StudentRecord, student_id.value)
        if record is not None:
            self._session.delete(record)

    def search_by_name(self, name_contains: str) -> list[Student]:
        records = (
            self._session.query(StudentRecord)
            .filter(StudentRecord.full_name.ilike(f"%{name_contains}%"))
            .all()
        )
        return [_to_domain(r) for r in records]

    def list_by_enrollment_date(
        self, from_dt: datetime | None, to_dt: datetime | None
    ) -> list[Student]:
        query = self._session.query(StudentRecord)
        if from_dt is not None:
            query = query.filter(StudentRecord.enrolled_at >= from_dt)
        if to_dt is not None:
            query = query.filter(StudentRecord.enrolled_at <= to_dt)
        return [_to_domain(r) for r in query.all()]
