"""Overview screen — `EPIC-007E` criterion 2 (offscreen construction, zero
QML warnings) and criterion 3 (the three connection states are
distinguishable, and the not-attached one renders its staleness).
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QtMsgType, qInstallMessageHandler  # noqa: E402

from sagittarius_engine.extensions.pyside_mvc import configure_app_qml  # noqa: E402
from tools.state_console.presentation.overview.overview_view import (  # noqa: E402
    OverviewView,
)
from tools.state_console.presentation.overview.overview_view_model import (  # noqa: E402
    ATTACHED_IDLE,
    ATTACHED_READING,
    NOT_ATTACHED,
    OverviewViewModel,
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
    # configure_app_qml() itself is safe to call more than once in a
    # process (it just overwrites _app_qml_config) -- but the *theme
    # bridge* underneath it (get_theme_bridge()) is a true lazy singleton:
    # "only the first caller's palette takes effect" (its own docstring).
    # If an earlier test module in this same pytest run already configured
    # a different palette, this screen renders with that one, silently --
    # a pre-existing constraint of the shared kit, not something to work
    # around here; it does not affect whether construction is warning-free.
    configure_app_qml(
        STATE_CONSOLE_PALETTE, SimpleIconLoader(), STATE_CONSOLE_ICON_PALETTE
    )


def _is_qml_attributable(context, message: str) -> bool:
    """Same predicate `test_roster_screen.py`/`test_widget_kit_gallery.py`
    use, for the same reason (`BUG-006`): a platform font-database warning
    unrelated to any QML binding must not fail this test purely because of
    test collection order."""
    source = getattr(context, "file", None) or ""
    return source.endswith(".qml") or ".qml:" in message


def test_overview_screen_constructs_with_no_qml_runtime_warnings(qtbot):
    """`EPIC-007E` criterion 2. Deliberately does **not** capture through
    `view.close()`/app teardown: `BUG-006` (open) records that
    `RosterScreen.qml`'s own teardown produces the identical class of
    `TypeError: ... of null` non-deterministically, from bindings
    re-evaluating against a root context object already being torn down —
    a known, separately-tracked defect in `QmlHostView`'s teardown
    mechanism itself, not something this screen's own construction
    introduces. Construction is what this criterion actually asks about."""
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
        view = OverviewView()
        qtbot.addWidget(view)
        view.bind(OverviewViewModel())
        view.show()
        for _ in range(15):
            qtbot.wait(1)
    finally:
        qInstallMessageHandler(previous)

    assert messages == [], "QML runtime warnings:\n" + "\n".join(messages)
    assert view.quick_widget.errors() == []
    assert view.quick_widget.rootObject() is not None


# ------------------------------------------------------------- criterion 3


def test_not_attached_is_distinguishable_from_the_other_two_states(qtbot):
    """The literal wording of criterion 3: a test asserts the not-attached
    state renders its staleness rather than an empty panel."""
    view = OverviewView()
    qtbot.addWidget(view)
    vm = OverviewViewModel()
    view.bind(vm)
    view.show()
    for _ in range(5):
        qtbot.wait(1)

    root = view.quick_widget.rootObject()
    assert root.property("notAttached") is True
    assert "Not attached" in root.property("connectionStateName")

    vm.set_connection_state(ATTACHED_IDLE)
    for _ in range(5):
        qtbot.wait(1)
    assert root.property("notAttached") is False
    assert root.property("attachedReading") is False

    vm.set_connection_state(ATTACHED_READING)
    vm.set_snapshot_age_seconds(42.0)
    for _ in range(5):
        qtbot.wait(1)
    assert root.property("attachedReading") is True
    assert "42" in root.property("ageText")

    # Detaching after having read something is the case D1 existed to
    # protect against: the screen must say "not attached" again, not keep
    # showing the last snapshot with nothing marking it stale.
    vm.set_connection_state(NOT_ATTACHED)
    vm.set_detach_reason("connection lost: test")
    for _ in range(5):
        qtbot.wait(1)
    assert root.property("notAttached") is True
    assert "connection lost: test" in root.property("connectionNote")
    # The age label is still readable -- the last snapshot, frozen, labelled
    # with its age -- exactly what EPIC-007D section 4 asks for; it is not
    # wiped just because the connection dropped.
    assert "42" in root.property("ageText")


# --------------------------------------------------------- EPIC-008B §4


def _find_child(item, object_name):
    """Same `Loader`/`Repeater`-blind-spot workaround
    `_standalone_qml_theme.py::find_visual_child` documents -- a plain
    `findChild()` cannot see items a `Repeater`/`ListView` delegate
    created. Safe for exactly one search per tree -- see `_collect_all()`'s
    own docstring for why a second search on the same tree is not."""
    if item.objectName() == object_name:
        return item
    for child in item.childItems():
        found = _find_child(child, object_name)
        if found is not None:
            return found
    return None


def _collect_all(item, out):
    """@brief Walks the whole visual subtree exactly once, appending every
    item to `out`. `_standalone_qml_theme.py::collect_all_items()`'s own
    finding, reproduced locally rather than imported across test packages:
    a *second*, independent `childItems()` walk over a tree containing a
    `Repeater`/`ListView` can crash ("Internal C++ object already deleted")
    -- so a test needing more than one object walks the tree once, into a
    list it keeps alive, rather than searching twice."""
    out.append(item)
    for child in item.childItems():
        _collect_all(child, out)


def _by_object_name(items, object_name):
    return [item for item in items if item.objectName() == object_name]


def test_signals_plate_shows_real_counts_from_the_view_model(qtbot):
    view = OverviewView()
    qtbot.addWidget(view)
    vm = OverviewViewModel()
    view.bind(vm)
    view.show()
    for _ in range(5):
        qtbot.wait(1)

    vm.set_connection_state(ATTACHED_READING)
    vm.set_signal_counts(
        {"events": 2, "container": 0, "tasks": 1, "signals": 0, "overview": 3}
    )
    for _ in range(5):
        qtbot.wait(1)

    root = view.quick_widget.rootObject()
    figure = _find_child(root, "overviewSignalsFigure")
    assert figure is not None
    assert figure.property("text") == "3 open"


def test_signals_plate_reads_all_clear_when_nothing_is_open(qtbot):
    view = OverviewView()
    qtbot.addWidget(view)
    vm = OverviewViewModel()
    view.bind(vm)
    view.show()
    for _ in range(5):
        qtbot.wait(1)

    vm.set_connection_state(ATTACHED_READING)
    vm.set_signal_counts(
        {"events": 0, "container": 0, "tasks": 0, "signals": 0, "overview": 0}
    )
    for _ in range(5):
        qtbot.wait(1)

    root = view.quick_widget.rootObject()
    figure = _find_child(root, "overviewSignalsFigure")
    assert figure.property("text") == "All clear"


def test_module_grid_and_modules_tab_reflect_ready_state(qtbot):
    view = OverviewView()
    qtbot.addWidget(view)
    view.resize(800, 600)
    vm = OverviewViewModel()
    view.bind(vm)
    view.show()
    for _ in range(10):
        qtbot.wait(1)

    vm.set_connection_state(ATTACHED_READING)
    vm.set_modules(
        [{"name": "Ready1", "ready": True}, {"name": "Stuck", "ready": False}]
    )
    for _ in range(10):
        qtbot.wait(1)

    root = view.quick_widget.rootObject()
    root.setProperty("activeTab", "modules")
    # A freshly-visible ListView needs more than a couple of event-loop
    # turns to instantiate delegates for every model row -- a fixed,
    # generous number of no-op pumps, never a second collect_all() walk of
    # this tree (see that helper's own docstring for why).
    for _ in range(30):
        qtbot.wait(5)

    all_items: list = []
    _collect_all(root, all_items)

    (tab,) = _by_object_name(all_items, "subTab_modules")
    tab_label = _find_child(tab, "subTabLabel")
    tab_count = _find_child(tab, "subTabCount")
    assert tab_label.property("text") == "Modules"
    assert tab_count.property("text") == "2"

    names = [
        item.property("text")
        for item in _by_object_name(all_items, "overviewModuleRowName")
    ]
    assert names == ["Ready1", "Stuck"]

    (ready_cell, stuck_cell) = _by_object_name(all_items, "overviewModuleCell")
    assert ready_cell.property("color") != stuck_cell.property("color")
