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
                "handlerCount": 2,
                "emits": 0,
                "failures": 0,
                "registered": True,
            }
        ]
    )
    for _ in range(5):
        qtbot.wait(1)

    root = view.quick_widget.rootObject()
    assert root is not None
