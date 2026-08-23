"""IView prototype tests: proves EnrollFormPresenter works identically
against either concrete View, and that the container's factory-function
registration (register_enroll_form_view) picks the right one from config
-- the two things this prototype exists to validate before deciding
whether the full roster screen is worth a QWidget implementation too."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from examples.student_management.infrastructure.ui.pyside_mvc_extension import (
    PySideMvcExtension,
)
from examples.student_management.main import build_app
from examples.student_management.presentation.enroll_form.enroll_form_presenter import (
    EnrollFormPresenter,
)
from examples.student_management.presentation.enroll_form.enroll_form_view_factory import (
    IEnrollFormView,
    register_enroll_form_view,
)
from examples.student_management.presentation.enroll_form.qml_enroll_form_view import (
    QmlEnrollFormView,
)
from examples.student_management.presentation.enroll_form.widget_enroll_form_view import (
    WidgetEnrollFormView,
)
from sagittarius_engine.extensions.pyside_mvc import IView
from sagittarius_engine.interfaces.i_config import IConfig


def _boot(tmp_path):
    return build_app(
        db_url=f"sqlite:///{tmp_path / 'test.db'}",
        extra_extensions=[PySideMvcExtension()],
    )


def test_qml_and_widget_views_both_satisfy_iview(qtbot, tmp_path):
    _boot(tmp_path)  # configure_app_qml() must run before QmlEnrollFormView loads
    qml_view = QmlEnrollFormView()
    widget_view = WidgetEnrollFormView()
    qtbot.addWidget(qml_view)
    qtbot.addWidget(widget_view)

    assert isinstance(qml_view, IView)
    assert isinstance(widget_view, IView)


def test_presenter_drives_qml_view_identically_to_widget_view(qtbot, tmp_path):
    """The actual point of the prototype: EnrollFormPresenter is written
    once, against IView, with no knowledge of which concrete View it
    gets -- both must produce the same submitted data through the exact
    same presenter code path."""
    _boot(tmp_path)

    for view in (QmlEnrollFormView(), WidgetEnrollFormView()):
        qtbot.addWidget(view)
        submitted = []
        presenter = EnrollFormPresenter(view, lambda *args: submitted.append(args))

        presenter.view_model.fullName = "Dana Kim"
        presenter.view_model.email = "dana@example.com"
        presenter.view_model.major = "Physics"
        presenter.view_model.gpa = 3.4
        presenter.view_model.submit()

        assert submitted == [("Dana Kim", "dana@example.com", "Physics", 3.4)], (
            f"failed for {type(view).__name__}"
        )


def test_qml_enroll_form_view_loads_with_no_errors(qtbot, tmp_path):
    _boot(tmp_path)
    view = QmlEnrollFormView()
    qtbot.addWidget(view)
    EnrollFormPresenter(view, lambda *args: None)

    assert view.quick_widget.errors() == []
    assert view.quick_widget.rootObject() is not None


def test_widget_enroll_form_view_reflects_view_model_changes(qtbot, tmp_path):
    """The asymmetry found verifying this prototype with a real screenshot
    (2026-08-23): QML's `text: viewModel.fullName` binding updates the
    field automatically; a QWidget View has to wire that direction back
    explicitly (fullNameChanged -> setText) or it silently only works
    forward (typing), not for a programmatic ViewModel change."""
    _boot(tmp_path)
    view = WidgetEnrollFormView()
    qtbot.addWidget(view)
    presenter = EnrollFormPresenter(view, lambda *args: None)

    presenter.view_model.fullName = "Dana Kim"
    assert view._full_name_field.text() == "Dana Kim"

    presenter.view_model.gpa = 3.4
    assert view._gpa_field.value() == 3.4


def test_register_enroll_form_view_picks_backend_from_config(tmp_path):
    app = _boot(tmp_path)
    app.container.resolve(IConfig).set("ui.qtwidget", True)
    register_enroll_form_view(app.container)

    view = app.container.resolve(IEnrollFormView)

    assert isinstance(view, WidgetEnrollFormView)
    app.stop()


def test_register_enroll_form_view_defaults_to_qml(tmp_path):
    app = _boot(tmp_path)
    register_enroll_form_view(app.container)

    view = app.container.resolve(IEnrollFormView)

    assert isinstance(view, QmlEnrollFormView)
    app.stop()
