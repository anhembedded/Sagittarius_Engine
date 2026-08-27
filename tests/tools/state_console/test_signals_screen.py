"""Signals screen — `EPIC-007E` criterion 2 (offscreen construction, zero
QML warnings) plus the honesty discipline `signals_view_model.py` documents:
`StateSnapshot` carries no DLQ/FSM field yet (`EPIC-007F`), so this screen
must say so rather than render an empty table."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QtMsgType, qInstallMessageHandler  # noqa: E402

from sagittarius_engine.extensions.pyside_mvc import configure_app_qml  # noqa: E402
from tools.state_console.presentation.overview.overview_view_model import (  # noqa: E402
    ATTACHED_READING,
    NOT_ATTACHED,
)
from tools.state_console.presentation.signals.signals_view import (
    SignalsView,  # noqa: E402
)
from tools.state_console.presentation.signals.signals_view_model import (  # noqa: E402
    SignalsViewModel,
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


def test_signals_screen_constructs_with_no_qml_runtime_warnings(qtbot):
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
        view = SignalsView()
        qtbot.addWidget(view)
        view.bind(SignalsViewModel())
        view.show()
        for _ in range(15):
            qtbot.wait(1)
    finally:
        qInstallMessageHandler(previous)

    assert messages == [], "QML runtime warnings:\n" + "\n".join(messages)
    assert view.quick_widget.errors() == []
    assert view.quick_widget.rootObject() is not None


def test_signals_screen_says_not_yet_available_rather_than_an_empty_table(qtbot):
    view = SignalsView()
    qtbot.addWidget(view)
    vm = SignalsViewModel()
    view.bind(vm)
    view.show()
    for _ in range(5):
        qtbot.wait(1)

    vm.set_connection_state(ATTACHED_READING)
    for _ in range(5):
        qtbot.wait(1)

    root = view.quick_widget.rootObject()
    assert root.property("notAttached") is False

    vm.set_connection_state(NOT_ATTACHED)
    for _ in range(5):
        qtbot.wait(1)
    assert root.property("notAttached") is True
