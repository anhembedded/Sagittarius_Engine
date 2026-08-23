"""WidgetRosterView (TASK-037's full rollout): the QWidget rendering
backend for the roster screen, driven through the same
RosterPresenter/RosterViewModel the QML RosterView uses -- these tests
prove that end to end, not just that the widgets exist."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from examples.student_management.infrastructure.ui.pyside_mvc_extension import (
    PySideMvcExtension,
)
from examples.student_management.main import build_app
from examples.student_management.presentation.roster.roster_presenter import (
    RosterPresenter,
)
from examples.student_management.presentation.roster.roster_view_factory import (
    IRosterView,
    register_roster_view,
)
from examples.student_management.presentation.roster.widget_roster_view import (
    WidgetRosterView,
)
from sagittarius_engine.interfaces.i_config import IConfig


def _boot(tmp_path):
    return build_app(
        db_url=f"sqlite:///{tmp_path / 'test.db'}",
        extra_extensions=[PySideMvcExtension()],
    )


def test_register_roster_view_picks_widget_backend_from_config(qtbot, tmp_path):
    app = _boot(tmp_path)
    app.container.resolve(IConfig).set("ui.qtwidget", True)
    register_roster_view(app.container)

    view = app.container.resolve(IRosterView)
    qtbot.addWidget(view)

    assert isinstance(view, WidgetRosterView)
    app.stop()


def test_widget_roster_view_table_reflects_enrolled_students(qtbot, tmp_path):
    app = _boot(tmp_path)
    view = WidgetRosterView()
    qtbot.addWidget(view)
    presenter = RosterPresenter(view, app.container)

    presenter.view_model.requestEnroll("Alice Nguyen", "alice@example.com", "CS", 3.7)

    assert view._table_model.rowCount() == 1
    assert view._total_label.text() == "Total: 1"
    app.stop()


def test_widget_roster_view_activity_log_reflects_enrollment(qtbot, tmp_path):
    app = _boot(tmp_path)
    view = WidgetRosterView()
    qtbot.addWidget(view)
    presenter = RosterPresenter(view, app.container)

    assert view._log_list.count() == 0

    presenter.view_model.requestEnroll("Alice Nguyen", "alice@example.com", "CS", 3.7)

    assert view._log_list.count() == 1
    assert "Alice Nguyen" in view._log_list.item(0).text()
    app.stop()


def test_widget_roster_view_date_filter_narrows_table(qtbot, tmp_path):
    app = _boot(tmp_path)
    view = WidgetRosterView()
    qtbot.addWidget(view)
    presenter = RosterPresenter(view, app.container)

    presenter.view_model.requestEnroll("Alice Nguyen", "alice@example.com", "CS", 3.7)
    assert view._table_model.rowCount() == 1

    # A custom range entirely in the future excludes a student enrolled "now".
    view._use_custom_time_check.setChecked(True)
    view._from_edit.setDateTime(view._from_edit.dateTime().addYears(50))
    view._to_edit.setDateTime(view._to_edit.dateTime().addYears(51))

    assert view._table_model.rowCount() == 0

    view._on_clear_filter()

    assert view._table_model.rowCount() == 1
    app.stop()
