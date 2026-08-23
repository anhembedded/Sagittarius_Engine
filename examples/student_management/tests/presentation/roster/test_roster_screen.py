from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QtMsgType, qInstallMessageHandler

from examples.student_management.infrastructure.ui.pyside_mvc_extension import (
    PySideMvcExtension,
)
from examples.student_management.main import build_app
from examples.student_management.presentation.roster.roster_presenter import (
    RosterPresenter,
)
from examples.student_management.presentation.roster.roster_view import RosterView


def _boot(tmp_path):
    return build_app(
        db_url=f"sqlite:///{tmp_path / 'test.db'}",
        extra_extensions=[PySideMvcExtension()],
    )


def test_roster_screen_loads_with_no_qml_errors(qtbot, tmp_path):
    app = _boot(tmp_path)
    view = RosterView()
    qtbot.addWidget(view)
    presenter = RosterPresenter(view, app.container)

    assert view.quick_widget.errors() == []
    assert view.quick_widget.rootObject() is not None
    assert presenter.view_model is not None
    app.stop()


def test_roster_screen_emits_no_qml_runtime_warnings(qtbot, tmp_path):
    """Mirrors test_gallery_emits_no_qml_runtime_warnings's own reasoning:
    QQuickWidget.errors() only reports parse errors, not bindings that
    throw at evaluation. Capturing Qt's message stream is the only way
    that has actually caught a real defect in this codebase before."""
    app = _boot(tmp_path)

    messages: list[str] = []

    def handler(mode, context, message):
        if mode in (
            QtMsgType.QtWarningMsg,
            QtMsgType.QtCriticalMsg,
            QtMsgType.QtFatalMsg,
        ):
            messages.append(message)

    previous = qInstallMessageHandler(handler)
    try:
        view = RosterView()
        qtbot.addWidget(view)
        presenter = RosterPresenter(view, app.container)
        view.show()
        for _ in range(15):
            qtbot.wait(1)
    finally:
        qInstallMessageHandler(previous)
        app.stop()

    assert messages == [], "QML runtime warnings:\n" + "\n".join(messages)
    assert presenter.view_model is not None


def test_roster_screen_shows_enrolled_student(qtbot, tmp_path):
    app = _boot(tmp_path)
    view = RosterView()
    qtbot.addWidget(view)
    presenter = RosterPresenter(view, app.container)
    view.show()
    for _ in range(5):
        qtbot.wait(1)

    presenter.view_model.requestEnroll("Alice Nguyen", "alice@example.com", "CS", 3.7)
    for _ in range(5):
        qtbot.wait(1)

    assert presenter.view_model.totalStudents == 1
    assert presenter.view_model.students[0]["fullName"] == "Alice Nguyen"
    app.stop()


def test_roster_screen_toggles_compact_mode(qtbot, tmp_path):
    app = _boot(tmp_path)
    view = RosterView()
    qtbot.addWidget(view)
    presenter = RosterPresenter(view, app.container)
    view.show()
    for _ in range(5):
        qtbot.wait(1)

    assert presenter.view_model.compactMode is False
    presenter.view_model.compactMode = True
    assert presenter.view_model.compactMode is True
    app.stop()
