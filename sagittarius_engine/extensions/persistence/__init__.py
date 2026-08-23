from .database_module import DatabaseExtension, SqlAlchemyExtension
from .i_database_manager import DEFAULT_DB, DatabaseNotFoundError, IDatabaseManager
from .i_session import ISession
from .repository import BaseRepository
from .sqlalchemy_session_adapter import SQLAlchemySessionAdapter

#: Deliberately NOT re-exported here: `SqlAlchemyDatabaseManager` and
#: `SqliteShardManager`. Both import `sqlalchemy` at module scope, and this package's
#: `__init__` is reached from `sagittarius_engine/__init__.py` — re-exporting them makes
#: SQLAlchemy a hard requirement just to boot the kernel, which
#: `test_core_boot_does_not_require_persistence_extension` exists to prevent (it caught
#: exactly that regression when `SqliteShardManager` was first added here). Import them
#: from their own modules: `...persistence.sqlite_shard_manager`.
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
