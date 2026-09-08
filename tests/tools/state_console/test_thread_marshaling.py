"""`EPIC-007E` criterion 9: `SnapshotReceived` emitted from a real,
non-Qt background thread reaches `OverviewPresenter`'s Qt-side slot with no
new bridge, timer, or queue written for this milestone — only
`pyside_mvc`'s existing `QtEventBridge`/`thread_affinity` path, the same one
`RosterPresenter` exercises for `student.added` (`self.subscribe()`, not the
raw `event_bus.on()`).
"""

from __future__ import annotations

import os
import threading

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")

from sagittarius_engine.extensions.audit.contracts import StateSnapshot  # noqa: E402
from sagittarius_engine.extensions.pyside_mvc import configure_app_qml  # noqa: E402
from tools.state_console.app import build_console_app  # noqa: E402
from tools.state_console.domain.events import SnapshotReceived  # noqa: E402
from tools.state_console.infrastructure.console_mvc_extension import (  # noqa: E402
    ConsoleMvcExtension,
)
from tools.state_console.presentation.overview.overview_presenter import (  # noqa: E402
    OverviewPresenter,
)
from tools.state_console.presentation.overview.overview_view import (  # noqa: E402
    OverviewView,
)
from tools.state_console.presentation.theme.icon_loader import (  # noqa: E402
    SimpleIconLoader,
)
from tools.state_console.presentation.theme.palette import (  # noqa: E402
    STATE_CONSOLE_ICON_PALETTE,
    STATE_CONSOLE_PALETTE,
)


@pytest.fixture(scope="module", autouse=True)
def _configure_theme():
    configure_app_qml(
        STATE_CONSOLE_PALETTE, SimpleIconLoader(), STATE_CONSOLE_ICON_PALETTE
    )


def test_subscribe_uses_the_qt_event_bridge_not_the_raw_bus(qtbot):
    app = build_console_app(
        "ws://127.0.0.1:1", extra_extensions=[ConsoleMvcExtension()]
    )
    try:
        view = OverviewView()
        qtbot.addWidget(view)
        presenter = OverviewPresenter(view, app.container)

        # OverviewPresenter._connect_engine_events() already subscribed
        # self._on_snapshot via self.subscribe() during __init__.
        # BasePresenter.subscribe() registers the bridge's own forward()
        # closure on the raw bus, never the handler directly -- this is
        # what proves the marshaling path is actually engaged, not the
        # raw event_bus.on() RosterPresenter uses.
        subscriptions = app.event_bus.subscriptions().get("SnapshotReceived", ())
        assert len(subscriptions) == 1
        assert subscriptions[0] is not presenter._on_snapshot  # noqa: SLF001
    finally:
        app.stop()


def test_a_snapshot_emitted_from_a_real_background_thread_reaches_the_presenter(qtbot):
    app = build_console_app(
        "ws://127.0.0.1:1", extra_extensions=[ConsoleMvcExtension()]
    )
    try:
        view = OverviewView()
        qtbot.addWidget(view)
        presenter = OverviewPresenter(view, app.container)

        received: list[int] = []
        presenter.subscribe(SnapshotReceived, lambda e: received.append(e.snapshot.t))

        emitting_thread_id: list[int] = []
        handler_thread_id: list[int] = []

        def _emit_from_worker() -> None:
            emitting_thread_id.append(threading.get_ident())
            app.event_bus.emit(SnapshotReceived(StateSnapshot(t=12345)))

        def _record_handler_thread(_e) -> None:
            handler_thread_id.append(threading.get_ident())

        presenter.subscribe(SnapshotReceived, _record_handler_thread)

        worker = threading.Thread(target=_emit_from_worker)
        worker.start()
        worker.join(timeout=2.0)
        assert not worker.is_alive()

        for _ in range(20):
            qtbot.wait(5)
            if received:
                break

        assert received == [12345]
        assert handler_thread_id, "handler never ran"
        assert handler_thread_id[0] == threading.get_ident(), (
            "handler ran on the emitting (background) thread, not the "
            "test's own (Qt main) thread -- QtEventBridge did not marshal it"
        )
        assert emitting_thread_id[0] != handler_thread_id[0]
    finally:
        app.stop()
