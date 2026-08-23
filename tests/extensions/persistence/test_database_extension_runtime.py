"""
[Integration Test — EPIC-003C]

Proves the mechanism a later Elite Warrior migration would depend on: a consumer
resolves `IDatabaseManager` from the container *after* `DatabaseExtension.register()`
has already run (i.e., at real runtime, not during setup), and can add/remove named
databases dynamically — mirroring shards being created/destroyed per trading symbol.
"""

import os
import tempfile
import threading

import pytest
from sqlalchemy import text as sql_text

from sagittarius_engine import App
from sagittarius_engine.extensions.persistence import (
    DatabaseNotFoundError,
    IDatabaseManager,
)
from sagittarius_engine.extensions.persistence.database_manager import (
    SqlAlchemyDatabaseManager,
)
from sagittarius_engine.extensions.persistence.database_module import DatabaseExtension
from sagittarius_engine.infrastructure import MemoryEventBus, StdLibContainer
from sagittarius_engine.infrastructure.config.dict_config import DictConfig
from sagittarius_engine.interfaces import IConfig


def _boot_app_with_database_extension(config_values: dict) -> App:
    container = StdLibContainer()
    event_bus = MemoryEventBus()
    app = App(container, event_bus)
    container.singleton(IConfig, DictConfig(config_values))
    app.use(DatabaseExtension())
    app.boot()
    return app


def test_runtime_add_database_after_boot_is_immediately_usable():
    app = _boot_app_with_database_extension({"database.url": "sqlite:///:memory:"})
    manager = app.container.resolve(IDatabaseManager)

    manager.add_database("BTCUSDT", "sqlite:///:memory:")

    session = manager.get_session("BTCUSDT")
    assert session is not None
    assert set(manager.names()) == {"default", "BTCUSDT"}


def test_shutdown_disposes_the_engine_so_a_backing_sqlite_file_can_be_deleted():
    """@brief Regression test, two bugs deep. DatabaseExtension.shutdown()
    was previously a no-op (found 2026-08-23), so app.stop() never disposed
    the engine's connection pool at all. Fixing that alone was still
    insufficient: App.stop() runs each shutdown step (including this one) on
    its own dedicated thread for hang-protection (TASK-017 issue 7), and the
    session this manager owns is a scoped_session, keyed by the thread that
    created it — scoped_session.remove(), called from that different thread,
    silently closes nothing. See test_dispose_all_closes_a_session_created_on_a_different_thread
    below for the isolated version of this exact mechanism. Harmless on
    POSIX, but on Windows the leaked sqlite:/// file handle meant a caller
    that tried to delete the file after stop() (e.g.
    examples/student_management's own integration tests cleaning up a
    tempfile.TemporaryDirectory) got PermissionError. Proven here with a
    real file-backed database rather than :memory:, since the bug is
    specifically about an OS-level file handle, through the real App (not a
    synthetic thread) so this fails again if App.stop()'s threading changes
    in a way that reintroduces it."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = os.path.join(tmp_dir, "test.db")
        app = _boot_app_with_database_extension(
            {"database.url": f"sqlite:///{db_path}"}
        )
        manager = app.container.resolve(IDatabaseManager)
        # Force the connection to actually open, not just be configured.
        manager.get_session().execute(sql_text("SELECT 1"))

        app.stop()

        os.remove(db_path)  # raises PermissionError on Windows if still locked


def test_dispose_all_closes_a_session_created_on_a_different_thread():
    """@brief Isolates the exact mechanism the App-level test above proves
    end-to-end: dispose_all() must close a scoped_session's connection even
    when called from a thread other than the one that created it (as
    App.stop() now does for every shutdown step, TASK-017 issue 7).
    scoped_session.remove() cannot do this — it is thread-local by design —
    which is why dispose_all() uses SQLAlchemy's close_all_sessions()
    instead. Verified directly against the manager, no App involved, so a
    failure here points straight at database_manager.py rather than at
    App's own shutdown sequencing."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = os.path.join(tmp_dir, "test.db")
        manager = SqlAlchemyDatabaseManager()
        manager.add_database("default", f"sqlite:///{db_path}")

        def use_on_this_thread() -> None:
            manager.get_session().execute(sql_text("SELECT 1"))

        use_on_this_thread()  # session created on the main test thread

        cleanup_thread = threading.Thread(target=manager.dispose_all)
        cleanup_thread.start()
        cleanup_thread.join()

        os.remove(db_path)  # raises PermissionError on Windows if still locked


def test_shutdown_clears_the_database_manager():
    app = _boot_app_with_database_extension({"database.url": "sqlite:///:memory:"})
    manager = app.container.resolve(IDatabaseManager)
    assert manager.names() == ["default"]

    app.stop()

    assert manager.names() == []


def test_runtime_remove_database_after_boot_disposes_and_forgets():
    app = _boot_app_with_database_extension({"database.url": "sqlite:///:memory:"})
    manager = app.container.resolve(IDatabaseManager)
    manager.add_database("ETHUSDT", "sqlite:///:memory:")

    manager.remove_database("ETHUSDT")

    assert manager.names() == ["default"]
    with pytest.raises(DatabaseNotFoundError):
        manager.get_session("ETHUSDT")


def test_runtime_add_then_remove_cycle_matches_per_symbol_shard_lifecycle():
    app = _boot_app_with_database_extension(
        {"database.shards": {"BTCUSDT": "sqlite:///:memory:"}}
    )
    manager = app.container.resolve(IDatabaseManager)
    assert manager.names() == ["BTCUSDT"]

    manager.add_database("ETHUSDT", "sqlite:///:memory:")
    manager.add_database("SOLUSDT", "sqlite:///:memory:")
    assert set(manager.names()) == {"BTCUSDT", "ETHUSDT", "SOLUSDT"}

    manager.remove_database("SOLUSDT")
    assert set(manager.names()) == {"BTCUSDT", "ETHUSDT"}

    with pytest.raises(DatabaseNotFoundError):
        manager.get_session("SOLUSDT")
    assert manager.get_session("BTCUSDT") is not None
    assert manager.get_session("ETHUSDT") is not None
