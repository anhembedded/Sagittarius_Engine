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
    presenter = RosterPresenter(view, app.container)
    view.setWindowTitle("Student Management — Sagittarius Engine sample app")
    view.resize(900, 600)
    view.show()

    exit_code = qt_app.exec()
    app.stop()

    # Explicitly tear down the QML-hosted widget (and thus its QQuickWidget
    # scene graph) BEFORE main() returns and the interpreter starts its own
    # shutdown. Found 2026-08-23: leaving this to Python's own exit-time GC
    # destroys Qt/QML objects in an unspecified order, and on a real
    # (non-offscreen) platform that can race the QQuickWidget's render-thread
    # scene-graph teardown against the shared Theme QQmlPropertyMap's own
    # finalization -- if Theme's C++ object gets deleted first, every
    # still-live `Theme.xxx` binding still being torn down on the render
    # thread throws "TypeError: ... of null". Doing it here, synchronously,
    # while every extension (and Theme) is still fully alive, removes the
    # race instead of trying to win it.
    view.close()
    del presenter
    del view
    for _ in range(10):
        qt_app.processEvents()

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
