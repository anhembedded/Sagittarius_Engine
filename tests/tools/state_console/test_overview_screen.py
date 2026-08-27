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
    assert "Not attached" in root.property("statusText")

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
    assert "connection lost: test" in root.property("statusText")
    # The age label is still readable -- the last snapshot, frozen, labelled
    # with its age -- exactly what EPIC-007D section 4 asks for; it is not
    # wiped just because the connection dropped.
    assert "42" in root.property("ageText")
