from unittest.mock import Mock

import pytest

from sagittarius_engine.base import BaseModule
from sagittarius_engine.exceptions import ModuleRegistrationError
from sagittarius_engine.extensions.cqrs import ICommand, IQuery
from sagittarius_engine.infrastructure.container.std_container import (
    DependencyResolutionError,
    StdLibContainer,
)
from sagittarius_engine.infrastructure.event_bus.memory_event_bus import MemoryEventBus
from sagittarius_engine.interfaces import IEventBus
from sagittarius_engine.kernel import App


def test_event_bus_emit_on_off():
    bus = MemoryEventBus()
    handler = Mock()

    bus.on("test_event", handler)
    bus.emit("test_event", {"data": "value"})
    handler.assert_called_once_with({"data": "value"})

    bus.off("test_event", handler)
    bus.emit("test_event", {"data": "value_2"})
    assert handler.call_count == 1  # Should not be called again


def test_container_singleton():
    container = StdLibContainer()

    class MyDependency:
        pass

    dep = MyDependency()
    container.singleton(MyDependency, dep)
    resolved = container.resolve(MyDependency)
    assert resolved is dep


def test_container_binding_resolution():
    container = StdLibContainer()

    class IService:
        pass

    class ServiceImpl(IService):
        pass

    container.bind(IService, ServiceImpl)
    resolved = container.resolve(IService)
    assert isinstance(resolved, ServiceImpl)


def test_container_auto_resolution():
    container = StdLibContainer()

    class Dependency:
        pass

    class Service:
        def __init__(self, dep: Dependency):
            self.dep = dep

    resolved = container.resolve(Service)
    assert isinstance(resolved, Service)
    assert isinstance(resolved.dep, Dependency)


def test_container_missing_typehint_fails():
    container = StdLibContainer()

    class BadService:
        def __init__(self, untyped_dep):
            pass

    with pytest.raises(DependencyResolutionError, match="Missing type hint"):
        container.resolve(BadService)


def test_app_use_module():
    container = StdLibContainer()
    event_bus = MemoryEventBus()
    app = App(container=container, event_bus=event_bus)

    class MyModule(BaseModule):
        def register(self, a: App):
            a.container.singleton("custom", "registered")  # type: ignore[arg-type]  # type: ignore[arg-type]  # type: ignore[arg-type]  # type: ignore[arg-type]

        def boot(self, a: App):
            pass

    module = MyModule()
    app.use(module)
    assert "custom" in app.container._instances
    assert app.container.resolve("custom") == "registered"


def test_app_use_invalid_module():
    container = StdLibContainer()
    event_bus = MemoryEventBus()
    app = App(container=container, event_bus=event_bus)
    with pytest.raises(ModuleRegistrationError):
        app.use(object())  # Not an IModule


def test_app_boot():
    container = StdLibContainer()
    event_bus = MemoryEventBus()
    app = App(container=container, event_bus=event_bus)
    handler = Mock()
    app.event_bus.on("app.booted", handler)

    boot_mock = Mock()

    class MyModule(BaseModule):
        def boot(self, a: App):
            boot_mock()

    app.use(MyModule())
    app.boot()

    boot_mock.assert_called_once()
    handler.assert_called_once_with(app)


def test_app_execute_command():
    container = StdLibContainer()
    event_bus = MemoryEventBus()
    app = App(container=container, event_bus=event_bus)

    class DummyCommand(ICommand):
        def __init__(self, event_bus: IEventBus):
            self.event_bus = event_bus

        def execute(self, input_dto: dict):
            return "executed"

    container.bind(DummyCommand, DummyCommand)
    container.singleton(IEventBus, event_bus)

    result = app.dispatch(DummyCommand, {})
    assert result == "executed"


def test_app_execute_query():
    container = StdLibContainer()
    event_bus = MemoryEventBus()
    app = App(container=container, event_bus=event_bus)

    class DummyQuery(IQuery):
        def __init__(self, event_bus: IEventBus):
            self.event_bus = event_bus

        def execute(self, input_dto: dict):
            return "queried"

    container.bind(DummyQuery, DummyQuery)
    container.singleton(IEventBus, event_bus)

    result = app.dispatch(DummyQuery, {})
    assert result == "queried"


def test_kernel_facade_and_components():
    from sagittarius_engine.kernel import (
        Bootstrap,
        Dispatcher,
        EngineContext,
        EngineLifecycle,
        ModuleLoader,
    )
    from sagittarius_engine.utils.null_logger import NullLogger

    container = StdLibContainer()
    event_bus = MemoryEventBus()
    app = App(container=container, event_bus=event_bus)

    # 1. Verify EngineContext composition
    assert app.context.container is container
    assert app.context.event_bus is event_bus
    assert app.container is container
    assert app.event_bus is event_bus
    assert isinstance(app.context.logger, NullLogger)  # Falls back to NullLogger
    assert app.context.config is None  # not bound yet

    # 2. Verify EngineLifecycle state transitions
    # EPIC-006C: a freshly constructed app is CREATED, not STOPPED — "never
    # started" and "has been shut down" are different answers to the only
    # question anything monitoring an engine asks first.
    assert app.lifecycle.is_created
    assert not app.lifecycle.is_stopped
    assert not app.lifecycle.is_booting
    assert not app.lifecycle.is_booted

    app.boot()
    assert app.lifecycle.is_booted
    assert not app.lifecycle.is_stopped

    # 3. Verify Docstrings
    assert (
        App.__doc__ is not None
        and "The public façade of the Sagittarius Engine." in App.__doc__
    )
    assert (
        EngineContext.__doc__ is not None
        and "The runtime composition root of the Sagittarius Engine."
        in EngineContext.__doc__
    )
    assert (
        Bootstrap.__doc__ is not None
        and "Responsible for bootstrapping the engine." in Bootstrap.__doc__
    )
    assert (
        Dispatcher.__doc__ is not None
        and "Responsible for executing handlers through the middleware pipeline."
        in Dispatcher.__doc__
    )
    # Reworded by EPIC-006C, which gave this class the `app.ready` milestone
    # on top of the state it already owned.
    assert (
        EngineLifecycle.__doc__ is not None
        and "Owns the engine's state" in EngineLifecycle.__doc__
    )
    assert (
        ModuleLoader.__doc__ is not None
        and "Responsible for discovering and loading engine extensions."
        in ModuleLoader.__doc__
    )
