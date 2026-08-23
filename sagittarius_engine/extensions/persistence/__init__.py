from .database_module import DatabaseExtension, SqlAlchemyExtension
from .i_database_manager import DEFAULT_DB, DatabaseNotFoundError, IDatabaseManager
from .i_session import ISession
from .repository import BaseRepository
from .sqlalchemy_session_adapter import SQLAlchemySessionAdapter

#: Deliberately NOT re-exported here: `SqlAlchemyDatabaseManager` and
#: `SqliteShardManager`. Both import `sqlalchemy` at module scope, whereas this package
#: must stay importable *without* it — `DatabaseExtension` is built to degrade
#: gracefully when SQLAlchemy is absent (guarded import, `SQLALCHEMY_INSTALLED`, logs a
#: warning and skips setup; see `test_database_module_no_sqlalchemy`), and `ISession` /
#: `IDatabaseManager` are pure interfaces with no SQLAlchemy dependency of their own.
#: Re-exporting an unguarded importer would quietly make SQLAlchemy mandatory for anyone
#: doing `from ...extensions.persistence import ISession`.
#:
#: This was first caught the harder way: adding `SqliteShardManager` here broke
#: `test_core_boot_does_not_require_persistence_extension`, because the root package
#: still reached this `__init__` at the time. `TASK-031` has since stopped the root
#: importing any extension, so that particular path no longer applies — the reason above
#: is the one that still does.
#:
#: Import them from their own modules: `...persistence.sqlite_shard_manager`.
__all__ = [
    "DEFAULT_DB",
    "BaseRepository",
    "DatabaseExtension",
    "DatabaseNotFoundError",
    "IDatabaseManager",
    "ISession",
    "SQLAlchemySessionAdapter",
    "SqlAlchemyExtension",
]
