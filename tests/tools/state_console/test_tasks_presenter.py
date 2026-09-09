"""`TasksPresenter` — `EPIC-007E` §3, extended by `EPIC-008B` subtask E's
`owner`/`errorType`/`stack` task fields, `outstanding` pool column, and the
new per-job `jobs` list.

Same `Mock` container + real `MemoryEventBus` fixture
`test_container_presenter.py` established -- no `QApplication`, no real
websocket, no QML."""

from __future__ import annotations

import os
from unittest.mock import Mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")

from sagittarius_engine.extensions.audit.contracts import (  # noqa: E402
    JobRecord,
    LifecycleState,
    StateSnapshot,
    TaskRecord,
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
from tools.state_console.domain.events import SnapshotReceived  # noqa: E402
from tools.state_console.presentation.tasks.tasks_presenter import (  # noqa: E402
    TasksPresenter,
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
    p = TasksPresenter(Mock(), container)
    try:
        yield p, bus
    finally:
        p.dispose()


def test_a_failed_task_carries_its_owner_error_type_and_stack(presenter):
    p, bus = presenter
    bus.emit(
        SnapshotReceived(
            StateSnapshot(
                tasks=(
                    TaskRecord(
                        id="t1",
                        name="export_roster_pdf",
                        state="failed",
                        error="disk full",
                        error_type="OSError",
                        stack="Traceback...\nOSError: disk full",
                        thread="SagittariusBgTask_1",
                    ),
                )
            )
        )
    )

    (row,) = p.view_model.tasks
    assert row["owner"] == "SagittariusBgTask_1"
    assert row["error"] == "disk full"
    assert row["errorType"] == "OSError"
    assert row["stack"] == "Traceback...\nOSError: disk full"


def test_a_completed_task_carries_no_failure_detail(presenter):
    p, bus = presenter
    bus.emit(
        SnapshotReceived(
            StateSnapshot(tasks=(TaskRecord(id="t1", name="sync", state="completed"),))
        )
    )

    (row,) = p.view_model.tasks
    assert row["owner"] == ""
    assert row["errorType"] == ""
    assert row["stack"] == ""


def test_outstanding_is_submitted_minus_completed(presenter):
    p, bus = presenter
    bus.emit(
        SnapshotReceived(
            StateSnapshot(
                thread_pools=(
                    ThreadPoolStats(name="background", submitted=611, completed=609),
                )
            )
        )
    )

    (row,) = p.view_model.threadPools
    assert row["outstanding"] == 2


def test_jobs_reports_name_trigger_and_next_fire(presenter):
    p, bus = presenter
    bus.emit(
        SnapshotReceived(
            StateSnapshot(
                lifecycle=LifecycleState(
                    jobs=(
                        JobRecord(
                            name="sync_roster",
                            trigger="every 0:05:00",
                            next_fire_seconds=42.0,
                        ),
                    )
                )
            )
        )
    )

    (job,) = p.view_model.jobs
    assert job["name"] == "sync_roster"
    assert job["trigger"] == "every 0:05:00"
    assert job["nextFireSeconds"] == 42.0
    assert job["state"] == "active"


def test_a_broken_job_reports_state_no_next_fire(presenter):
    p, bus = presenter
    bus.emit(
        SnapshotReceived(
            StateSnapshot(
                lifecycle=LifecycleState(
                    jobs=(
                        JobRecord(
                            name="dead_job",
                            trigger="every 0:01:00",
                            next_fire_seconds=None,
                        ),
                    )
                )
            )
        )
    )

    (job,) = p.view_model.jobs
    assert job["nextFireSeconds"] is None
    assert job["state"] == "no next fire"


def test_jobs_is_empty_when_lifecycle_is_absent(presenter):
    p, bus = presenter
    bus.emit(SnapshotReceived(StateSnapshot()))

    assert p.view_model.jobs == []
