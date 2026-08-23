"""Sharded-SQLite `IDatabaseManager`: one database file per shard name.

Generalized out of `Sagittarius_Elite_Warrior`'s own `DatabaseManager` (EPIC-004),
which sharded per traded symbol. Nothing here is trading-specific — a shard name is
just a name — so any app that wants "one SQLite file per tenant/partition/instrument"
gets the file layout, the safety checks, and the SQLite tuning without rewriting them.
"""

from __future__ import annotations

import os
import re
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from sagittarius_engine.extensions.persistence.i_database_manager import (
    DEFAULT_DB,
    DatabaseNotFoundError,
    IDatabaseManager,
)
from sagittarius_engine.extensions.persistence.i_session import ISession
from sagittarius_engine.extensions.persistence.sqlalchemy_session_adapter import (
    SQLAlchemySessionAdapter,
)

#: Passed to `directory` to keep every shard in memory instead of on disk. Each shard
#: gets its own shared-cache URI so connections to the *same* shard see one database
#: while different shards stay isolated — plain `:memory:` would give every connection
#: its own private, empty database.
IN_MEMORY = ":memory:"

#: Shard names become filenames, so they are restricted rather than escaped. Anything
#: outside this set is rejected before it can reach the filesystem.
DEFAULT_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")

#: `check_same_thread=False` because SQLAlchemy pools connections across threads and
#: does its own synchronization; `timeout` so concurrent writers wait for the lock
#: instead of failing immediately with "database is locked".
DEFAULT_CONNECT_ARGS: dict[str, Any] = {"check_same_thread": False, "timeout": 15}

#: WAL lets readers and writers work concurrently instead of blocking each other;
#: `synchronous=NORMAL` is the standard companion — durable across app crashes,
#: trading one fsync-per-commit for throughput.
DEFAULT_PRAGMAS: tuple[str, ...] = (
    "journal_mode=WAL",
    "synchronous=NORMAL",
)


@dataclass(frozen=True)
class SqliteShardConfig:
    """@brief Configuration for `SqliteShardManager`."""

    #: Directory holding `<name>.db` files, or `IN_MEMORY`.
    directory: str
    #: `MetaData` whose tables are created on each new shard (usually
    #: `YourDeclarativeBase.metadata`). `None` skips schema creation entirely.
    metadata: sa.MetaData | None = None
    connect_args: dict[str, Any] = field(
        default_factory=lambda: dict(DEFAULT_CONNECT_ARGS)
    )
    pragmas: tuple[str, ...] = DEFAULT_PRAGMAS
    name_pattern: re.Pattern[str] = DEFAULT_NAME_PATTERN


class SqliteShardManager(IDatabaseManager):
    """
    @brief One SQLite database file per shard name, created on first use.

    @details Differs from `SqlAlchemyDatabaseManager` in three ways that matter:
    shards are created **lazily** by `get_session()` rather than declared up front
    (a caller usually cannot know every shard name at boot); `get_session()` hands
    back a **fresh** session each call rather than one shared instance, so callers
    can hold independent transactions; and `remove_shard()`/`purge_all()` delete
    files from disk, which the in-memory-registry manager never does.

    Thread-safe — all state changes hold an `RLock`, matching `StdLibContainer`.
    """

    def __init__(self, config: SqliteShardConfig) -> None:
        self._config = config
        self._directory = config.directory
        self._factories: dict[str, sessionmaker[Session]] = {}
        self._engines: dict[str, sa.Engine] = {}
        self._lock = threading.RLock()

        if self._directory != IN_MEMORY:
            os.makedirs(self._directory, exist_ok=True)

    # ── IDatabaseManager ────────────────────────────────────────────────────

    def add_database(self, name: str, url: str, **engine_options: Any) -> None:
        """@brief Registers a shard at an explicit URL, bypassing directory layout.

        @details Rarely needed — `get_session()` creates shards on demand. Present so
        `SqliteShardManager` honours `IDatabaseManager` and so a caller can point one
        shard somewhere unusual (a read-only file, a differently-tuned engine).
        """
        with self._lock:
            if name in self._factories:
                raise ValueError(
                    f"Shard {name!r} is already registered. Call remove_shard() first "
                    "if you intend to replace it."
                )
            self._create_shard(name, url, **engine_options)

    def get_session(self, name: str = DEFAULT_DB) -> ISession:
        """@brief Returns a **new** session for `name`, creating the shard if needed."""
        return SQLAlchemySessionAdapter(self.get_raw_session(name))

    def get_engine(self, name: str = DEFAULT_DB) -> sa.Engine:
        """@brief Returns the raw `Engine` for `name`, creating the shard if needed."""
        with self._lock:
            self._ensure_shard(name)
            return self._engines[name]

    def remove_database(self, name: str) -> None:
        """@brief `IDatabaseManager` spelling of `remove_shard`, minus the return value.

        @details Raises `DatabaseNotFoundError` when nothing was removed, because the
        interface promises that, whereas `remove_shard` reports it as `False`.
        """
        if not self.remove_shard(name):
            raise DatabaseNotFoundError(name, self.names())

    def names(self) -> list[str]:
        """@brief `IDatabaseManager` spelling of `list_shards`."""
        return self.list_shards()

    def dispose_all(self) -> None:
        """@brief Disposes every open engine. Touches nothing on disk."""
        with self._lock:
            for engine in self._engines.values():
                engine.dispose()
            self._engines.clear()
            self._factories.clear()

    # ── Shard-specific surface ──────────────────────────────────────────────

    def get_raw_session(self, name: str) -> Session:
        """@brief Like `get_session`, but the unwrapped SQLAlchemy `Session`.

        @details For callers that need the full `Session` API rather than `ISession`'s
        subset. Prefer `get_session()` unless something specific is missing.
        """
        with self._lock:
            self._ensure_shard(name)
            return self._factories[name]()

    def list_shards(self) -> list[str]:
        """@brief Shard names that exist, sorted.

        @details On disk this is what is actually *there*, not merely what this manager
        has opened — a shard written by a previous run counts. In memory, only shards
        this instance created can be known.
        """
        with self._lock:
            if self._directory == IN_MEMORY:
                return sorted(self._factories.keys())

            if not os.path.isdir(self._directory):
                return []

            return sorted(
                path.stem
                for path in Path(self._directory).glob("*.db")
                if path.is_file() and self._config.name_pattern.match(path.stem)
            )

    def remove_shard(self, name: str) -> bool:
        """@brief Disposes the shard's engine and deletes its files.

        @return True if an open session or any file was removed.
        """
        self._validate_name(name)

        with self._lock:
            had_engine = self._dispose_shard(name)

            if self._directory == IN_MEMORY:
                return had_engine

            removed_any = False
            # -wal and -shm are SQLite's WAL sidecar files; leaving them behind would
            # resurrect data the caller asked to delete.
            for suffix in (".db", ".db-wal", ".db-shm"):
                path = self._shard_path(name, suffix)
                if os.path.isfile(path):
                    os.remove(path)
                    removed_any = True

            return removed_any or had_engine

    def purge_all(self) -> int:
        """@brief Disposes every engine and deletes every shard file.

        @return How many shards existed before the purge.
        """
        with self._lock:
            count = len(self.list_shards())
            self.dispose_all()

            if self._directory != IN_MEMORY:
                base_dir = os.path.abspath(self._directory)
                for path in Path(self._directory).glob("*.db*"):
                    if not path.is_file():
                        continue
                    abs_path = os.path.abspath(str(path))
                    if os.path.commonpath([base_dir, abs_path]) == base_dir:
                        os.remove(abs_path)

            return count

    def vacuum(self, name: str | None = None) -> None:
        """@brief Checkpoints the WAL and compacts the file, for one shard or all.

        @details SQLite does not return space to the filesystem on delete; without
        this, a shard's file only ever grows.
        """
        for shard in [name] if name is not None else self.list_shards():
            if not self._config.name_pattern.match(shard):
                continue
            with self.get_raw_session(shard) as session:
                session.execute(sa.text("PRAGMA wal_checkpoint(TRUNCATE)"))
                session.execute(sa.text("VACUUM"))

    # ── Internals ───────────────────────────────────────────────────────────

    def _validate_name(self, name: str) -> None:
        if not self._config.name_pattern.match(name):
            raise ValueError(f"Invalid shard name: {name!r}")

    def _shard_path(self, name: str, suffix: str = ".db") -> str:
        """@brief Resolves `<directory>/<name><suffix>`, refusing to escape `directory`.

        @details `name` is pattern-checked before this is reached, but the containment
        check stays as defence in depth: a caller can supply its own `name_pattern`,
        and a permissive one must still not be able to reach outside the directory.
        """
        base_dir = os.path.abspath(self._directory)
        candidate = os.path.abspath(
            os.path.normpath(os.path.join(self._directory, f"{name}{suffix}"))
        )
        if os.path.commonpath([base_dir, candidate]) != base_dir:
            raise PermissionError("Path traversal attempt detected")
        return candidate

    def _shard_url(self, name: str) -> str:
        if self._directory == IN_MEMORY:
            return f"sqlite:///file:{name}?mode=memory&cache=shared&uri=true"
        return f"sqlite:///{self._shard_path(name)}"

    def _ensure_shard(self, name: str) -> None:
        """@brief Creates the shard if this manager has not opened it yet."""
        if name in self._factories:
            return
        self._validate_name(name)
        self._create_shard(name, self._shard_url(name), **self._engine_kwargs())

    def _engine_kwargs(self) -> dict[str, Any]:
        return {"connect_args": dict(self._config.connect_args)}

    def _create_shard(self, name: str, url: str, **engine_options: Any) -> None:
        engine = sa.create_engine(url, **engine_options)
        self._attach_pragmas(engine)

        if self._config.metadata is not None:
            self._config.metadata.create_all(engine)

        self._engines[name] = engine
        self._factories[name] = sessionmaker(bind=engine)

    def _attach_pragmas(self, engine: sa.Engine) -> None:
        """@brief Applies the configured PRAGMAs to every connection this engine opens.

        @details Must be per-connection, not once at creation: SQLite scopes PRAGMAs to
        the connection, and a pooled engine opens more than one over its lifetime.
        """
        pragmas = self._config.pragmas
        if not pragmas:
            return

        @sa.event.listens_for(engine, "connect")
        def _set_pragmas(dbapi_connection: Any, _connection_record: Any) -> None:
            cursor = dbapi_connection.cursor()
            try:
                for pragma in pragmas:
                    cursor.execute(f"PRAGMA {pragma}")
            finally:
                cursor.close()

    def _dispose_shard(self, name: str) -> bool:
        engine = self._engines.pop(name, None)
        self._factories.pop(name, None)
        if engine is None:
            return False
        engine.dispose()
        return True
