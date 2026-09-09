"""`ShellPresenter` — `EPIC-008B` §§2-3.

Owns the shell-wide chrome (`ConnectionBandViewModel`/`RailViewModel`/
`ConnectFlowViewModel`), as opposed to each screen's own Presenter
(`OverviewPresenter` etc.), which only knows its own section. Subscribes to
the full set of connection events through `self.subscribe()` —
`BasePresenter`'s `QtEventBridge`-backed helper, the same one
`OverviewPresenter` uses, so `SnapshotReceived` (which genuinely arrives on
the websocket receive loop's thread) is already marshalled onto the Qt
thread before any handler here runs.

Translates the five events into `reference/handoff.md` §4's 6-state
display model (`COLD`/`CONNECTING`/`FAILED`/`IDLE`/`READING`/`STALE`) using
its exact copy table, and into the rail's per-section badge counts
(`signal_counts.count_signals`). Also owns opening/closing the connect flow
overlay (§3) and turning a submitted address into a real
`connect_to()` call plus a `RecentAddressesStore.record()`.
"""

from __future__ import annotations

import time
from typing import Any

from PySide6.QtCore import QTimer

from sagittarius_engine.extensions.pyside_mvc import BasePresenter
from tools.state_console.domain.events import (
    ConsoleAttached,
    ConsoleConnecting,
    ConsoleDetached,
    ConsoleFailed,
    ConsoleFailureKind,
    SnapshotReceived,
)
from tools.state_console.infrastructure.console_connection_extension import (
    ConsoleConnectionExtension,
)
from tools.state_console.presentation.shell.connect_flow_view_model import (
    ConnectFlowViewModel,
)
from tools.state_console.presentation.shell.connection_band_view_model import (
    ConnectionBandViewModel,
)
from tools.state_console.presentation.shell.rail_view_model import RailViewModel
from tools.state_console.presentation.shell.recent_addresses_store import (
    RecentAddressesStore,
    default_recent_addresses_settings,
)
from tools.state_console.presentation.shell.signal_counts import count_signals

#: How often the live-ticking age/elapsed/stale clocks refresh -- same
#: cadence and reasoning as OverviewPresenter._AGE_TICK_MS.
_AGE_TICK_MS = 1000

#: `LiveConnectionBand.maxHeartbeatTicks`'s own default -- kept in sync
#: here since this is the side that appends and must trim to match.
_MAX_HEARTBEAT_TICKS = 44

#: `reference/handoff.md` §5's failure-kind "Title" column, lowercased for
#: §4's note copy ("<error title lowercased> · <code>"). `UNKNOWN` has no
#: row in that table (it covers protocol-level surprises the design never
#: enumerated) -- a generic title, not a crash, is the right fallback.
_FAILURE_TITLE_BY_KIND: dict[ConsoleFailureKind, str] = {
    ConsoleFailureKind.MALFORMED: "address is not valid",
    ConsoleFailureKind.REFUSED: "connection refused",
    ConsoleFailureKind.REJECTED: "rejected by the backend",
}


def _format_mmss(seconds: float) -> str:
    whole = max(0, int(seconds))
    return f"{whole // 60:02d}:{whole % 60:02d}"


class ShellPresenter(BasePresenter):
    """
    @param view Must provide `bind_band(view_model)`, `bind_rail(view_model)`,
    `bind_connect_flow(view_model)`, `set_connect_flow_visible(bool)` and
    `navigate_to(section_id)` -- `ConsoleShellView` is the one real
    implementation.
    @param sections `(route_name, label)` pairs, in rail display order --
    `ConsoleShellView.SCREENS`.
    @param recent_addresses Defaults to a real, persisted store
    (`default_recent_addresses_settings()`); tests inject one backed by a
    throwaway `QSettings` file instead.
    """

    def __init__(
        self,
        view: Any,
        container: Any,
        sections: tuple[tuple[str, str], ...],
        recent_addresses: RecentAddressesStore | None = None,
    ) -> None:
        super().__init__(view, container)
        self._connection = container.resolve(ConsoleConnectionExtension)
        self._sections = sections
        self._recent_addresses = recent_addresses or RecentAddressesStore(
            default_recent_addresses_settings()
        )

        self.band_view_model = ConnectionBandViewModel()
        self.rail_view_model = RailViewModel()
        self.connect_flow_view_model = ConnectFlowViewModel()
        self.view.bind_band(self.band_view_model)
        self.view.bind_rail(self.rail_view_model)
        self.view.bind_connect_flow(self.connect_flow_view_model)
        self.rail_view_model.set_sections(
            [{"id": name, "label": label, "badgeCount": 0} for name, label in sections]
        )

        self.band_view_model.actionRequested.connect(self._on_action_requested)
        self.band_view_model.changeTargetRequested.connect(
            self._on_change_target_requested
        )
        self.rail_view_model.navigateRequested.connect(self.view.navigate_to)
        self.connect_flow_view_model.connectRequested.connect(
            self._on_connect_flow_submitted
        )
        self.connect_flow_view_model.cancelRequested.connect(
            self._on_connect_flow_cancelled
        )

        self._state = "cold"
        self._uri = ""
        self._failure_note = ""
        self._connecting_at: float | None = None
        self._attached_at: float | None = None
        self._last_snapshot_at: float | None = None
        self._stale_since: float | None = None
        self._heartbeat_ticks: list[float] = []

        self.subscribe(ConsoleConnecting, self._on_connecting)
        self.subscribe(ConsoleAttached, self._on_attached)
        self.subscribe(ConsoleFailed, self._on_failed)
        self.subscribe(ConsoleDetached, self._on_detached)
        self.subscribe(SnapshotReceived, self._on_snapshot)

        self._render()

        self._age_timer = QTimer(self)
        self._age_timer.timeout.connect(self._render)
        self._age_timer.start(_AGE_TICK_MS)

    # ------------------------------------------------------- engine events

    def _on_connecting(self, event: ConsoleConnecting) -> None:
        self._state = "connecting"
        self._uri = event.uri
        self._connecting_at = time.monotonic()
        self._heartbeat_ticks = []
        # A fresh attempt is underway -- whatever opened the overlay
        # (change…, Attach…, or the connect flow's own submit) is resolved;
        # the band itself now shows CONNECTING.
        self.view.set_connect_flow_visible(False)
        self._render()

    def _on_attached(self, _event: ConsoleAttached) -> None:
        self._state = "idle"
        self._attached_at = time.monotonic()
        self._heartbeat_ticks = []
        self._render()

    def _on_failed(self, event: ConsoleFailed) -> None:
        self._state = "failed"
        self._uri = event.uri
        title = _FAILURE_TITLE_BY_KIND.get(event.kind, "connection failed")
        self._failure_note = f"{title} · {event.code}"
        self._heartbeat_ticks = []
        self._render()

    def _on_detached(self, _event: ConsoleDetached) -> None:
        # ConsoleDetached only ever follows a connection that reached
        # ConsoleAttached at least once (see ConsoleConnectionExtension's
        # own docstring) -- an attempt that never attached is ConsoleFailed
        # instead. STALE ("was reading, connection dropped") is therefore
        # always the right transition here, never FAILED.
        self._state = "stale"
        self._stale_since = time.monotonic()
        self._heartbeat_ticks = []
        self._render()

    def _on_snapshot(self, event: SnapshotReceived) -> None:
        self._state = "reading"
        self._last_snapshot_at = time.monotonic()
        self._heartbeat_ticks.append(1.0)
        del self._heartbeat_ticks[:-_MAX_HEARTBEAT_TICKS]

        counts = count_signals(event.snapshot)
        self.rail_view_model.set_sections(
            [
                {"id": name, "label": label, "badgeCount": counts.get(name, 0)}
                for name, label in self._sections
            ]
        )
        self._render()

    # ------------------------------------------------------------ actions

    def _on_action_requested(self) -> None:
        if self._state in ("reading", "idle", "connecting"):
            self._connection.detach()
        elif self._state in ("failed", "stale"):
            self._connection.connect_to(self._uri)
        else:  # cold: "Attach…"
            self._open_connect_flow(changing_target=False)

    def _on_change_target_requested(self) -> None:
        self._open_connect_flow(changing_target=True)

    def _open_connect_flow(self, *, changing_target: bool) -> None:
        vm = self.connect_flow_view_model
        vm.set_changing_target(changing_target)
        vm.set_current_target(self._uri)
        # No "process · when last used" label yet: the store only tracks
        # order, not timestamps or process identity (nothing to fabricate
        # a label out of) -- see RecentAddressesStore's own docstring.
        vm.set_recents(
            [
                {
                    "address": address,
                    "lastUsedLabel": "",
                    "isCurrent": address == self._uri
                    and self._state in ("idle", "reading"),
                }
                for address in self._recent_addresses.list()
            ]
        )
        self.view.set_connect_flow_visible(True)

    def _on_connect_flow_submitted(self, address: str) -> None:
        self._recent_addresses.record(address)
        self._connection.connect_to(address)
        # The overlay closes for real once ConsoleConnecting actually
        # fires (_on_connecting) -- connect_to() runs the attempt on a
        # background task, so closing here would be premature.

    def _on_connect_flow_cancelled(self) -> None:
        self.view.set_connect_flow_visible(False)

    # ------------------------------------------------------------- render

    def _render(self) -> None:
        vm = self.band_view_model
        vm.set_state(self._state)
        vm.set_target_text(self._uri)
        vm.set_heartbeat_ticks(list(self._heartbeat_ticks))

        if self._state == "reading":
            vm.set_state_label("Attached · reading")
            vm.set_state_note("snapshot stream live · ~1/s")
            vm.set_age_label("last snapshot")
            vm.set_age_value(f"{self._elapsed(self._last_snapshot_at)} ago")
            vm.set_action_label("Detach")
        elif self._state == "idle":
            vm.set_state_label("Attached · idle")
            vm.set_state_note("handshake complete · no snapshot yet")
            vm.set_age_label("waiting for")
            vm.set_age_value(self._elapsed(self._attached_at))
            vm.set_action_label("Detach")
        elif self._state == "connecting":
            vm.set_state_label("Connecting")
            vm.set_state_note(f"opening socket · {self._uri}")
            vm.set_age_label("elapsed")
            vm.set_age_value(self._elapsed(self._connecting_at))
            vm.set_action_label("Cancel")
        elif self._state == "failed":
            vm.set_state_label("Connection failed")
            vm.set_state_note(self._failure_note)
            vm.set_age_label("last attempt")
            vm.set_age_value("failed")
            vm.set_action_label("Retry")
        elif self._state == "stale":
            vm.set_state_label("Not attached")
            vm.set_state_note("showing last-known data")
            vm.set_age_label("stale for")
            vm.set_age_value(self._elapsed(self._stale_since))
            vm.set_action_label("Reconnect")
        else:  # cold
            vm.set_state_label("Not attached")
            vm.set_state_note("no target attached")
            vm.set_age_label("last contact")
            vm.set_age_value("never")
            vm.set_action_label("Attach…")

    @staticmethod
    def _elapsed(since: float | None) -> str:
        if since is None:
            return "00:00"
        return _format_mmss(time.monotonic() - since)

    def shutdown(self) -> None:
        self._age_timer.stop()
