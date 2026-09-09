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
        False,
    )
    for _ in range(5):
        qtbot.wait(1)

    assert view.quick_widget.rootObject() is not None
    assert vm.openScopes == 3


# --------------------------------------------------------- EPIC-008B subtask D


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


def test_sub_tabs_show_real_counts(qtbot):
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
            },
            {
                "abstract": "IClock",
                "concrete": "SystemClock",
                "lifetime": "transient",
                "instantiated": False,
            },
        ],
        3,
        False,
    )
    for _ in range(5):
        qtbot.wait(1)

    root = view.quick_widget.rootObject()
    all_items: list = []
    _collect_all(root, all_items)

    (registrations_tab,) = _by_object_name(all_items, "subTab_registrations")
    (never_built_tab,) = _by_object_name(all_items, "subTab_neverBuilt")
    registrations_label = _find_child(registrations_tab, "subTabLabel")
    registrations_count = _find_child(registrations_tab, "subTabCount")
    never_built_label = _find_child(never_built_tab, "subTabLabel")
    never_built_count = _find_child(never_built_tab, "subTabCount")
    assert registrations_label.property("text") == "Registrations"
    assert registrations_count.property("text") == "2"
    assert never_built_label.property("text") == "Never built"
    assert never_built_count.property("text") == "1"


def test_open_scopes_plate_turns_fault_above_the_threshold(qtbot):
    """Asserts on `openScopesFault` (a plain boolean the QML itself
    computes), not on resolved colours: `Theme.danger`/`Theme.textPrimary`
    can both resolve to the same placeholder black under the shared theme
    bridge singleton when an earlier test in a full-suite run has already
    locked in a different palette (`get_theme_bridge()`'s own "only the
    first caller's palette takes effect" — a real, pre-existing constraint
    of the shared kit, not something to work around by asserting resolved
    RGB values here). The colour binding itself
    (`color: root.openScopesFault ? Theme.danger : Theme.textPrimary`) is a
    one-line ternary already exercised visually by this subtask's own
    screenshot verification."""
    view = ContainerView()
    qtbot.addWidget(view)
    view.resize(800, 600)
    vm = ContainerViewModel()
    view.bind(vm)
    view.show()
    for _ in range(5):
        qtbot.wait(1)

    vm.set_container_state([], 5, False)
    for _ in range(5):
        qtbot.wait(1)

    root = view.quick_widget.rootObject()
    root.setProperty("activeTab", "openScopes")
    for _ in range(10):
        qtbot.wait(1)

    all_items: list = []
    _collect_all(root, all_items)
    (figure,) = _by_object_name(all_items, "containerOpenScopesFigure")
    (note,) = _by_object_name(all_items, "containerOpenScopesNote")
    assert root.property("openScopesFault") is False
    assert note.property("text") == "steady · opened and closed with each request"

    vm.set_container_state([], 30, True)
    for _ in range(5):
        qtbot.wait(1)

    assert figure.property("text") == "30"
    assert root.property("openScopesFault") is True
    assert note.property("text") == "climbing since attach · none closed"


def test_open_scopes_note_reads_elevated_not_climbing_when_the_leak_predates_attach(
    qtbot,
):
    """A leak seeded once, before the console ever attached (exactly what
    `DemoFaultsExtension._seed_leaked_scopes` does): `openScopesClimbing` is
    `False` (the count never rose past its post-attach baseline), but the
    count is still over threshold -- neither "steady...closed" (a specific,
    false claim that scopes are being closed) nor "climbing" (a specific,
    false claim that it is still rising) is honest here."""
    view = ContainerView()
    qtbot.addWidget(view)
    view.resize(800, 600)
    vm = ContainerViewModel()
    view.bind(vm)
    view.show()
    for _ in range(5):
        qtbot.wait(1)

    vm.set_container_state([], 30, False)
    for _ in range(5):
        qtbot.wait(1)

    root = view.quick_widget.rootObject()
    root.setProperty("activeTab", "openScopes")
    for _ in range(10):
        qtbot.wait(1)

    all_items: list = []
    _collect_all(root, all_items)
    (note,) = _by_object_name(all_items, "containerOpenScopesNote")
    assert note.property("text") == "elevated since attach · not decreasing"
