import os
from typing import ClassVar, Protocol

from sqlalchemy import create_engine

from examples.student_management.application.ports.student_repository import (
    IStudentRepository,
)
from examples.student_management.infrastructure.persistence.orm_models import Base
from examples.student_management.infrastructure.persistence.sqlalchemy_student_repository import (
    SqlAlchemyStudentRepository,
)
from sagittarius_engine.extensions.persistence.i_session import ISession
from sagittarius_engine.interfaces import IConfig
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

        # Workaround for TASK-019 (Sagittarius_Engine/Tasks/backlog/): the
        # engine's DatabaseExtension builds a SQLAlchemy Engine internally but
        # never exposes it, so there is no sanctioned way to reach it and run
        # create_all(). Rebuilding a second Engine from the same config value
        # only works because database.url points at a real file, not
        # ':memory:' — two Engines against the same in-memory URL are two
        # unrelated, unshared databases, so create_all() would silently
        # target the wrong one. See docs/persistence_and_transactions.md.
        config: IConfig = context.container.resolve(IConfig)
        db_url: str = config.get("database.url", "sqlite:///:memory:")
        if ":memory:" in db_url:
            raise ValueError(
                "StudentManagementExtension requires a file-based sqlite URL "
                "(':memory:' would create its schema in an unrelated database "
                "from the one DatabaseExtension's session actually uses)."
            )
        _ensure_parent_dir(db_url)
        schema_engine = create_engine(db_url)
        Base.metadata.create_all(schema_engine)
        schema_engine.dispose()

    def boot(self, context: IStudentManagementContext) -> None:
        pass

    def shutdown(self, context: IStudentManagementContext) -> None:
        pass


def _ensure_parent_dir(sqlite_url: str) -> None:
    path = sqlite_url.removeprefix("sqlite:///")
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
