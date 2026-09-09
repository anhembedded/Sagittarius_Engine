"""`ContainerPresenter` — `EPIC-007E` §3, extended by `EPIC-008B` subtask D's
`openScopesClimbing` baseline comparison.

Same `Mock` container + real `MemoryEventBus` fixture
`test_overview_presenter.py` established -- no `QApplication`, no real
websocket, no QML."""

from __future__ import annotations

import os
from unittest.mock import Mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")

from sagittarius_engine.extensions.audit.contracts import (  # noqa: E402
    ContainerState,
    StateSnapshot,
)
from sagittarius_engine.infrastructure.event_bus.memory_event_bus import (  # noqa: E402
    MemoryEventBus,
)
from sagittarius_engine.interfaces import (  # noqa: E402
    IConfig,
    IDispatcher,
    IEventBus,
    ILogger,
)
from tools.state_console.domain.events import (  # noqa: E402
    ConsoleAttached,
    SnapshotReceived,
)
from tools.state_console.presentation.container.container_presenter import (  # noqa: E402
    ContainerPresenter,
)


@pytest.fixture
def container_with_bus():
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


@pytest.fixture
def presenter(container_with_bus):
    container, bus = container_with_bus
    p = ContainerPresenter(Mock(), container)
    try:
        yield p, bus
    finally:
        p.dispose()


def test_the_first_snapshot_after_attach_is_never_climbing(presenter):
    p, bus = presenter
    bus.emit(SnapshotReceived(StateSnapshot(container=ContainerState(open_scopes=30))))

    assert p.view_model.openScopesClimbing is False


def test_climbing_above_the_post_attach_baseline(presenter):
    p, bus = presenter
    bus.emit(SnapshotReceived(StateSnapshot(container=ContainerState(open_scopes=5))))
    bus.emit(SnapshotReceived(StateSnapshot(container=ContainerState(open_scopes=12))))

    assert p.view_model.openScopesClimbing is True


def test_holding_steady_at_or_below_the_baseline_is_not_climbing(presenter):
    p, bus = presenter
    bus.emit(SnapshotReceived(StateSnapshot(container=ContainerState(open_scopes=5))))
    bus.emit(SnapshotReceived(StateSnapshot(container=ContainerState(open_scopes=5))))
    bus.emit(SnapshotReceived(StateSnapshot(container=ContainerState(open_scopes=2))))

    assert p.view_model.openScopesClimbing is False


def test_a_fresh_attach_resets_the_baseline(presenter):
    """A stale baseline from a previous, unrelated connection must not
    make a brand-new attach's own first reading look like it climbed."""
    p, bus = presenter
    bus.emit(SnapshotReceived(StateSnapshot(container=ContainerState(open_scopes=2))))
    bus.emit(SnapshotReceived(StateSnapshot(container=ContainerState(open_scopes=40))))
    assert p.view_model.openScopesClimbing is True

    bus.emit(ConsoleAttached())
    bus.emit(SnapshotReceived(StateSnapshot(container=ContainerState(open_scopes=40))))

    assert p.view_model.openScopesClimbing is False
