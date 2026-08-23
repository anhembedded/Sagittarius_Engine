import threading
from dataclasses import dataclass
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

from sagittarius_engine.extensions.persistence.i_database_manager import (
    DEFAULT_DB,
    DatabaseNotFoundError,
    IDatabaseManager,
)
from sagittarius_engine.extensions.persistence.i_session import ISession
from sagittarius_engine.extensions.persistence.sqlalchemy_session_adapter import (
    SQLAlchemySessionAdapter,
)


@dataclass
class _DatabaseEntry:
    engine: Any
    session: SQLAlchemySessionAdapter


class SqlAlchemyDatabaseManager(IDatabaseManager):
    """
    @brief SQLAlchemy-backed `IDatabaseManager`. Thread-safe: every method acquires an
    internal `RLock` before touching the entry dict, matching `StdLibContainer`'s own
    locking pattern for the same reason — extensions may register/resolve concurrently.
    """

    def __init__(self) -> None:
        self._entries: dict[str, _DatabaseEntry] = {}
        self._lock = threading.RLock()

    def add_database(self, name: str, url: str, **engine_options: Any) -> None:
        with self._lock:
            if name in self._entries:
                raise ValueError(
                    f"Database {name!r} is already registered. Call remove_database() "
                    "first if you intend to replace it."
                )
            engine = create_engine(url, **engine_options)
            session_factory = sessionmaker(bind=engine)
            session = scoped_session(session_factory)
            self._entries[name] = _DatabaseEntry(
                engine=engine, session=SQLAlchemySessionAdapter(session)
            )

    def remove_database(self, name: str) -> None:
        with self._lock:
            entry = self._entries.pop(name, None)
            if entry is None:
                raise DatabaseNotFoundError(name, list(self._entries.keys()))
            entry.engine.dispose()

    def get_session(self, name: str = DEFAULT_DB) -> ISession:
        with self._lock:
            entry = self._entries.get(name)
            if entry is None:
                raise DatabaseNotFoundError(name, list(self._entries.keys()))
            return entry.session

    def get_engine(self, name: str = DEFAULT_DB) -> Any:
        with self._lock:
            entry = self._entries.get(name)
            if entry is None:
                raise DatabaseNotFoundError(name, list(self._entries.keys()))
            return entry.engine

    def names(self) -> list[str]:
        with self._lock:
            return list(self._entries.keys())

    def dispose_all(self) -> None:
        with self._lock:
            for entry in self._entries.values():
                entry.engine.dispose()
            self._entries.clear()
