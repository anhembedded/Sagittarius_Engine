"""GUI entry point for the runtime state console — `EPIC-007E`.

Copies `examples/student_management/gui.py`'s shape line for line
(`docs/ui_extension_lifecycle.md`'s ordering finding applies here exactly as
it does there): a `QApplication` is constructed before `App.boot()` runs, and
`PySide6` is imported only inside this function — never at module scope
(`EPIC-007E` §2 rule 2; `TASK-039`/`EPIC-005` §2 D7 is what a module-scope
import here costs).
"""

from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sagittarius-console")
    parser.add_argument(
        "uri",
        nargs="?",
        default=None,
        help="ws://host:port[?token=...] of a running TraceServer. Omit to "
        "launch cold and pick a target from the connect flow (EPIC-008B §3).",
    )
    args = parser.parse_args(argv)

    from PySide6.QtWidgets import QApplication

    from tools.state_console.app import build_console_app
    from tools.state_console.infrastructure.console_mvc_extension import (
        ConsoleMvcExtension,
    )
    from tools.state_console.presentation.shell.console_shell_view import (
        ConsoleShellView,
    )

    qt_app = QApplication(sys.argv[:1])

    # boot=False: ShellPresenter (and the Overview screen, first navigated
    # to inside ConsoleShellView's own constructor) must subscribe to the
    # connection's events before ConsoleConnectionExtension.boot() fires
    # the one-shot, non-retrying connection attempt -- see
    # build_console_app()'s own docstring for why a booted-then-shelled
    # order can silently lose a fast failure.
    app = build_console_app(
        args.uri, extra_extensions=[ConsoleMvcExtension()], boot=False
    )

    shell = ConsoleShellView(app.container)
    title_target = args.uri if args.uri is not None else "not attached"
    shell.setWindowTitle(f"Runtime State Console — {title_target}")
    shell.resize(1100, 700)

    app.boot()
    shell.show()

    exit_code = qt_app.exec()
    shell.shutdown()
    app.stop()

    # Same QML/Theme teardown-race precedent as gui.py: give any in-flight
    # QML render-thread binding a chance to finish tearing down before the
    # view (and the Theme it references) is actually destroyed.
    shell.close()
    del shell
    for _ in range(10):
        qt_app.processEvents()

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
