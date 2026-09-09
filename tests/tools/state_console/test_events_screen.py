"""Events & wiring screen — `EPIC-007E` criterion 2 (offscreen construction,
zero QML warnings)."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QtMsgType, qInstallMessageHandler  # noqa: E402

from sagittarius_engine.extensions.pyside_mvc import configure_app_qml  # noqa: E402
from tools.state_console.presentation.events.events_view import EventsView  # noqa: E402
from tools.state_console.presentation.events.events_view_model import (  # noqa: E402
    EventsViewModel,
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
    """Same predicate as `test_overview_screen.py` — see `BUG-006`."""
    source = getattr(context, "file", None) or ""
    return source.endswith(".qml") or ".qml:" in message


def test_events_screen_constructs_with_no_qml_runtime_warnings(qtbot):
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
        view = EventsView()
        qtbot.addWidget(view)
        view.bind(EventsViewModel())
        view.show()
        for _ in range(15):
            qtbot.wait(1)
    finally:
        qInstallMessageHandler(previous)

    assert messages == [], "QML runtime warnings:\n" + "\n".join(messages)
    assert view.quick_widget.errors() == []
    assert view.quick_widget.rootObject() is not None


def test_events_table_renders_a_snapshot_row(qtbot):
    view = EventsView()
    qtbot.addWidget(view)
    vm = EventsViewModel()
    view.bind(vm)
    view.show()
    for _ in range(5):
        qtbot.wait(1)

    vm.set_events(
        [
            {
                "name": "student.enrolled",
                "module": "examples.student_management",
                "handlers": ["RosterPresenter.on_enrolled"],
                "handlerCount": 1,
                "emits": 0,
                "failures": 0,
                "registered": True,
                "declaration": "declared",
                "nearMatch": "",
            }
        ]
    )
    for _ in range(5):
        qtbot.wait(1)

    root = view.quick_widget.rootObject()
    assert root is not None


# --------------------------------------------------------- EPIC-008B subtask C


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
    `test_overview_screen.py::_collect_all` documents -- needed whenever a
    test wants more than one object out of a tree containing
    `AppDataTable`'s own `ListView`."""
    out.append(item)
    for child in item.childItems():
        _collect_all(child, out)


def _by_object_name(items, object_name):
    return [item for item in items if item.objectName() == object_name]


_DECLARED_ROW = {
    "name": "student.enrolled",
    "module": "examples.student_management",
    "handlers": ["RosterPresenter.on_enrolled"],
    "handlerCount": 1,
    "emits": 0,
    "failures": 0,
    "registered": True,
    "declaration": "declared",
    "nearMatch": "",
}

_UNDECLARED_ROW = {
    "name": "student.updatd",
    "module": "",
    "handlers": ["RosterPresenter.on_updated"],
    "handlerCount": 1,
    "emits": 0,
    "failures": 0,
    "registered": False,
    "declaration": "undeclared",
    "nearMatch": "student.updated",
}


def test_wiring_bug_banner_shows_only_when_something_is_undeclared(qtbot):
    view = EventsView()
    qtbot.addWidget(view)
    vm = EventsViewModel()
    view.bind(vm)
    view.show()
    for _ in range(5):
        qtbot.wait(1)

    vm.set_events([_DECLARED_ROW])
    for _ in range(5):
        qtbot.wait(1)
    root = view.quick_widget.rootObject()
    # One search, kept alive for the rest of the test -- searching this
    # tree a second time (it contains AppDataTable's own ListView) risks
    # the "Internal C++ object already deleted" crash
    # test_overview_screen.py::_collect_all's own docstring documents; the
    # banner's `visible` binding updates on the same object either way.
    banner = _find_child(root, "eventsWiringBugBanner")
    assert banner.property("visible") is False

    vm.set_events([_DECLARED_ROW, _UNDECLARED_ROW])
    for _ in range(5):
        qtbot.wait(1)
    assert banner.property("visible") is True


def test_undeclared_sub_tab_shows_the_real_count(qtbot):
    view = EventsView()
    qtbot.addWidget(view)
    vm = EventsViewModel()
    view.bind(vm)
    view.show()
    for _ in range(5):
        qtbot.wait(1)

    vm.set_events([_DECLARED_ROW, _UNDECLARED_ROW, _UNDECLARED_ROW])
    for _ in range(5):
        qtbot.wait(1)

    root = view.quick_widget.rootObject()
    all_items: list = []
    _collect_all(root, all_items)

    (all_tab,) = _by_object_name(all_items, "subTab_all")
    (undeclared_tab,) = _by_object_name(all_items, "subTab_undeclared")
    all_label = _find_child(all_tab, "subTabLabel")
    all_count = _find_child(all_tab, "subTabCount")
    undeclared_label = _find_child(undeclared_tab, "subTabLabel")
    undeclared_count = _find_child(undeclared_tab, "subTabCount")
    assert all_label.property("text") == "All"
    assert all_count.property("text") == "3"
    assert undeclared_label.property("text") == "Undeclared"
    assert undeclared_count.property("text") == "2"
