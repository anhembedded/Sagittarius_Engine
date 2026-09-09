"""`EventsPresenter` — `EPIC-007E` §3, extended by `EPIC-008B` subtask C.
Same `self.subscribe()` pattern as `OverviewPresenter` (`QtEventBridge`, not
the raw bus — `SnapshotReceived` genuinely crosses threads)."""

from __future__ import annotations

import difflib
from typing import Any

from sagittarius_engine.extensions.pyside_mvc import BasePresenter
from tools.state_console.domain.events import (
    ConsoleAttached,
    ConsoleDetached,
    SnapshotReceived,
)
from tools.state_console.presentation.events.events_view_model import (
    EventsViewModel,
)
from tools.state_console.presentation.overview.overview_view_model import (
    ATTACHED_IDLE,
    ATTACHED_READING,
    NOT_ATTACHED,
)


class EventsPresenter(BasePresenter):
    def __init__(self, view: Any, container: Any) -> None:
        super().__init__(view, container)
        self.view_model = EventsViewModel()
        self.view.bind(self.view_model)
        self._connect_engine_events()

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
        events = event.snapshot.events
        declared_names = [e.name for e in events if e.registered]

        self.view_model.set_events(
            [
                {
                    "name": e.name,
                    "module": e.module,
                    "handlers": list(e.handlers),
                    "handlerCount": len(e.handlers),
                    "emits": e.emits,
                    "failures": e.failures,
                    "registered": e.registered,
                    "declaration": "declared" if e.registered else "undeclared",
                    "nearMatch": ""
                    if e.registered
                    else self._near_match(e.name, declared_names),
                }
                for e in events
            ]
        )

    @staticmethod
    def _near_match(name: str, declared_names: list[str]) -> str:
        """@brief `reference/handoff.md` §7.3's "did you mean `<near>`?" --
        computed client-side from names the snapshot already carries (every
        declared event name is one), not a new wire field."""
        matches = difflib.get_close_matches(name, declared_names, n=1, cutoff=0.6)
        return matches[0] if matches else ""
