"""
IView prototype entry point -- proves a Presenter written once against
IView works unchanged against either a QML or a QWidget concrete View,
picked by the DI container's own factory-function support (see
presentation/enroll_form/enroll_form_view_factory.py), not an if/else at
the call site.

Usage:
    python -m examples.student_management.enroll_form_prototype
    python -m examples.student_management.enroll_form_prototype --qtwidget

This prototype's own validation led to the full rollout in
presentation/roster/ (WidgetRosterView) and gui.py's own --qtwidget flag --
see TASK-037.
"""

import argparse
import sys

from PySide6.QtWidgets import QApplication

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
from sagittarius_engine.interfaces.i_config import IConfig


def main() -> int:
    parser = argparse.ArgumentParser(prog="enroll_form_prototype")
    parser.add_argument(
        "--qtwidget",
        action="store_true",
        help="Render with the QWidget View instead of the default QML one.",
    )
    args = parser.parse_args()

    qt_app = QApplication(sys.argv)

    app = build_app(extra_extensions=[PySideMvcExtension()])
    app.container.resolve(IConfig).set("ui.qtwidget", args.qtwidget)
    register_enroll_form_view(app.container)

    view = app.container.resolve(IEnrollFormView)

    def on_submit(full_name: str, email: str, major: str, gpa: float) -> None:
        print(f"Submitted: {full_name!r} {email!r} {major!r} gpa={gpa}")

    presenter = EnrollFormPresenter(view, on_submit)  # noqa: F841
    view.setWindowTitle(
        "Enroll Student — " + ("QWidget" if args.qtwidget else "QML") + " backend"
    )
    view.resize(400, 300)
    view.show()

    exit_code = qt_app.exec()
    app.stop()

    view.close()
    for _ in range(10):
        qt_app.processEvents()

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
