import sys

from PySide6.QtWidgets import QApplication

from examples.student_management.infrastructure.ui.pyside_mvc_extension import (
    PySideMvcExtension,
)
from examples.student_management.main import build_app
from examples.student_management.presentation.roster.roster_presenter import (
    RosterPresenter,
)
from examples.student_management.presentation.roster.roster_view import RosterView


def main() -> int:
    """
    @brief GUI entry point. See docs/ui_extension_lifecycle.md — the
    QApplication-before-App.boot() ordering here is the load-bearing fact
    this whole subtask exists to nail down, not an implementation detail.
    """
    qt_app = QApplication(sys.argv)

    app = build_app(extra_extensions=[PySideMvcExtension()])

    view = RosterView()
    presenter = RosterPresenter(view, app.container)  # noqa: F841 — keeps presenter alive
    view.setWindowTitle("Student Management — Sagittarius Engine sample app")
    view.resize(900, 600)
    view.show()

    exit_code = qt_app.exec()
    app.stop()
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
