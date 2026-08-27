"""`EPIC-007E` criterion 11: `ConsoleAttached`/`ConsoleDetached`/`SnapshotReceived`
are real `BaseEvent` subclasses, registered in `EventRegistry` like any other
domain event -- `sagittarius-doctor` run against the console's own
`build_console_app()` reports 0 errors, the same dogfooding check
`EPIC-007D` §3 holds the sample app to."""

from __future__ import annotations

import pytest

pytest.importorskip("websockets")

from sagittarius_engine.extensions.diagnostics import WiringInspector  # noqa: E402
from tools.state_console.app import build_console_app  # noqa: E402


def test_the_consoles_own_app_reports_zero_errors():
    app = build_console_app("ws://127.0.0.1:1")
    try:
        report = WiringInspector().inspect(
            bus=app.context.event_bus, container=app.context.container
        )
        assert not report.errors, report.format()
    finally:
        app.stop()
