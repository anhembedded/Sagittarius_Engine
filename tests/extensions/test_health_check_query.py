from unittest.mock import MagicMock, patch

from sagittarius_engine.extensions.health.health_check_query import HealthCheckQuery
from sagittarius_engine.extensions.persistence import ISession
from sagittarius_engine.interfaces import IContainer, IEventBus


def test_health_check_query_healthy():
    mock_container = MagicMock(spec=IContainer)
    mock_event_bus = MagicMock(spec=IEventBus)
    mock_session = MagicMock(spec=ISession)

    # Configure container to return mock_session for ISession, and mock_container for IContainer
    def resolve_side_effect(interface):
        if interface == IContainer:
            return mock_container
        if interface == ISession:
            return mock_session
        raise Exception("Unexpected resolve")

    mock_container.resolve.side_effect = resolve_side_effect
    mock_event_bus.emit = MagicMock()

    # Mock sqlalchemy
    with patch.dict("sys.modules", {"sqlalchemy": MagicMock()}):
        query = HealthCheckQuery(container=mock_container, event_bus=mock_event_bus)
        result = query.execute()

        assert result["status"] == "healthy"
        assert result["components"]["container"] == "ok"
        assert result["components"]["event_bus"] == "ok"
        assert result["components"]["database"] == "ok"
        mock_session.execute.assert_called_once()


def test_health_check_query_unhealthy_container():
    mock_container = MagicMock(spec=IContainer)
    mock_event_bus = MagicMock(spec=IEventBus)
    mock_session = MagicMock(spec=ISession)

    def resolve_side_effect(interface):
        if interface == IContainer:
            raise Exception("Container error")
        if interface == ISession:
            return mock_session
        raise Exception("Unexpected resolve")

    mock_container.resolve.side_effect = resolve_side_effect
    mock_event_bus.emit = MagicMock()

    with patch.dict("sys.modules", {"sqlalchemy": MagicMock()}):
        query = HealthCheckQuery(container=mock_container, event_bus=mock_event_bus)
        result = query.execute()

        assert result["status"] == "unhealthy"
        assert result["components"]["container"] == "error: container resolution failed"
        assert result["components"]["event_bus"] == "ok"
        assert result["components"]["database"] == "ok"


def test_health_check_query_unhealthy_event_bus():
    mock_container = MagicMock(spec=IContainer)
    mock_event_bus = object()  # No emit method
    mock_session = MagicMock(spec=ISession)

    def resolve_side_effect(interface):
        if interface == IContainer:
            return mock_container
        if interface == ISession:
            return mock_session
        raise Exception("Unexpected resolve")

    mock_container.resolve.side_effect = resolve_side_effect

    with patch.dict("sys.modules", {"sqlalchemy": MagicMock()}):
        query = HealthCheckQuery(container=mock_container, event_bus=mock_event_bus)
        result = query.execute()

        assert result["status"] == "unhealthy"
        assert result["components"]["container"] == "ok"
        assert result["components"]["event_bus"] == "error: event bus check failed"
        assert result["components"]["database"] == "ok"


def test_health_check_query_database_not_configured():
    mock_container = MagicMock(spec=IContainer)
    mock_event_bus = MagicMock(spec=IEventBus)

    def resolve_side_effect(interface):
        if interface == IContainer:
            return mock_container
        if interface == ISession:
            raise Exception("No DB configured")
        raise Exception("Unexpected resolve")

    mock_container.resolve.side_effect = resolve_side_effect
    mock_event_bus.emit = MagicMock()

    with patch.dict("sys.modules", {"sqlalchemy": MagicMock()}):
        query = HealthCheckQuery(container=mock_container, event_bus=mock_event_bus)
        result = query.execute()

        assert (
            result["status"] == "healthy"
        )  # Overall status doesn't change on exception for DB configuration
        assert result["components"]["container"] == "ok"
        assert result["components"]["event_bus"] == "ok"
        assert result["components"]["database"] == "not configured"


def test_health_check_query_sqlalchemy_not_installed():
    mock_container = MagicMock(spec=IContainer)
    mock_event_bus = MagicMock(spec=IEventBus)
    mock_session = MagicMock(spec=ISession)

    def resolve_side_effect(interface):
        if interface == IContainer:
            return mock_container
        if interface == ISession:
            return mock_session
        raise Exception("Unexpected resolve")

    mock_container.resolve.side_effect = resolve_side_effect
    mock_event_bus.emit = MagicMock()

    # Ensure sqlalchemy cannot be imported by setting it to None in sys.modules
    with patch.dict("sys.modules", {"sqlalchemy": None}):
        query = HealthCheckQuery(container=mock_container, event_bus=mock_event_bus)
        result = query.execute()

        assert result["status"] == "unhealthy"
        assert result["components"]["container"] == "ok"
        assert result["components"]["event_bus"] == "ok"
        assert result["components"]["database"] == "sqlalchemy not installed"


def test_health_check_query_database_connection_failed():
    mock_container = MagicMock(spec=IContainer)
    mock_event_bus = MagicMock(spec=IEventBus)
    mock_session = MagicMock(spec=ISession)
    mock_session.execute.side_effect = Exception("Connection failed")

    def resolve_side_effect(interface):
        if interface == IContainer:
            return mock_container
        if interface == ISession:
            return mock_session
        raise Exception("Unexpected resolve")

    mock_container.resolve.side_effect = resolve_side_effect
    mock_event_bus.emit = MagicMock()

    with patch.dict("sys.modules", {"sqlalchemy": MagicMock()}):
        query = HealthCheckQuery(container=mock_container, event_bus=mock_event_bus)
        result = query.execute()

        assert result["status"] == "unhealthy"
        assert result["components"]["container"] == "ok"
        assert result["components"]["event_bus"] == "ok"
        assert result["components"]["database"] == "database connection failed"
