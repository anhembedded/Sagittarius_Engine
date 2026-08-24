"""`BasePresenter` lifecycle — subscription cleanup and the abstract-method
contract (EPIC-008D).

Two defects this locks down, both found auditing the reference consuming
app's event flow on 2026-08-24:

1. **`on()` with no `off()`.** The whole app called `event_bus.on(...)` and
   never once called `off()`. It has not leaked in production only because
   `PresenterManager` builds each presenter once and keeps it until the
   process ends — but a test that builds a presenter repeatedly accumulates
   handlers on the container's shared bus, so the previous test's presenter
   keeps handling events during the next one.
2. **`raise NotImplementedError` on inherited methods.** `code-rule.md`'s
   Liskov rule forbids exactly that, and the cost was visible: a Settings
   screen with nothing to subscribe to still had to override
   `_connect_engine_events()` with an empty body purely to avoid an
   exception.
"""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from sagittarius_engine.extensions.pyside_mvc.mvc.base_presenter import BasePresenter
from sagittarius_engine.infrastructure.event_bus.memory_event_bus import MemoryEventBus
from sagittarius_engine.interfaces import (
    IConfig,
    IDispatcher,
    IEventBus,
    ILogger,
)

_EVENT = "some.event"


@pytest.fixture
def container_with_bus():
    """A container returning real collaborators where the behaviour under
    test depends on them (the bus) and mocks where it does not."""
    bus = MemoryEventBus()
    config = Mock()
    config.get.return_value = False
    config.get_all.return_value = {}

    def resolve(interface):
        return {
            IEventBus: bus,
            ILogger: Mock(),
            IDispatcher: Mock(),
            IConfig: config,
        }[interface]

    container = Mock()
    container.resolve.side_effect = resolve
    return container, bus


def test_a_presenter_that_overrides_nothing_can_be_constructed(container_with_bus):
    """`_connect_ui_signals`/`_connect_engine_events` must be no-ops by
    default, not `NotImplementedError`. A screen with nothing to subscribe to
    is a valid screen, not a programming error."""
    container, _bus = container_with_bus

    class _Bare(BasePresenter):
        pass

    presenter = _Bare(Mock(), container)
    presenter._connect_ui_signals()
    presenter._connect_engine_events()


def test_subscriptions_made_through_the_presenter_are_removed_on_dispose(
    container_with_bus,
):
    container, bus = container_with_bus

    class _Subscribing(BasePresenter):
        def __init__(self, view, container):
            super().__init__(view, container)
            self.received: list[object] = []
            self._connect_engine_events()

        def _connect_engine_events(self) -> None:
            self.subscribe(_EVENT, self.received.append)

    presenter = _Subscribing(Mock(), container)
    bus.emit(_EVENT, "before")
    assert presenter.received == ["before"]

    presenter.dispose()

    assert bus.get_handlers(_EVENT) == ()
    bus.emit(_EVENT, "after")
    assert presenter.received == ["before"], (
        "A disposed presenter must stop receiving events."
    )


def test_dispose_calls_the_subclass_shutdown_hook(container_with_bus):
    """`dispose()` is the framework-owned teardown; `shutdown()` stays the
    author-owned hook the consuming app already implements. A subclass that
    overrides `shutdown()` must not accidentally cancel the framework's own
    unsubscribe by doing so."""
    container, bus = container_with_bus

    class _WithShutdown(BasePresenter):
        def __init__(self, view, container):
            super().__init__(view, container)
            self.shutdown_calls = 0
            self.subscribe(_EVENT, lambda _p: None)

        def shutdown(self) -> None:
            self.shutdown_calls += 1

    presenter = _WithShutdown(Mock(), container)

    presenter.dispose()

    assert presenter.shutdown_calls == 1
    assert bus.get_handlers(_EVENT) == ()


def test_dispose_is_idempotent(container_with_bus):
    container, bus = container_with_bus

    class _Subscribing(BasePresenter):
        def __init__(self, view, container):
            super().__init__(view, container)
            self.shutdown_calls = 0
            self.subscribe(_EVENT, lambda _p: None)

        def shutdown(self) -> None:
            self.shutdown_calls += 1

    presenter = _Subscribing(Mock(), container)

    presenter.dispose()
    presenter.dispose()

    assert presenter.shutdown_calls == 1


def test_repeatedly_building_presenters_does_not_accumulate_handlers(
    container_with_bus,
):
    """The concrete cost of never calling `off()`: on a container-scoped bus,
    each rebuilt presenter used to stack another handler, so an event fired
    once was handled N times."""
    container, bus = container_with_bus
    calls: list[int] = []

    class _Subscribing(BasePresenter):
        def __init__(self, view, container):
            super().__init__(view, container)
            self.subscribe(_EVENT, lambda _p: calls.append(1))

    for _ in range(3):
        presenter = _Subscribing(Mock(), container)
        presenter.dispose()

    bus.emit(_EVENT, None)

    assert calls == []
    assert bus.get_handlers(_EVENT) == ()
