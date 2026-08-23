from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import Engine

from sagittarius_engine.exceptions import DependencyResolutionError
from sagittarius_engine.extensions.persistence.database_module import DatabaseExtension
from sagittarius_engine.extensions.persistence.i_database_manager import (
    DatabaseNotFoundError,
    IDatabaseManager,
)
from sagittarius_engine.extensions.persistence.i_session import ISession
from sagittarius_engine.infrastructure import StdLibContainer
from sagittarius_engine.infrastructure.config.dict_config import DictConfig
from sagittarius_engine.interfaces import IConfig
from sagittarius_engine.interfaces.i_logger import ILogger


def _container_with_config(config_values: dict) -> StdLibContainer:
    container = StdLibContainer()
    container.singleton(IConfig, DictConfig(config_values))
    return container


def test_database_module_no_sqlalchemy():
    with patch(
        "sagittarius_engine.extensions.persistence.database_module.SQLALCHEMY_INSTALLED",
        False,
    ):
        extension = DatabaseExtension()
        mock_app = MagicMock()
        mock_logger = MagicMock()
        mock_app.container.resolve.return_value = mock_logger

        extension.register(mock_app)
        mock_logger.warning.assert_called()


def test_legacy_database_url_registers_isession_and_engine_and_manager():
    container = _container_with_config({"database.url": "sqlite:///:memory:"})
    context = MagicMock(container=container)

    DatabaseExtension().register(context)

    session = container.resolve(ISession)
    engine = container.resolve(Engine)
    manager = container.resolve(IDatabaseManager)

    assert session is not None
    assert engine is not None
    assert manager.get_session("default") is session
    assert manager.get_engine("default") is engine
    assert manager.names() == ["default"]


def test_missing_database_url_falls_back_to_in_memory_sqlite_in_development():
    container = _container_with_config({})
    context = MagicMock(container=container)

    DatabaseExtension().register(context)

    manager = container.resolve(IDatabaseManager)
    assert manager.names() == ["default"]
    assert container.resolve(ISession) is not None


def test_missing_database_url_raises_in_production():
    container = _container_with_config({"env": "production"})
    context = MagicMock(container=container)

    with pytest.raises(ValueError, match="production environment"):
        DatabaseExtension().register(context)


def test_database_shards_registers_manager_without_default_isession():
    container = _container_with_config(
        {
            "database.shards": {
                "BTCUSDT": "sqlite:///:memory:",
                "ETHUSDT": "sqlite:///:memory:",
            }
        }
    )
    context = MagicMock(container=container)

    DatabaseExtension().register(context)

    manager = container.resolve(IDatabaseManager)
    assert set(manager.names()) == {"BTCUSDT", "ETHUSDT"}

    # Ambiguous which shard "the" ISession/Engine would mean — deliberately not registered.
    with pytest.raises(DependencyResolutionError):
        container.resolve(ISession)
    with pytest.raises(DependencyResolutionError):
        container.resolve(Engine)


def test_database_shards_missing_key_raises_database_not_found():
    container = _container_with_config(
        {"database.shards": {"BTCUSDT": "sqlite:///:memory:"}}
    )
    context = MagicMock(container=container)
    DatabaseExtension().register(context)

    manager = container.resolve(IDatabaseManager)
    with pytest.raises(DatabaseNotFoundError):
        manager.get_session("UNKNOWN")


def test_config_resolution_failure_falls_back_to_in_memory_sqlite_in_development():
    container = StdLibContainer()  # no IConfig registered at all
    context = MagicMock(container=container)

    DatabaseExtension().register(context)

    manager = container.resolve(IDatabaseManager)
    assert manager.names() == ["default"]


def test_config_resolution_failure_raises_in_production():
    container = StdLibContainer()  # no IConfig registered at all
    context = MagicMock(container=container)

    with (
        patch.dict("os.environ", {"ENV": "production"}),
        pytest.raises(ValueError, match="production"),
    ):
        DatabaseExtension().register(context)


def test_logger_receives_info_message_on_successful_legacy_registration():
    container = _container_with_config({"database.url": "sqlite:///:memory:"})
    mock_logger = MagicMock(spec=ILogger)
    # A MagicMock is callable, and StdLibContainer.singleton() treats any callable as a
    # lazy factory (see std_container.py) — wrap it so the container stores the instance
    # itself rather than calling it once and caching the (unrelated) return value.
    container.singleton(ILogger, lambda c: mock_logger)
    context = MagicMock(container=container)

    DatabaseExtension().register(context)

    mock_logger.info.assert_called()
