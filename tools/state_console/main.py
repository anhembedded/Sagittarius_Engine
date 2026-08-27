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
        "uri", help="ws://host:port[?token=...] of a running TraceServer"
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

    app = build_console_app(args.uri, extra_extensions=[ConsoleMvcExtension()])

    shell = ConsoleShellView(app.container)
    shell.setWindowTitle(f"Runtime State Console — {args.uri}")
    shell.resize(1100, 700)
    shell.show()

    exit_code = qt_app.exec()
    shell.manager.shutdown()
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
