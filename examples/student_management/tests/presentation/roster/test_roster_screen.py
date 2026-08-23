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

        # Close the window, then stop the app, WHILE STILL CAPTURING --
        # gui.py's real teardown order (qt_app.exec() returns once the user
        # closes the window, then app.stop() runs). Uninstalling the handler
        # before this point (the bug this reordering fixes, found 2026-08-23
        # by actually running the app) means teardown-time QML errors were
        # invisible to this test no matter how thorough the rest of it was.
        view.close()
        for _ in range(15):
            qtbot.wait(1)
        app.stop()
        for _ in range(15):
            qtbot.wait(1)
    finally:
        qInstallMessageHandler(previous)

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


def test_roster_screen_date_filter_narrows_visible_students(qtbot, tmp_path):
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
    assert len(presenter.view_model.students) == 1

    # A custom range entirely in the future excludes a student enrolled "now".
    presenter.view_model.setUseCustomTime(True)
    presenter.view_model.setFromDateTime("2099-01-01 00:00")
    presenter.view_model.setToDateTime("2099-12-31 00:00")
    for _ in range(5):
        qtbot.wait(1)
    assert presenter.view_model.useCustomTime is True
    assert presenter.view_model.students == []

    # A wide-open custom range includes them again.
    presenter.view_model.setFromDateTime("2000-01-01 00:00")
    presenter.view_model.setToDateTime("2100-01-01 00:00")
    for _ in range(5):
        qtbot.wait(1)
    assert len(presenter.view_model.students) == 1

    # Turning the filter off restores the unfiltered list too.
    presenter.view_model.setUseCustomTime(False)
    for _ in range(5):
        qtbot.wait(1)
    assert presenter.view_model.useCustomTime is False
    assert len(presenter.view_model.students) == 1
    app.stop()


def test_roster_screen_enrolling_appends_to_activity_log(qtbot, tmp_path):
    app = _boot(tmp_path)
    view = RosterView()
    qtbot.addWidget(view)
    presenter = RosterPresenter(view, app.container)
    view.show()
    for _ in range(5):
        qtbot.wait(1)

    log_model = presenter.view_model.logModel
    assert log_model.rowCount() == 0

    presenter.view_model.requestEnroll("Alice Nguyen", "alice@example.com", "CS", 3.7)
    for _ in range(5):
        qtbot.wait(1)

    assert log_model.rowCount() == 1
    entry = log_model.entries[0]
    assert "Alice Nguyen" in entry.message
    assert entry.level == "success"
    app.stop()


def test_roster_screen_a_filtered_view_survives_an_unrelated_enrollment(
    qtbot, tmp_path
):
    """A date filter narrowing the table to zero rows must not be silently
    discarded just because a new student enrolls elsewhere in time."""
    app = _boot(tmp_path)
    view = RosterView()
    qtbot.addWidget(view)
    presenter = RosterPresenter(view, app.container)
    view.show()
    for _ in range(5):
        qtbot.wait(1)

    presenter.view_model.setUseCustomTime(True)
    presenter.view_model.setFromDateTime("2099-01-01 00:00")
    presenter.view_model.setToDateTime("2099-12-31 00:00")
    for _ in range(5):
        qtbot.wait(1)

    presenter.view_model.requestEnroll("Alice Nguyen", "alice@example.com", "CS", 3.7)
    for _ in range(5):
        qtbot.wait(1)

    assert presenter.view_model.useCustomTime is True
    assert presenter.view_model.students == []
    app.stop()
