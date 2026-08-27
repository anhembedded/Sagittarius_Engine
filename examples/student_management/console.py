"""Headless entry point for `-Console` — `EPIC-007D` §2.1.

Boots the sample app with `StateConsoleExtension` attached (and, with
`--demo-faults`, `DemoFaultsExtension` too), then blocks until interrupted.
Read it from another terminal:

    .venv/bin/sagittarius-trace snapshot ws://127.0.0.1:8781 --watch 1s
"""

from __future__ import annotations

import argparse
import signal
import sys
import threading
from types import FrameType

from examples.student_management.infrastructure.demo_faults.extension import (
    DemoFaultsExtension,
)
from examples.student_management.main import build_app
from sagittarius_engine.extensions.state_console import StateConsoleExtension


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="student_management console")
    parser.add_argument(
        "--port", type=int, default=8781, help="port the console listens on"
    )
    parser.add_argument(
        "--token", default=None, help="require this token on ?token= to connect"
    )
    parser.add_argument(
        "--demo-faults",
        action="store_true",
        help="also attach DemoFaultsExtension — see EPIC-007D §2.2",
    )
    args = parser.parse_args(argv)

    console_extension = StateConsoleExtension(port=args.port, token=args.token)
    extensions: list = [console_extension]
    if args.demo_faults:
        extensions.append(DemoFaultsExtension())

    app = build_app(extra_extensions=extensions)
    # Not args.port: with --port 0 (ephemeral), that is the request, not the
    # bound port. build_app() only returns after boot reaches readiness, and
    # StateConsoleExtension._start() runs there, so the real server (and its
    # real port) already exists by this line.
    server = console_extension._server  # noqa: SLF001
    bound_port = server.port if server is not None else args.port
    auth = " (token required)" if args.token else ""
    print(
        f"Runtime state console attached on ws://127.0.0.1:{bound_port}{auth}. "
        "Ctrl+C to stop.",
        file=sys.stderr,
    )

    stop_event = threading.Event()

    def _handle_signal(_signum: int, _frame: FrameType | None) -> None:
        stop_event.set()

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)
    try:
        stop_event.wait()
    finally:
        app.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
