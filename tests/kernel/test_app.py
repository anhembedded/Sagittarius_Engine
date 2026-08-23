import inspect
import unittest.mock
from unittest.mock import MagicMock

import pytest

from sagittarius_engine.exceptions import ModuleRegistrationError
from sagittarius_engine.interfaces import (
    IContainer,
    IEventBus,
    IExtension,
    ILogger,
    IMiddleware,
)
from sagittarius_engine.kernel.app import App
from sagittarius_engine.kernel.context import EngineContext


def test_app_snippet_init():
    """Test the exact behavior of the App.__init__ snippet."""
    # Check if we are running against the original production code
    sig = inspect.signature(App.__init__)
    if "event_bus" in sig.parameters:
        pytest.skip("Original production code detected.")

    container_mock = MagicMock(spec=IContainer)
    app = App(container=container_mock)

    assert getattr(app, "_container", None) is container_mock


def test_app_production_init():
    """Test the original production code's __init__ method."""
    sig = inspect.signature(App.__init__)
    if "event_bus" not in sig.parameters:
        pytest.skip("Snippet code detected.")

    container_mock = MagicMock(spec=IContainer)
    event_bus_mock = MagicMock(spec=IEventBus)

    # Using patch to avoid actually instantiating EngineContext
    with unittest.mock.patch(
        "sagittarius_engine.kernel.app.EngineContext"
    ) as mock_context:
        app = App(container=container_mock, event_bus=event_bus_mock)

        mock_context.assert_called_once_with(app, container_mock, event_bus_mock)
        assert app.context == mock_context.return_value


def test_app_properties():
    app = App.__new__(App)
    app.context = MagicMock(spec=EngineContext)
    app.context.container = MagicMock(spec=IContainer)
    app.context.event_bus = MagicMock(spec=IEventBus)
    app.context.modules = [MagicMock(spec=IExtension)]
    app.context.middleware_pipeline = MagicMock()
    app.context.lifecycle = MagicMock()

    assert app.container is app.context.container
    assert app.event_bus is app.context.event_bus
    assert app.modules is app.context.modules
    assert app.pipeline is app.context.middleware_pipeline
    assert app.lifecycle is app.context.lifecycle


def test_app_use_success():
    app = App.__new__(App)
    app.context = MagicMock()
    app.context.extension_manager = MagicMock()

    extension_mock = MagicMock(spec=IExtension)
    app.use(extension_mock)

    app.context.extension_manager.register.assert_called_once_with(extension_mock)


def test_app_use_type_error():
    app = App.__new__(App)
    app.context = MagicMock()
    app.context.extension_manager = MagicMock()
    app.context.extension_manager.register.side_effect = TypeError("Invalid module")

    extension_mock = MagicMock(spec=IExtension)

    with pytest.raises(ModuleRegistrationError, match="Invalid module"):
        app.use(extension_mock)


def test_app_use_middleware():
    app = App.__new__(App)
    app.context = MagicMock()
    app.context.middleware_pipeline = MagicMock()

    middleware_mock = MagicMock(spec=IMiddleware)
    app.use_middleware(middleware_mock)

    app.context.middleware_pipeline.add.assert_called_once_with(middleware_mock)


def test_app_get_logger():
    app = App.__new__(App)
    app.context = MagicMock()
    logger_mock = MagicMock(spec=ILogger)
    app.context.logger = logger_mock

    assert app._get_logger() is logger_mock


def test_app_boot():
    app = App.__new__(App)
    app.context = MagicMock()
    app.context.bootstrap = MagicMock()

    app.boot("some_path")

    app.context.bootstrap.boot.assert_called_once_with("some_path")


def test_app_dispatch():
    app = App.__new__(App)
    app.context = MagicMock()
    app.context.dispatcher = MagicMock()
    app.context.dispatcher.dispatch.return_value = "result"

    handler_class = MagicMock()
    input_dto = MagicMock()

    result = app.dispatch(handler_class, input_dto)

    assert result == "result"
    app.context.dispatcher.dispatch.assert_called_once_with(handler_class, input_dto)


def test_app_execute_deprecated():
    app = App.__new__(App)
    app.context = MagicMock()
    app.context.dispatcher = MagicMock()
    app.context.dispatcher.dispatch.return_value = "result"

    command_class = MagicMock()
    input_dto = MagicMock()

    with pytest.warns(
        DeprecationWarning, match="App.execute is deprecated. Use App.dispatch instead."
    ):
        result = app.execute(command_class, input_dto)

    assert result == "result"
    app.context.dispatcher.dispatch.assert_called_once_with(command_class, input_dto)


def test_app_query_deprecated():
    app = App.__new__(App)
    app.context = MagicMock()
    app.context.dispatcher = MagicMock()
    app.context.dispatcher.dispatch.return_value = "result"

    query_class = MagicMock()
    input_dto = MagicMock()

    with pytest.warns(
        DeprecationWarning, match="App.query is deprecated. Use App.dispatch instead."
    ):
        result = app.query(query_class, input_dto)

    assert result == "result"
    app.context.dispatcher.dispatch.assert_called_once_with(query_class, input_dto)


def test_app_stop_already_stopped():
    app = App.__new__(App)
    app.context = MagicMock()
    app.context.lifecycle.is_stopping = True
    app.context.lifecycle.is_stopped = False

    app.stop()

    app.context.lifecycle.set_stopping.assert_not_called()


def test_app_stop_success():
    app = App.__new__(App)
    app.context = MagicMock()
    app.context.lifecycle.is_stopping = False
    app.context.lifecycle.is_stopped = False
    logger_mock = MagicMock(spec=ILogger)
    app.context.logger = logger_mock

    app.stop()

    app.context.lifecycle.set_stopping.assert_called_once()
    app.context.scheduler.stop.assert_called_once()
    app.context.hosted_services.stop.assert_called_once()
    app.context.extension_manager.stop_and_dispose.assert_called_once()
    app.context.tasks.shutdown.assert_called_once()
    app.context.async_runtime.stop.assert_called_once()
    app.context.event_bus.shutdown.assert_called_once()
    app.context.lifecycle.set_stopped.assert_called_once()
    assert (
        logger_mock.info.call_count == 2
    )  # App is stopping gracefully... and App stopped.


def test_app_stop_exceptions_logged():
    app = App.__new__(App)
    app.context = MagicMock()
    app.context.lifecycle.is_stopping = False
    app.context.lifecycle.is_stopped = False
    logger_mock = MagicMock(spec=ILogger)
    app.context.logger = logger_mock

    # Give all components side effects to raise exceptions
    app.context.scheduler.stop.side_effect = Exception("scheduler error")
    app.context.hosted_services.stop.side_effect = Exception("hosted services error")
    app.context.extension_manager.stop_and_dispose.side_effect = Exception(
        "extension error"
    )
    app.context.tasks.shutdown.side_effect = Exception("tasks error")
    app.context.async_runtime.stop.side_effect = Exception("async runtime error")
    app.context.event_bus.shutdown.side_effect = Exception("event bus error")

    app.stop()

    assert logger_mock.error.call_count == 6


def test_app_stop_completes_despite_a_rogue_hanging_extension():
    """@brief TASK-017 issue 7 regression: a step that hangs (e.g. a rogue
    extension's stop()) must not block App.stop() from completing, and every
    later step must still run."""
    import threading
    import time

    app = App.__new__(App)
    app.context = MagicMock()
    app.context.lifecycle.is_stopping = False
    app.context.lifecycle.is_stopped = False
    logger_mock = MagicMock(spec=ILogger)
    app.context.logger = logger_mock

    release_rogue = threading.Event()

    def rogue_extension_stop():
        # Simulates an extension whose stop() never returns in time.
        release_rogue.wait(timeout=5.0)

    app.context.extension_manager.stop_and_dispose.side_effect = rogue_extension_stop

    started_at = time.monotonic()
    app.stop(step_timeout=0.2)
    elapsed = time.monotonic() - started_at

    try:
        assert elapsed < 2.0, f"App.stop() blocked for {elapsed}s on the rogue step"
        # Every step after the rogue one must still have run.
        app.context.tasks.shutdown.assert_called_once()
        app.context.async_runtime.stop.assert_called_once()
        app.context.event_bus.shutdown.assert_called_once()
        app.context.lifecycle.set_stopped.assert_called_once()
        assert any(
            "did not stop within" in str(call.args[0])
            for call in logger_mock.error.call_args_list
        )
    finally:
        release_rogue.set()  # let the rogue thread exit instead of leaking it
    app.context.lifecycle.set_stopped.assert_called_once()
