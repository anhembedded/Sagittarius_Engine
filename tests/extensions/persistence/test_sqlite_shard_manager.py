"""Tests for `SqliteShardManager` (EPIC-004A).

The behavioural cases mirror `Sagittarius_Elite_Warrior`'s own
`test_database_manager_shards.py` / `test_security.py` on purpose: this class was
generalized out of that app's `DatabaseManager`, and these tests are what proves the
generalization did not lose anything before that app is migrated onto it (EPIC-004D).
"""

from __future__ import annotations

import tempfile
import threading
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from sagittarius_engine.extensions.persistence.i_database_manager import (
    DatabaseNotFoundError,
)
from sagittarius_engine.extensions.persistence.sqlite_shard_manager import (
    IN_MEMORY,
    SqliteShardConfig,
    SqliteShardManager,
)


class _Base(DeclarativeBase):
    pass


class _Row(_Base):
    __tablename__ = "rows"
    id: Mapped[int] = mapped_column(primary_key=True)
    value: Mapped[str] = mapped_column()


@pytest.fixture
def tmp_manager():
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = SqliteShardManager(
            SqliteShardConfig(directory=tmpdir, metadata=_Base.metadata)
        )
        try:
            yield manager, tmpdir
        finally:
            manager.dispose_all()


# ── Lazy creation ───────────────────────────────────────────────────────────


def test_get_session_creates_the_shard_on_first_use(tmp_manager):
    manager, tmpdir = tmp_manager

    with manager.get_session("BTCUSDT"):
        pass

    assert (Path(tmpdir) / "BTCUSDT.db").exists()
    assert manager.list_shards() == ["BTCUSDT"]


def test_get_session_returns_a_new_session_each_call(tmp_manager):
    """Distinct sessions, so callers can hold independent transactions —
    unlike SqlAlchemyDatabaseManager, which hands back one shared adapter."""
    manager, _ = tmp_manager

    first = manager.get_session("BTCUSDT")
    second = manager.get_session("BTCUSDT")

    assert first is not second


def test_schema_is_created_so_the_shard_is_immediately_writable(tmp_manager):
    manager, _ = tmp_manager

    with manager.get_raw_session("BTCUSDT") as session:
        session.add(_Row(id=1, value="hello"))
        session.commit()

    with manager.get_raw_session("BTCUSDT") as session:
        assert session.get(_Row, 1).value == "hello"


def test_shards_are_isolated_from_each_other(tmp_manager):
    manager, _ = tmp_manager

    with manager.get_raw_session("BTCUSDT") as session:
        session.add(_Row(id=1, value="btc"))
        session.commit()

    with manager.get_raw_session("ETHUSDT") as session:
        assert session.get(_Row, 1) is None


def test_metadata_none_skips_schema_creation():
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = SqliteShardManager(SqliteShardConfig(directory=tmpdir, metadata=None))
        try:
            with manager.get_raw_session("NOSCHEMA") as session:
                with pytest.raises(sa.exc.OperationalError):
                    session.execute(sa.text("SELECT * FROM rows"))
        finally:
            manager.dispose_all()


# ── SQLite tuning (the part Elite relied on and never had a test for) ───────


def test_wal_and_synchronous_pragmas_are_applied_to_connections(tmp_manager):
    manager, _ = tmp_manager

    with manager.get_raw_session("BTCUSDT") as session:
        journal_mode = session.execute(sa.text("PRAGMA journal_mode")).scalar()
        synchronous = session.execute(sa.text("PRAGMA synchronous")).scalar()

    assert journal_mode.lower() == "wal"
    assert synchronous == 1  # NORMAL


def test_pragmas_can_be_disabled(tmp_manager):
    _, tmpdir = tmp_manager
    manager = SqliteShardManager(
        SqliteShardConfig(directory=tmpdir, metadata=_Base.metadata, pragmas=())
    )
    try:
        with manager.get_raw_session("NOPRAGMA") as session:
            journal_mode = session.execute(sa.text("PRAGMA journal_mode")).scalar()
        assert journal_mode.lower() != "wal"
    finally:
        manager.dispose_all()


def test_connect_args_actually_reach_the_driver(tmp_manager):
    """Proven by passing an argument `sqlite3.connect` rejects: if the config were
    silently dropped instead of forwarded, opening the shard would succeed."""
    _, tmpdir = tmp_manager
    manager = SqliteShardManager(
        SqliteShardConfig(directory=tmpdir, connect_args={"no_such_arg": 1})
    )
    try:
        # `create_engine` is lazy — the driver is only invoked on first connect.
        with pytest.raises(TypeError):
            manager.get_engine("BADARGS").connect()
    finally:
        manager.dispose_all()


def test_a_session_is_usable_from_another_thread(tmp_manager):
    manager, _ = tmp_manager
    manager.get_engine("BTCUSDT")  # create on main thread
    errors: list[Exception] = []

    def write() -> None:
        try:
            with manager.get_raw_session("BTCUSDT") as session:
                session.add(_Row(id=1, value="from-thread"))
                session.commit()
        except Exception as e:  # noqa: BLE001
            errors.append(e)

    thread = threading.Thread(target=write)
    thread.start()
    thread.join()

    assert errors == []


# ── Name validation and path safety ─────────────────────────────────────────


@pytest.mark.parametrize("bad_name", ["../etc/passwd", "a/b", "has space", "", "x.y"])
def test_invalid_shard_names_are_rejected(tmp_manager, bad_name):
    manager, _ = tmp_manager

    with pytest.raises(ValueError, match="Invalid shard name"):
        manager.get_session(bad_name)


def test_path_traversal_is_blocked_even_if_the_name_pattern_permits_it():
    """Defence in depth: a caller supplying a permissive `name_pattern` must still
    not be able to write outside `directory`."""
    import re

    with tempfile.TemporaryDirectory() as tmpdir:
        manager = SqliteShardManager(
            SqliteShardConfig(directory=tmpdir, name_pattern=re.compile(r"^.*$"))
        )
        try:
            with pytest.raises(PermissionError, match="Path traversal"):
                manager.get_session("../../../etc/passwd")
        finally:
            manager.dispose_all()


# ── list / remove / purge ───────────────────────────────────────────────────


def test_list_shards_reflects_files_on_disk_not_just_opened_ones(tmp_manager):
    manager, tmpdir = tmp_manager
    with manager.get_session("BTCUSDT"):
        pass

    # A shard left behind by a previous run — never opened by this instance.
    (Path(tmpdir) / "LEFTOVER.db").touch()

    assert manager.list_shards() == ["BTCUSDT", "LEFTOVER"]


def test_remove_shard_deletes_files_and_reports_true(tmp_manager):
    manager, tmpdir = tmp_manager
    with manager.get_session("BTCUSDT"):
        pass
    with manager.get_session("ETHUSDT"):
        pass

    assert manager.remove_shard("BTCUSDT") is True

    assert not (Path(tmpdir) / "BTCUSDT.db").exists()
    assert (Path(tmpdir) / "ETHUSDT.db").exists()
    assert manager.list_shards() == ["ETHUSDT"]


def test_remove_shard_removes_wal_sidecar_files(tmp_manager):
    manager, tmpdir = tmp_manager
    with manager.get_raw_session("BTCUSDT") as session:
        session.add(_Row(id=1, value="x"))
        session.commit()

    (Path(tmpdir) / "BTCUSDT.db-wal").touch()
    (Path(tmpdir) / "BTCUSDT.db-shm").touch()

    manager.remove_shard("BTCUSDT")

    assert not (Path(tmpdir) / "BTCUSDT.db-wal").exists()
    assert not (Path(tmpdir) / "BTCUSDT.db-shm").exists()


def test_remove_shard_on_unknown_name_reports_false(tmp_manager):
    manager, _ = tmp_manager

    assert manager.remove_shard("NEVEREXISTED") is False


def test_remove_database_raises_where_remove_shard_returns_false(tmp_manager):
    """`IDatabaseManager.remove_database` promises to raise; `remove_shard` reports."""
    manager, _ = tmp_manager

    with pytest.raises(DatabaseNotFoundError):
        manager.remove_database("NEVEREXISTED")


def test_purge_all_deletes_every_shard_and_returns_the_count(tmp_manager):
    manager, _ = tmp_manager
    with manager.get_session("SOLUSDT"):
        pass
    with manager.get_session("BNBUSDT"):
        pass

    assert manager.purge_all() == 2
    assert manager.list_shards() == []


def test_dispose_all_closes_engines_without_touching_disk(tmp_manager):
    manager, tmpdir = tmp_manager
    with manager.get_session("BTCUSDT"):
        pass

    manager.dispose_all()

    assert (Path(tmpdir) / "BTCUSDT.db").exists()
    assert manager.list_shards() == ["BTCUSDT"]  # still on disk, just not open


def test_vacuum_runs_for_one_shard_and_for_all(tmp_manager):
    manager, _ = tmp_manager
    with manager.get_session("XRPUSDT"):
        pass

    manager.vacuum("XRPUSDT")
    manager.vacuum()


# ── In-memory mode ──────────────────────────────────────────────────────────


def test_in_memory_shards_are_isolated_but_survive_reconnect():
    manager = SqliteShardManager(
        SqliteShardConfig(directory=IN_MEMORY, metadata=_Base.metadata)
    )
    try:
        with manager.get_raw_session("BTCUSDT") as session:
            session.add(_Row(id=1, value="btc"))
            session.commit()

        # Shared-cache URI: a second connection to the same shard sees the data.
        with manager.get_raw_session("BTCUSDT") as session:
            assert session.get(_Row, 1).value == "btc"

        # A different shard is a different database.
        with manager.get_raw_session("ETHUSDT") as session:
            assert session.get(_Row, 1) is None

        assert manager.list_shards() == ["BTCUSDT", "ETHUSDT"]
    finally:
        manager.dispose_all()


def test_in_memory_remove_shard_reports_whether_it_was_open():
    manager = SqliteShardManager(SqliteShardConfig(directory=IN_MEMORY))
    try:
        with manager.get_session("BTCUSDT"):
            pass

        assert manager.remove_shard("BTCUSDT") is True
        assert manager.remove_shard("BTCUSDT") is False
    finally:
        manager.dispose_all()


# ── IDatabaseManager conformance ────────────────────────────────────────────


def test_add_database_registers_an_explicit_url(tmp_manager):
    manager, tmpdir = tmp_manager
    manager.add_database("CUSTOM", f"sqlite:///{tmpdir}/elsewhere.db")

    assert manager.get_engine("CUSTOM") is not None


def test_add_database_rejects_a_duplicate_name(tmp_manager):
    manager, tmpdir = tmp_manager
    manager.add_database("CUSTOM", f"sqlite:///{tmpdir}/elsewhere.db")

    with pytest.raises(ValueError, match="already registered"):
        manager.add_database("CUSTOM", f"sqlite:///{tmpdir}/elsewhere.db")


def test_concurrent_get_session_on_distinct_shards_is_thread_safe(tmp_manager):
    manager, _ = tmp_manager
    errors: list[Exception] = []

    def touch(name: str) -> None:
        try:
            with manager.get_session(name):
                pass
        except Exception as e:  # noqa: BLE001
            errors.append(e)

    threads = [threading.Thread(target=touch, args=(f"S{i}",)) for i in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == []
    assert len(manager.list_shards()) == 20
