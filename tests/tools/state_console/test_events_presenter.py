"""`EventsPresenter` — `EPIC-007E` §3, extended by `EPIC-008B` subtask C's
`handlers`/`declaration`/`nearMatch` per-row fields.

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
    EventState,
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
from tools.state_console.domain.events import SnapshotReceived  # noqa: E402
from tools.state_console.presentation.events.events_presenter import (  # noqa: E402
    EventsPresenter,
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
    p = EventsPresenter(Mock(), container)
    try:
        yield p, bus
    finally:
        p.dispose()


def test_a_declared_event_is_tagged_declared_with_no_near_match(presenter):
    p, bus = presenter
    snapshot = StateSnapshot(
        events=(EventState(name="student.enrolled", module="roster", registered=True),)
    )

    bus.emit(SnapshotReceived(snapshot))

    (row,) = p.view_model.events
    assert row["declaration"] == "declared"
    assert row["nearMatch"] == ""


def test_an_undeclared_event_is_tagged_undeclared_with_its_handlers(presenter):
    p, bus = presenter
    snapshot = StateSnapshot(
        events=(
            EventState(
                name="student.updatd",
                handlers=("RosterPresenter.on_updated",),
                registered=False,
            ),
        )
    )

    bus.emit(SnapshotReceived(snapshot))

    (row,) = p.view_model.events
    assert row["declaration"] == "undeclared"
    assert row["handlers"] == ["RosterPresenter.on_updated"]


def test_an_undeclared_event_finds_a_near_match_among_declared_names(presenter):
    p, bus = presenter
    snapshot = StateSnapshot(
        events=(
            EventState(name="student.updated", registered=True),
            EventState(name="student.updatd", registered=False),
        )
    )

    bus.emit(SnapshotReceived(snapshot))

    rows = {row["name"]: row for row in p.view_model.events}
    assert rows["student.updatd"]["nearMatch"] == "student.updated"
    assert rows["student.updated"]["nearMatch"] == ""


def test_an_undeclared_event_with_no_similar_declared_name_gets_no_suggestion(
    presenter,
):
    p, bus = presenter
    snapshot = StateSnapshot(
        events=(
            EventState(name="totally.unrelated.declared.name", registered=True),
            EventState(name="xyz", registered=False),
        )
    )

    bus.emit(SnapshotReceived(snapshot))

    rows = {row["name"]: row for row in p.view_model.events}
    assert rows["xyz"]["nearMatch"] == ""
