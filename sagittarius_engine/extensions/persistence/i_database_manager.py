from abc import ABC, abstractmethod
from typing import Any

from sagittarius_engine.extensions.persistence.i_session import ISession

DEFAULT_DB = "default"


class DatabaseNotFoundError(KeyError):
    """@brief Raised when a database name has not been registered via `add_database`."""

    def __init__(self, name: str, known_names: list[str]):
        super().__init__(
            f"No database registered under {name!r}. Known databases: {known_names!r}."
        )
        self.name = name
        self.known_names = known_names


class IDatabaseManager(ABC):
    """
    @brief Owns one-or-many named SQLAlchemy engines/sessions.

    @details The single-database case is just the multi-database case with one entry
    keyed `DEFAULT_DB` — callers that only ever need one database can ignore `name`
    entirely and every method defaults to it.
    """

    @abstractmethod
    def add_database(self, name: str, url: str, **engine_options: Any) -> None:
        """@brief Creates an engine + session for `name`. Raises `ValueError` if `name`
        is already registered.

        @param engine_options Passed straight through to SQLAlchemy's `create_engine`
        (`connect_args`, `pool_size`, `echo`, …). Without this, a caller could not set
        SQLite's `check_same_thread`/`timeout`, which any multi-threaded app needs.
        """
        ...

    @abstractmethod
    def remove_database(self, name: str) -> None:
        """@brief Disposes the engine and drops the session for `name`. Raises
        `DatabaseNotFoundError` if `name` is not registered."""
        ...

    @abstractmethod
    def get_session(self, name: str = DEFAULT_DB) -> ISession:
        """@brief Returns the `ISession` for `name`. Raises `DatabaseNotFoundError` if
        `name` is not registered."""
        ...

    @abstractmethod
    def get_engine(self, name: str = DEFAULT_DB) -> Any:
        """@brief Returns the raw SQLAlchemy `Engine` for `name`. Raises
        `DatabaseNotFoundError` if `name` is not registered."""
        ...

    @abstractmethod
    def names(self) -> list[str]:
        """@brief Returns the currently registered database names."""
        ...

    @abstractmethod
    def dispose_all(self) -> None:
        """@brief Disposes every engine this manager owns and forgets them all.

        @details Call at application shutdown or test teardown — without it, SQLite
        file handles stay open and surface as `ResourceWarning: unclosed database`.
        Unlike `remove_database`, this never touches anything on disk.
        """
        ...
