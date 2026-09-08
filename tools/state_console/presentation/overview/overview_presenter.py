"""`OverviewPresenter` — `EPIC-007E` §1.1/§3/§4.

Subscribes to `ConsoleAttached`/`ConsoleDetached`/`SnapshotReceived` through
`self.subscribe()` — `BasePresenter`'s `QtEventBridge`-backed helper, not the
raw `event_bus.on()` `RosterPresenter` uses. `SnapshotReceived` genuinely
arrives on the websocket receive loop's thread, not the Qt thread; `subscribe()`
is what marshals delivery onto this presenter's thread before
`_on_snapshot()` ever runs — no new bridge, timer, or queue written for this
screen (`EPIC-007E` criterion 9).
"""

from __future__ import annotations

import time
from typing import Any

from PySide6.QtCore import QTimer

from sagittarius_engine.extensions.pyside_mvc import BasePresenter
from tools.state_console.domain.events import (
    ConsoleAttached,
    ConsoleDetached,
    SnapshotReceived,
)
from tools.state_console.presentation.overview.overview_view_model import (
    ATTACHED_IDLE,
    ATTACHED_READING,
    NOT_ATTACHED,
    OverviewViewModel,
)

#: How often the displayed snapshot age refreshes while attached but idle,
#: or after detaching -- so "last snapshot 45s ago" keeps counting up
#: instead of freezing at whatever it read when the last update arrived.
_AGE_TICK_MS = 1000


class OverviewPresenter(BasePresenter):
    def __init__(self, view: Any, container: Any) -> None:
        super().__init__(view, container)
        self.view_model = OverviewViewModel()
        self.view.bind(self.view_model)
        self._last_snapshot_at: float | None = None
        self._connect_engine_events()

        self._age_timer = QTimer(self)
        self._age_timer.timeout.connect(self._tick_snapshot_age)
        self._age_timer.start(_AGE_TICK_MS)

    def _connect_engine_events(self) -> None:
        self.subscribe(ConsoleAttached, self._on_attached)
        self.subscribe(ConsoleDetached, self._on_detached)
        self.subscribe(SnapshotReceived, self._on_snapshot)

    def _on_attached(self, _event: ConsoleAttached) -> None:
        self.view_model.set_connection_state(ATTACHED_IDLE)

    def _on_detached(self, event: ConsoleDetached) -> None:
        self.view_model.set_connection_state(NOT_ATTACHED)
        self.view_model.set_detach_reason(event.reason)

    def _on_snapshot(self, event: SnapshotReceived) -> None:
        self.view_model.set_connection_state(ATTACHED_READING)
        self._last_snapshot_at = time.monotonic()

        snapshot = event.snapshot
        if snapshot.lifecycle is not None:
            self.view_model.set_lifecycle(
                snapshot.lifecycle.state,
                snapshot.lifecycle.extensions_registered,
                snapshot.lifecycle.extensions_initialized,
            )
        self.view_model.set_thread_pools(
            [
                {
                    "name": pool.name,
                    "inFlight": pool.in_flight,
                    "maxWorkers": pool.max_workers,
                    "queueDepth": pool.queue_depth,
                }
                for pool in snapshot.thread_pools
            ]
        )
        self._tick_snapshot_age()

    def _tick_snapshot_age(self) -> None:
        if self._last_snapshot_at is None:
            self.view_model.set_snapshot_age_seconds(-1.0)
            return
        self.view_model.set_snapshot_age_seconds(
            time.monotonic() - self._last_snapshot_at
        )

    def shutdown(self) -> None:
        self._age_timer.stop()
