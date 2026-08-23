import threading
from dataclasses import dataclass
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import close_all_sessions, scoped_session, sessionmaker

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
            # Close the session BEFORE disposing the engine. entry.session
            # wraps a scoped_session, which keeps its thread-local Session
            # (and the connection it has checked out) alive independently of
            # the engine's own pool — engine.dispose() alone does not force
            # a checked-out connection closed, only pooled/idle ones. Found
            # 2026-08-23: this ordering matters, not just doing both.
            entry.session.close()
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
            # close_all_sessions(), not entry.session.close() per entry:
            # App.stop() runs each shutdown step (including this one, via
            # DatabaseExtension.shutdown()) on its own dedicated thread for
            # hang-protection (TASK-017 issue 7). scoped_session.remove()
            # only clears the CALLING thread's session — it is a no-op for
            # a session created on the original boot thread, which leaves
            # its connection (and, for a file-backed SQLite database, the
            # underlying OS file handle) open. Found 2026-08-23: the
            # per-entry entry.session.close() this replaced worked in every
            # standalone/same-thread test but not through the real App,
            # because App.stop()'s threading changed which thread this
            # method runs on. close_all_sessions() is SQLAlchemy's
            # cross-thread-safe equivalent — it closes every scoped session
            # process-wide, regardless of which thread created it. Correct
            # here specifically because dispose_all() already means "every
            # database this manager owns is going away"; deliberately not
            # used in remove_database() below, which runs on the caller's
            # own thread at arbitrary application runtime and must not tear
            # down unrelated shards' still-active sessions.
            close_all_sessions()
            for entry in self._entries.values():
                entry.engine.dispose()
            self._entries.clear()
