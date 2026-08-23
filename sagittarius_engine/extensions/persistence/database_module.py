import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

from sagittarius_engine.extensions.persistence.i_database_manager import (
    DEFAULT_DB,
    IDatabaseManager,
)
from sagittarius_engine.extensions.persistence.i_session import ISession
from sagittarius_engine.interfaces import IConfig, ILogger
from sagittarius_engine.interfaces.i_extension import IExtension

try:
    from sqlalchemy import Engine

    from sagittarius_engine.extensions.persistence.database_manager import (
        SqlAlchemyDatabaseManager,
    )

    SQLALCHEMY_INSTALLED = True
except ImportError:
    SQLALCHEMY_INSTALLED = False


from typing import Protocol

from sagittarius_engine.interfaces.i_container import IContainer


class IDatabaseContext(Protocol):
    @property
    def container(self) -> IContainer: ...


class DatabaseExtension(IExtension[IDatabaseContext]):
    """
    @brief Extension for setting up the Database connection(s) and Session(s).

    @details Supports two config shapes, mutually exclusive:
    - `database.url` (a string) — the legacy single-database path. Registers `ISession`
      and `Engine` singletons directly, so existing consumers keep working unchanged.
    - `database.shards` (a `dict[str, str]` of name -> url) — multiple named databases.
      `ISession`/`Engine` are NOT registered as singletons in this case (which shard would
      that mean?) — consumers must resolve `IDatabaseManager` and call
      `get_session(name)`/`get_engine(name)`.

    Either way, `IDatabaseManager` is always registered, so it's the one sanctioned way to
    reach a raw `Engine` (supersedes `TASK-019`) and, for shard consumers, the only way to
    reach a session at all.
    """

    def register(self, context: IDatabaseContext) -> None:
        logger = self._get_logger(context)
        if not SQLALCHEMY_INSTALLED:
            if logger:
                logger.warning(
                    "DatabaseExtension: sqlalchemy is not installed. Database setup skipped."
                )
            return
        shards: dict[str, str] | None = None
        try:
            config: IConfig = context.container.resolve(IConfig)
            env = str(
                config.get("env")
                or config.get("app.env")
                or os.environ.get("ENV")
                or os.environ.get("APP_ENV")
                or "development"
            ).lower()
            shards = config.get("database.shards")
            db_url = config.get("database.url")
            if not shards and not db_url:
                if env == "production":
                    raise ValueError(
                        "Database configuration 'database.url' is missing in production environment."
                    )
                db_url = "sqlite:///:memory:"
                if logger:
                    logger.info(
                        "DatabaseExtension: 'database.url' not found. Using default in-memory SQLite."
                    )
        except Exception as e:
            if isinstance(e, ValueError) and "production environment" in str(e):
                raise
            env = str(
                os.environ.get("ENV") or os.environ.get("APP_ENV") or "development"
            ).lower()
            if env == "production":
                raise ValueError(
                    f"Failed to resolve database configuration in production: {e}"
                ) from e
            shards = None
            db_url = "sqlite:///:memory:"
            if logger:
                logger.info(
                    "DatabaseExtension: IConfig not found or failed to resolve. Using default in-memory SQLite."
                )
        try:
            manager = SqlAlchemyDatabaseManager()
            if shards:
                for name, url in shards.items():
                    manager.add_database(name, url)
                context.container.singleton(IDatabaseManager, manager)
                if logger:
                    logger.info(
                        f"DatabaseExtension: {len(shards)} sharded database(s) registered: "
                        f"{list(shards.keys())}."
                    )
            else:
                manager.add_database(DEFAULT_DB, db_url)
                context.container.singleton(ISession, manager.get_session(DEFAULT_DB))
                context.container.singleton(Engine, manager.get_engine(DEFAULT_DB))
                context.container.singleton(IDatabaseManager, manager)
                if logger:
                    logger.info(
                        f"DatabaseExtension: SQLAlchemy engine created for {db_url} and "
                        "ISession registered."
                    )
        except Exception as e:
            if logger:
                logger.error(f"DatabaseExtension: Failed to initialize database - {e}")

    def boot(self, context: IDatabaseContext) -> None:
        pass

    def shutdown(self, context: IDatabaseContext) -> None:
        """@brief Disposes every registered database's engine (closes its
        connection pool). Without this, an sqlite:/// file's OS-level file
        handle stays open after App.stop() — harmless on POSIX (which allows
        deleting an open file), but on Windows a caller that then tries to
        remove the database file (e.g. a test's tempfile.TemporaryDirectory
        cleanup) gets PermissionError. Found 2026-08-23: register() already
        builds an IDatabaseManager and registers it as a singleton — this
        was previously a no-op that never reached it to call the dispose_all()
        it already provides."""
        try:
            manager = context.container.resolve(IDatabaseManager)
        except Exception:
            return  # register() never got far enough to register one.
        manager.dispose_all()

    def _get_logger(self, context: IDatabaseContext) -> ILogger | None:
        try:
            return context.container.resolve(ILogger)
        except Exception:
            return None


SqlAlchemyExtension = DatabaseExtension
