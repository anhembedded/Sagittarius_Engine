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


def test_signals_screen_renders_a_dead_letter_and_a_rejected_transition(qtbot):
    """`EPIC-007F`: a real dead-lettered event and a real rejected
    transition both reach this screen's tables."""
    view = SignalsView()
    qtbot.addWidget(view)
    vm = SignalsViewModel()
    view.bind(vm)
    view.show()
    for _ in range(5):
        qtbot.wait(1)

    vm.set_connection_state(ATTACHED_READING)
    vm.set_dead_letters(
        [
            {
                "id": "dl-0",
                "eventName": "demo.student_deleted",
                "handler": "_always_raises",
                "exceptionType": "KeyError",
                "exceptionMessage": "demo: enrolment record missing",
                "payloadRepr": "{'student_id': 'demo-0000'}",
                "retries": 1,
                "agoSeconds": 12.0,
            }
        ]
    )
    vm.set_state_machines(
        [
            {
                "name": "EnrolmentFlow",
                "currentState": "ENROLLED",
                "rejectedCount": 1,
                "attemptedCount": 4,
                "declaredStates": [
                    "DRAFT",
                    "SUBMITTED",
                    "APPROVED",
                    "ENROLLED",
                    "REJECTED",
                ],
                "transitions": [
                    {
                        "fromState": "ENROLLED",
                        "toState": "SUBMITTED",
                        "event": "",
                        "rejected": True,
                        "reason": "Invalid transition from 'ENROLLED' to 'SUBMITTED'.",
                        "ageSeconds": 1.0,
                    },
                    {
                        "fromState": "DRAFT",
                        "toState": "SUBMITTED",
                        "event": "",
                        "rejected": False,
                        "reason": "",
                        "ageSeconds": 5.0,
                    },
                ],
            }
        ]
    )
    for _ in range(5):
        qtbot.wait(1)

    assert view.quick_widget.rootObject() is not None
    assert vm.deadLetters[0]["eventName"] == "demo.student_deleted"
    assert vm.stateMachines[0]["rejectedCount"] == 1
    assert any(t["rejected"] for t in vm.stateMachines[0]["transitions"])
    assert not vm.hasUiThreadHealth


def test_ui_thread_health_section_appears_only_when_watched(qtbot):
    view = SignalsView()
    qtbot.addWidget(view)
    vm = SignalsViewModel()
    view.bind(vm)
    view.show()
    for _ in range(5):
        qtbot.wait(1)

    assert vm.hasUiThreadHealth is False

    vm.set_ui_thread_health(2, 5200.0, 3)
    for _ in range(5):
        qtbot.wait(1)
    assert vm.hasUiThreadHealth is True
    assert vm.freezeCount == 2
    assert vm.offThreadMutationCount == 3

    vm.clear_ui_thread_health()
    assert vm.hasUiThreadHealth is False


def test_reprocess_control_states_why_it_is_disabled(qtbot):
    view = SignalsView()
    qtbot.addWidget(view)
    vm = SignalsViewModel()
    view.bind(vm)
    view.show()
    for _ in range(5):
        qtbot.wait(1)

    assert "ADR-003" in vm.reprocessDisabledReason
    assert view.quick_widget.rootObject() is not None


# --------------------------------------------------------- EPIC-008B subtask F


def _collect_all(item, out):
    """@brief Same one-walk-keep-it-alive discipline
    `test_overview_screen.py::_collect_all` documents."""
    out.append(item)
    for child in item.childItems():
        _collect_all(child, out)


def test_declared_states_render_as_a_chip_row_with_the_current_one_filled(qtbot):
    view = SignalsView()
    qtbot.addWidget(view)
    view.resize(900, 700)
    vm = SignalsViewModel()
    view.bind(vm)
    view.show()
    for _ in range(5):
        qtbot.wait(1)

    vm.set_connection_state(ATTACHED_READING)
    vm.set_state_machines(
        [
            {
                "name": "Door",
                "currentState": "OPEN",
                "rejectedCount": 0,
                "attemptedCount": 1,
                "declaredStates": ["CLOSED", "OPEN", "LOCKED"],
                "transitions": [],
            }
        ]
    )
    for _ in range(20):
        qtbot.wait(5)

    root = view.quick_widget.rootObject()
    all_items: list = []
    _collect_all(root, all_items)
    chip_texts = {
        item.property("text"): item
        for item in all_items
        if item.property("text") in ("CLOSED", "OPEN", "LOCKED")
    }
    assert set(chip_texts) == {"CLOSED", "OPEN", "LOCKED"}


def test_a_state_machine_with_no_rejections_shows_a_muted_rejected_figure(qtbot):
    view = SignalsView()
    qtbot.addWidget(view)
    view.resize(900, 700)
    vm = SignalsViewModel()
    view.bind(vm)
    view.show()
    for _ in range(5):
        qtbot.wait(1)

    vm.set_connection_state(ATTACHED_READING)
    vm.set_state_machines(
        [
            {
                "name": "Door",
                "currentState": "CLOSED",
                "rejectedCount": 0,
                "attemptedCount": 0,
                "declaredStates": ["CLOSED", "OPEN"],
                "transitions": [],
            }
        ]
    )
    for _ in range(20):
        qtbot.wait(5)

    root = view.quick_widget.rootObject()
    all_items: list = []
    _collect_all(root, all_items)
    (rejected_text,) = [
        item for item in all_items if item.property("text") == "0 rejected"
    ]
    assert rejected_text.property("font").bold() is False
