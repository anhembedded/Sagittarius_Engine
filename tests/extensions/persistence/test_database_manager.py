import threading

import pytest

from sagittarius_engine.extensions.persistence.database_manager import (
    SqlAlchemyDatabaseManager,
)
from sagittarius_engine.extensions.persistence.i_database_manager import (
    DEFAULT_DB,
    DatabaseNotFoundError,
)


def _manager() -> SqlAlchemyDatabaseManager:
    return SqlAlchemyDatabaseManager()


def test_add_and_get_session_and_engine_round_trip():
    manager = _manager()
    manager.add_database(DEFAULT_DB, "sqlite:///:memory:")

    session = manager.get_session(DEFAULT_DB)
    engine = manager.get_engine(DEFAULT_DB)

    assert session is not None
    assert engine is not None
    assert manager.get_session(DEFAULT_DB) is session
    assert manager.get_engine(DEFAULT_DB) is engine


def test_add_database_duplicate_name_raises():
    manager = _manager()
    manager.add_database("shard1", "sqlite:///:memory:")

    with pytest.raises(ValueError):
        manager.add_database("shard1", "sqlite:///:memory:")


def test_remove_database_disposes_and_subsequent_get_raises():
    manager = _manager()
    manager.add_database("shard1", "sqlite:///:memory:")
    engine = manager.get_engine("shard1")

    manager.remove_database("shard1")

    assert engine.pool.status() is not None  # engine object still exists post-dispose
    with pytest.raises(DatabaseNotFoundError):
        manager.get_session("shard1")
    with pytest.raises(DatabaseNotFoundError):
        manager.get_engine("shard1")


def test_remove_database_unknown_name_raises():
    manager = _manager()

    with pytest.raises(DatabaseNotFoundError):
        manager.remove_database("nonexistent")


def test_get_session_unknown_name_error_message_names_known_databases():
    manager = _manager()
    manager.add_database("shard1", "sqlite:///:memory:")

    with pytest.raises(DatabaseNotFoundError) as exc_info:
        manager.get_session("nonexistent")

    assert "nonexistent" in str(exc_info.value)
    assert "shard1" in str(exc_info.value)


def test_names_reflects_add_and_remove_sequence():
    manager = _manager()
    assert manager.names() == []

    manager.add_database("shard1", "sqlite:///:memory:")
    manager.add_database("shard2", "sqlite:///:memory:")
    assert set(manager.names()) == {"shard1", "shard2"}

    manager.remove_database("shard1")
    assert manager.names() == ["shard2"]


def test_concurrent_add_database_is_thread_safe():
    manager = _manager()
    errors: list[Exception] = []

    def add(name: str) -> None:
        try:
            manager.add_database(name, "sqlite:///:memory:")
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=add, args=(f"shard{i}",)) for i in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == []
    assert set(manager.names()) == {f"shard{i}" for i in range(20)}
