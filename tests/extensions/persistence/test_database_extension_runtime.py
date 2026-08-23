"""
[Integration Test — EPIC-003C]

Proves the mechanism a later Elite Warrior migration would depend on: a consumer
resolves `IDatabaseManager` from the container *after* `DatabaseExtension.register()`
has already run (i.e., at real runtime, not during setup), and can add/remove named
databases dynamically — mirroring shards being created/destroyed per trading symbol.
"""

import pytest

from sagittarius_engine import App
from sagittarius_engine.extensions.persistence import (
    DatabaseNotFoundError,
    IDatabaseManager,
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
