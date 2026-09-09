"""Tasks & threads screen — `EPIC-007E` criterion 2 (offscreen construction,
zero QML warnings)."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QtMsgType, qInstallMessageHandler  # noqa: E402

from sagittarius_engine.extensions.pyside_mvc import configure_app_qml  # noqa: E402
from tools.state_console.presentation.tasks.tasks_view import TasksView  # noqa: E402
from tools.state_console.presentation.tasks.tasks_view_model import (  # noqa: E402
    TasksViewModel,
)
from tools.state_console.presentation.theme.icon_loader import (  # noqa: E402
    SimpleIconLoader,
)
from tools.state_console.presentation.theme.palette import (  # noqa: E402
    STATE_CONSOLE_ICON_PALETTE,
    STATE_CONSOLE_PALETTE,
)


@pytest.fixture(scope="module", autouse=True)
def _configure_theme():
    configure_app_qml(
        STATE_CONSOLE_PALETTE, SimpleIconLoader(), STATE_CONSOLE_ICON_PALETTE
    )


def _is_qml_attributable(context, message: str) -> bool:
    source = getattr(context, "file", None) or ""
    return source.endswith(".qml") or ".qml:" in message


def test_tasks_screen_constructs_with_no_qml_runtime_warnings(qtbot):
    messages: list[str] = []

    def handler(mode, context, message):
        if mode in (
            QtMsgType.QtWarningMsg,
            QtMsgType.QtCriticalMsg,
            QtMsgType.QtFatalMsg,
        ) and _is_qml_attributable(context, message):
            messages.append(message)

    previous = qInstallMessageHandler(handler)
    try:
        view = TasksView()
        qtbot.addWidget(view)
        view.bind(TasksViewModel())
        view.show()
        for _ in range(15):
            qtbot.wait(1)
    finally:
        qInstallMessageHandler(previous)

    assert messages == [], "QML runtime warnings:\n" + "\n".join(messages)
    assert view.quick_widget.errors() == []
    assert view.quick_widget.rootObject() is not None


def test_tasks_screen_reports_bounded_occupancy(qtbot):
    view = TasksView()
    qtbot.addWidget(view)
    vm = TasksViewModel()
    view.bind(vm)
    view.show()
    for _ in range(5):
        qtbot.wait(1)

    vm.set_bounded(
        retained_tasks=4,
        retained_task_limit=128,
        scheduler_jobs=2,
        scheduler_jobs_without_next_run=1,
    )
    for _ in range(5):
        qtbot.wait(1)

    assert view.quick_widget.rootObject() is not None
    assert vm.retainedTasks == 4
    assert vm.retainedTaskLimit == 128
    assert vm.schedulerJobs == 2
    assert vm.schedulerJobsWithoutNextRun == 1


# --------------------------------------------------------- EPIC-008B subtask E


def _find_child(item, object_name):
    """Same `Loader`/`Repeater`-blind-spot workaround
    `test_overview_screen.py::_find_child` documents -- safe for exactly
    one search per tree."""
    if item.objectName() == object_name:
        return item
    for child in item.childItems():
        found = _find_child(child, object_name)
        if found is not None:
            return found
    return None


def _collect_all(item, out):
    """@brief Same one-walk-keep-it-alive discipline
    `test_overview_screen.py::_collect_all` documents."""
    out.append(item)
    for child in item.childItems():
        _collect_all(child, out)


def _by_object_name(items, object_name):
    return [item for item in items if item.objectName() == object_name]


_FAILED_TASK = {
    "id": "t-failed",
    "name": "export_roster_pdf",
    "state": "failed",
    "progress": 0.4,
    "ageSeconds": 12.0,
    "owner": "SagittariusBgTask_1",
    "error": "disk full",
    "errorType": "OSError",
    "stack": 'Traceback (most recent call last):\n  File "x.py", line 1\nOSError: disk full',
}

_RUNNING_TASK = {
    "id": "t-running",
    "name": "sync_roster",
    "state": "running",
    "progress": 0.5,
    "ageSeconds": 3.0,
    "owner": "",
    "error": "",
    "errorType": "",
    "stack": "",
}


def test_sub_tabs_show_real_counts(qtbot):
    view = TasksView()
    qtbot.addWidget(view)
    vm = TasksViewModel()
    view.bind(vm)
    view.show()
    for _ in range(5):
        qtbot.wait(1)

    vm.set_tasks([_FAILED_TASK, _RUNNING_TASK])
    vm.set_thread_pools(
        [
            {
                "name": "background",
                "inFlight": 0,
                "maxWorkers": 20,
                "queueDepth": 0,
                "submitted": 1,
                "completed": 1,
                "outstanding": 0,
            }
        ]
    )
    for _ in range(5):
        qtbot.wait(1)

    root = view.quick_widget.rootObject()
    all_items: list = []
    _collect_all(root, all_items)

    (tasks_tab,) = _by_object_name(all_items, "subTab_tasks")
    (pools_tab,) = _by_object_name(all_items, "subTab_pools")
    (limits_tab,) = _by_object_name(all_items, "subTab_limits")
    assert _find_child(tasks_tab, "subTabCount").property("text") == "2"
    assert _find_child(pools_tab, "subTabCount").property("text") == "1"
    # "Limits" has no count concept at all (reference/handoff.md §7.1's own
    # "Status" precedent) -- SectionSubTabs's own `hasCount` contract hides
    # (not removes) the count Text for a tab with no `count` key.
    limits_count = _find_child(limits_tab, "subTabCount")
    assert limits_count.property("visible") is False
    assert limits_count.property("text") == ""


def test_failed_task_row_expands_to_show_error_type_message_and_stack(qtbot):
    view = TasksView()
    qtbot.addWidget(view)
    # A freshly-visible ListView needs real geometry to instantiate any
    # delegates at all -- same fix `test_overview_screen.py`'s own
    # `test_module_grid_and_modules_tab_reflect_ready_state` already needed.
    view.resize(800, 600)
    vm = TasksViewModel()
    view.bind(vm)
    view.show()
    for _ in range(5):
        qtbot.wait(1)

    vm.set_tasks([_FAILED_TASK, _RUNNING_TASK])
    for _ in range(5):
        qtbot.wait(1)

    root = view.quick_widget.rootObject()
    table = _find_child(root, "tasksTable")
    assert table.property("expandedRowKey") is None

    # AppDataTable's own row click sets `expandedRowKey` to the clicked
    # row's identity (see its `MouseArea.onClicked` in `AppDataTable.qml`)
    # -- a plain property assignment this test drives directly, since a
    # `MouseArea.clicked` cannot be invoked from a test the same way.
    table.setProperty("expandedRowKey", "t-failed")
    for _ in range(10):
        qtbot.wait(1)

    all_items: list = []
    _collect_all(root, all_items)
    # One `appDataTableExpansion` Loader exists per row regardless of state
    # (AppDataTable's own structure) -- only the failed row's is `active`.
    expansion = [
        item
        for item in _by_object_name(all_items, "appDataTableExpansion")
        if item.property("active") is True
    ]
    assert len(expansion) == 1
    detail_texts = [
        item.property("text") for item in all_items if item.property("text") is not None
    ]
    joined = "\n".join(str(t) for t in detail_texts)
    assert "OSERROR" in joined
    assert "disk full" in joined
    assert "OSError: disk full" in joined


def test_jobs_table_shows_a_broken_job_as_none_dead(qtbot):
    view = TasksView()
    qtbot.addWidget(view)
    view.resize(800, 600)
    vm = TasksViewModel()
    view.bind(vm)
    view.show()
    for _ in range(5):
        qtbot.wait(1)

    vm.set_jobs(
        [
            {
                "name": "sync_roster",
                "trigger": "every 0:05:00",
                "nextFireSeconds": 42.0,
                "state": "active",
            },
            {
                "name": "dead_job",
                "trigger": "every 0:01:00",
                "nextFireSeconds": None,
                "state": "no next fire",
            },
        ]
    )
    root = view.quick_widget.rootObject()
    root.setProperty("activeTab", "limits")
    for _ in range(10):
        qtbot.wait(1)

    all_items: list = []
    _collect_all(root, all_items)
    (jobs_table,) = _by_object_name(all_items, "limitsJobsTable")
    assert jobs_table is not None

    cell_texts = [
        item.property("text") for item in all_items if item.property("text") is not None
    ]
    joined = "\n".join(str(t) for t in cell_texts)
    assert "in 42s" in joined
    assert "none — dead" in joined
    assert "no next fire" in joined
