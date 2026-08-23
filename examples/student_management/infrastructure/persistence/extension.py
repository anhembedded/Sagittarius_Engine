import os
from typing import ClassVar, Protocol

from sqlalchemy import Engine

from examples.student_management.application.ports.student_repository import (
    IStudentRepository,
)
from examples.student_management.infrastructure.persistence.orm_models import Base
from examples.student_management.infrastructure.persistence.sqlalchemy_student_repository import (
    SqlAlchemyStudentRepository,
)
from sagittarius_engine.extensions.persistence.i_session import ISession
from sagittarius_engine.interfaces.i_container import IContainer
from sagittarius_engine.interfaces.i_extension import IExtension


class IStudentManagementContext(Protocol):
    @property
    def container(self) -> IContainer: ...


class StudentManagementExtension(IExtension[IStudentManagementContext]):
    """
    @brief Registers this app's repository and creates its schema.

    @details Needs the engine's `DatabaseExtension` to have registered `ISession`
    first. That ordering is declared below rather than left to `app.use()` call
    order — see docs/module_registration.md.
    """

    #: Matched by class name against another extension's `descriptor.name`
    #: (see `ExtensionManager._build_and_sort`, which topologically sorts on
    #: this) — makes boot order robust to `app.use()` call order instead of
    #: depending on it. Verified: reversing the two `app.use()` calls in
    #: main.py still boots cleanly with this declared.
    dependencies: ClassVar[list[str]] = ["DatabaseExtension"]

    def register(self, context: IStudentManagementContext) -> None:
        session = context.container.resolve(ISession)
        repo = SqlAlchemyStudentRepository(session)
        context.container.singleton(IStudentRepository, repo)

        # TASK-019 (Sagittarius_Engine, superseded by EPIC-003B): DatabaseExtension now
        # registers the raw Engine it built as a singleton, so schema creation uses that
        # same Engine — no second, unrelated Engine needed. See docs/persistence_and_transactions.md.
        engine = context.container.resolve(Engine)
        _ensure_parent_dir(str(engine.url))
        Base.metadata.create_all(engine)

    def boot(self, context: IStudentManagementContext) -> None:
        pass

    def shutdown(self, context: IStudentManagementContext) -> None:
        pass


def _ensure_parent_dir(sqlite_url: str) -> None:
    path = sqlite_url.removeprefix("sqlite:///")
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
