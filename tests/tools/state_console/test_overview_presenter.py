"""`OverviewPresenter` — `EPIC-007E` §3/§4, extended by `EPIC-008B` §4's
modules/signal-counts/snapshots-received fields.

A `Mock` container + a real `MemoryEventBus`, the same lightweight fixture
`test_base_presenter_lifecycle.py` already established for `BasePresenter`
subclasses that need real event delivery but nothing else Qt-heavy -- no
`QApplication`, no real websocket, no QML. `_thread_pool_row()` and the
event handlers are plain data transforms; this is where they earn direct
coverage instead of only through the QML screen test."""

from __future__ import annotations

import os
from unittest.mock import Mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")

from sagittarius_engine.extensions.audit.contracts import (  # noqa: E402
    EventState,
    LifecycleState,
    ModuleState,
    StateSnapshot,
    ThreadPoolStats,
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
from tools.state_console.presentation.overview.overview_presenter import (  # noqa: E402
    OverviewPresenter,
)
from tools.state_console.presentation.overview.overview_view_model import (  # noqa: E402
    ATTACHED_READING,
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
def presenter(container_with_bus, qtbot):
    container, bus = container_with_bus
    view = Mock()
    p = OverviewPresenter(view, container)
    try:
        yield p, bus
    finally:
        p.dispose()


def test_a_snapshot_populates_modules_from_lifecycle(presenter):
    p, bus = presenter
    snapshot = StateSnapshot(
        lifecycle=LifecycleState(
            state="ready",
            extensions_registered=2,
            extensions_initialized=1,
            modules=(
                ModuleState(name="A", ready=True),
                ModuleState(name="B", ready=False),
            ),
        )
    )

    bus.emit(SnapshotReceived(snapshot))

    assert p.view_model.modules == [
        {"name": "A", "ready": True},
        {"name": "B", "ready": False},
    ]
    assert p.view_model.connectionState == ATTACHED_READING


def test_snapshots_received_counts_up_and_resets_on_reattach(presenter):
    p, bus = presenter

    bus.emit(SnapshotReceived(StateSnapshot()))
    bus.emit(SnapshotReceived(StateSnapshot()))
    assert p.view_model.snapshotsReceived == 2

    bus.emit(ConsoleAttached())
    assert p.view_model.snapshotsReceived == 0


def test_signal_counts_are_derived_from_the_real_snapshot(presenter):
    p, bus = presenter
    snapshot = StateSnapshot(events=(EventState(name="x", registered=False),))

    bus.emit(SnapshotReceived(snapshot))

    assert p.view_model.signalCounts["events"] == 1
    assert p.view_model.signalCounts["overview"] == 1


def test_thread_pool_row_computes_occupancy_percent_and_display_string():
    pool = ThreadPoolStats(
        name="background",
        max_workers=20,
        in_flight=5,
        queue_depth=2,
        submitted=100,
        completed=95,
    )

    row = OverviewPresenter._thread_pool_row(pool)  # noqa: SLF001

    assert row == {
        "name": "background",
        "inFlight": 5,
        "maxWorkers": 20,
        "queueDepth": 2,
        "submitted": 100,
        "completed": 95,
        "occupancyPercent": 25,
        "occupancyText": "25%",
    }


def test_thread_pool_row_handles_zero_max_workers_without_dividing_by_zero():
    pool = ThreadPoolStats(name="idle", max_workers=0, in_flight=0)

    row = OverviewPresenter._thread_pool_row(pool)  # noqa: SLF001

    assert row["occupancyPercent"] == 0
    assert row["occupancyText"] == "0%"
