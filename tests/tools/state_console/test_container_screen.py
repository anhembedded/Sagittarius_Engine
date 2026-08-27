"""Container screen — `EPIC-007E` criterion 2 (offscreen construction, zero
QML warnings)."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QtMsgType, qInstallMessageHandler  # noqa: E402

from sagittarius_engine.extensions.pyside_mvc import configure_app_qml  # noqa: E402
from tools.state_console.presentation.container.container_view import (  # noqa: E402
    ContainerView,
)
from tools.state_console.presentation.container.container_view_model import (  # noqa: E402
    ContainerViewModel,
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


def test_container_screen_constructs_with_no_qml_runtime_warnings(qtbot):
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
        view = ContainerView()
        qtbot.addWidget(view)
        view.bind(ContainerViewModel())
        view.show()
        for _ in range(15):
            qtbot.wait(1)
    finally:
        qInstallMessageHandler(previous)

    assert messages == [], "QML runtime warnings:\n" + "\n".join(messages)
    assert view.quick_widget.errors() == []
    assert view.quick_widget.rootObject() is not None


def test_container_screen_shows_open_scope_count(qtbot):
    view = ContainerView()
    qtbot.addWidget(view)
    vm = ContainerViewModel()
    view.bind(vm)
    view.show()
    for _ in range(5):
        qtbot.wait(1)

    vm.set_container_state(
        [
            {
                "abstract": "ILogger",
                "concrete": "LoggerService",
                "lifetime": "singleton",
                "instantiated": True,
            }
        ],
        3,
    )
    for _ in range(5):
        qtbot.wait(1)

    assert view.quick_widget.rootObject() is not None
    assert vm.openScopes == 3
