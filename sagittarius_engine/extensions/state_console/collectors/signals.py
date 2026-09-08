"""`SignalsCollector` — `EPIC-007F`.

Unlike every other collector, this one has nothing to read off the engine
by itself: a dead-lettered event and a rejected transition are only visible
to whatever explicitly wrapped the bus/machine that produced them
(`StateConsoleExtension.watch_dlq()`/`watch_state_machine()`). This
collector's job is only to assemble what those watchers have already
recorded into the wire shape — the watching itself happens elsewhere, at
`StateConsoleExtension.collect()`'s registration time, not at collection
time.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from sagittarius_engine.extensions.audit.contracts import (
    DeadLetterEntry,
    SignalsState,
    UiThreadHealth,
)
from sagittarius_engine.extensions.state_console.collector import ISnapshotSection
from sagittarius_engine.extensions.state_console.state_machine_watcher import (
    _StateMachineWatcher,
)


class SignalsCollector(ISnapshotSection[SignalsState]):
    """
    @brief The dead-letter queue and state-machine panels, plus optional
    UI-thread health.

    @param dlq_buses Every bus `watch_dlq()` was called with — usually one,
        but nothing here assumes exactly one.
    @param state_machine_watchers name -> `_StateMachineWatcher`, in
        registration order (`dict` preserves insertion order).
    @param ui_thread_health_sources Empty unless the observed app called
        `watch_ui_thread_health()` — absent, not zeroed, is what makes
        `UiThreadHealth`'s own "never watched" case honest. A live
        reference to `StateConsoleExtension`'s own single-item list (see
        that extension's own comment on why these are containers, not
        reassignable attributes), so a call made after this collector was
        built is still visible.
    """

    def __init__(
        self,
        dlq_buses: list[Any],
        state_machine_watchers: dict[str, _StateMachineWatcher],
        ui_thread_health_sources: list[Callable[[], UiThreadHealth]],
    ) -> None:
        self._dlq_buses = dlq_buses
        self._state_machine_watchers = state_machine_watchers
        self._ui_thread_health_sources = ui_thread_health_sources

    def collect(self) -> SignalsState:
        dead_letters: list[DeadLetterEntry] = []
        for bus in self._dlq_buses:
            dead_letters.extend(
                DeadLetterEntry.from_dlq_row(row, retries=bus.max_retries)
                for row in bus.get_dlq()
            )

        state_machines = tuple(
            watcher.collect() for watcher in self._state_machine_watchers.values()
        )

        ui_thread = (
            self._ui_thread_health_sources[-1]()
            if self._ui_thread_health_sources
            else None
        )

        return SignalsState(
            dead_letters=tuple(dead_letters),
            state_machines=state_machines,
            ui_thread=ui_thread,
        )
