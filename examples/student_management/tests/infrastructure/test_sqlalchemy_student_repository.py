import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.pool import StaticPool

from examples.student_management.domain.student import Email, Student, StudentId
from examples.student_management.infrastructure.persistence.orm_models import Base
from examples.student_management.infrastructure.persistence.sqlalchemy_student_repository import (
    SqlAlchemyStudentRepository,
)
from sagittarius_engine.extensions.persistence.sqlalchemy_session_adapter import (
    SQLAlchemySessionAdapter,
)


@pytest.fixture
def repo():
    # StaticPool + check_same_thread=False: an in-memory SQLite database lives
    # only on its one connection, and SQLAlchemy's default pool hands out a
    # fresh connection (== a fresh, empty database) per checkout. StaticPool
    # pins every checkout to the same underlying connection so the schema
    # created below is still there for the rest of the test.
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    session = SQLAlchemySessionAdapter(scoped_session(session_factory))
    yield SqlAlchemyStudentRepository(session)
    session.close()


def _commit(repo) -> None:
    repo._session.commit()


def test_add_and_get_roundtrip(repo):
    student = Student.enroll("Alice", Email("a@b.com"), "CS", 3.7)
    repo.add(student)
    _commit(repo)

    fetched = repo.get(student.id)

    assert fetched is not None
    assert fetched.full_name == "Alice"
    assert fetched.email.value == "a@b.com"
    assert fetched.gpa == 3.7


def test_get_missing_returns_none(repo):
    assert repo.get(StudentId.new()) is None


def test_list_all_returns_every_student(repo):
    repo.add(Student.enroll("Alice", Email("a@b.com"), "CS", 3.0))
    repo.add(Student.enroll("Bob", Email("b@b.com"), "Math", 3.5))
    _commit(repo)

    assert len(repo.list_all()) == 2


def test_update_persists_changes(repo):
    student = Student.enroll("Alice", Email("a@b.com"), "CS", 3.0)
    repo.add(student)
    _commit(repo)

    updated = student.with_updates(gpa=3.9)
    repo.update(updated)
    _commit(repo)

    assert repo.get(student.id).gpa == 3.9


def test_delete_removes_student(repo):
    student = Student.enroll("Alice", Email("a@b.com"), "CS", 3.0)
    repo.add(student)
    _commit(repo)

    repo.delete(student.id)
    _commit(repo)

    assert repo.get(student.id) is None


def test_search_by_name_is_case_insensitive(repo):
    repo.add(Student.enroll("Alice Nguyen", Email("a@b.com"), "CS", 3.0))
    repo.add(Student.enroll("Bob Tran", Email("b@b.com"), "Math", 3.5))
    _commit(repo)

    result = repo.search_by_name("alice")

    assert len(result) == 1
    assert result[0].full_name == "Alice Nguyen"
