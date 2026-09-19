from typing import Any

import pytest

from sagittarius_engine.infrastructure.container.std_container import StdLibContainer
from sagittarius_engine.infrastructure.event_bus import IPCBroker, IPCQueueEventBus
from sagittarius_engine.infrastructure.event_bus.memory_event_bus import MemoryEventBus
from sagittarius_engine.infrastructure.event_bus.thread_pool_event_bus import (
    ThreadPoolEventBus,
)
from sagittarius_engine.kernel import App


class TrackedMemoryEventBus(MemoryEventBus):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.emitted_events = []

    def emit(self, event_name_or_obj: str | Any, data: Any = None) -> None:
        self.emitted_events.append((event_name_or_obj, data))
        super().emit(event_name_or_obj, data)


@pytest.fixture
def container():
    return StdLibContainer()


@pytest.fixture
def event_bus():
    return TrackedMemoryEventBus()


@pytest.fixture
def app(container, event_bus):
    return App(container=container, event_bus=event_bus)


@pytest.fixture
def app_factory():
    """`BUG-014`: `Bootstrap.boot()` unconditionally starts both `Scheduler`
    and `AsyncRuntime` background threads. A test that constructs an `App`,
    calls `.boot()`, and never calls `.stop()` leaks that thread pair for the
    rest of the process -- audited across the suite as the dominant source of
    the leaked-thread segfault, not occasional slow joins. Same
    tracked-factory-with-teardown pattern as `thread_pool_bus_factory`/
    `ipc_broker_factory` above: every `App` built through this fixture is
    stopped in teardown regardless of whether the test itself reached a
    `.stop()` call or failed an assertion first.
    """
    apps: list[App] = []

    def _factory(container=None, event_bus=None) -> App:
        app = App(container or StdLibContainer(), event_bus or MemoryEventBus())
        apps.append(app)
        return app

    yield _factory

    for app in apps:
        app.stop()


@pytest.fixture
def thread_pool_bus_factory():
    buses = []

    def _factory(*args, **kwargs):
        bus = ThreadPoolEventBus(*args, **kwargs)
        buses.append(bus)
        return bus

    yield _factory

    for bus in buses:
        bus.shutdown()


@pytest.fixture
def ipc_broker_factory():
    brokers = []

    def _factory(*args, **kwargs):
        broker = IPCBroker(*args, **kwargs)
        brokers.append(broker)
        return broker

    yield _factory

    for broker in brokers:
        broker.stop()


@pytest.fixture
def ipc_bus_factory():
    buses = []

    def _factory(*args, **kwargs):
        bus = IPCQueueEventBus(*args, **kwargs)
        buses.append(bus)
        return bus

    yield _factory

    for bus in buses:
        bus.stop()
