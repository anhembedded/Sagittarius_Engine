# EPIC-008B: Shell rebuilt on the new kit

- **Status**: ✅ Done
- **Category**: Tooling (`tools/state_console`)
- **Started Date**: 2026-09-09
- **Completed Date**: 2026-09-09

---

## 🎯 Summary & Objectives

Rebuild `tools/state_console`'s shell on `EPIC-008A`'s kit output (`LiveConnectionBand`,
`AppRail`) and close the two real gaps that subtask found in `ConsoleConnectionExtension`
(no `CONNECTING`/classified-`FAILED` events, no live re-target), plus compose the connect flow
itself (`EPIC-008A` §5's resolution: existing primitives, not a new kit component).

Per `EPIC-008`'s own milestone table, this is done when `.\scripts\run-console.ps1 -Demo` shows
the new shell chrome (band + rail + badges) on every screen, Overview matches the reference
visually, and connecting to a different address works without restarting the process.

## 📐 Implementation Plan / Overview

### 1. `ConsoleConnectionExtension` — ✅ done

The two gaps `EPIC-008A` named, closed:

- **`ConsoleConnecting`/`ConsoleFailed` events** (`tools/state_console/domain/events.py`).
  `ConsoleFailed` carries `kind` (`"malformed"`/`"refused"`/`"rejected"`/`"unknown"`), `code`,
  `detail`, `uri` — classified from the real exception: `websockets.exceptions.InvalidURI` for
  malformed (confirmed empirically: `InvalidURI` is not an `OSError` subclass, so it's
  distinguishable from a real connection failure without any string-sniffing), `OSError` for
  refused, and `ConnectionClosed` with close code `4401` (verified against `TraceServer`'s own
  `_UNAUTHORIZED_CLOSE_CODE`, confirmed with a real authed server in the new tests, not assumed)
  for rejected.
- **Live re-target**: `connect_to(uri)` (detach + start fresh) and `detach()` (public,
  independent of `shutdown()`). `uri` is bound into the spawned task via `functools.partial`
  rather than read from `self.uri` inside the loop — verified empirically that
  `TaskManager.spawn()`'s `"token" in inspect.signature(...)` check still finds `token` through
  a partial that binds `uri`, so a `connect_to()` call reassigning `self.uri` cannot make an
  old, not-yet-cancelled attempt reconnect under the new address.
- **A real behavioural decision made while implementing, not merely a plumbing add:** the old
  `_run()` retried every failure forever, on a 2s timer, with no terminal state. That shape has
  no room for a `FAILED`/`STALE` state with an explicit Retry/Reconnect button
  (`reference/handoff.md` §4) — a spinner that retries forever *is* the absence of that state.
  Changed to: **one attempt per `_run()` call, no automatic retry, ever.** Reconnecting after
  either terminal event is always a fresh `connect_to()` call. This is a deliberate design
  correction, not a side effect — recorded here because it changes observable behaviour
  (`test_connecting_to_nothing_does_not_retry_on_its_own` pins it).
- **`uri: str | None = None`** — booting with no target is now possible (`COLD`), which is what
  will let §3 below launch without a CLI flag once the connect flow exists.

12 tests in `tests/tools/state_console/test_console_connection_extension.py` (7 new/rewritten),
all against a real `TraceServer` — no state faked. Existing
`test_connecting_to_nothing_emits_console_detached_not_an_exception` was rewritten (not merely
extended) to assert `ConsoleFailed`, since the old assertion encoded exactly the defect being
fixed.

### 2. Shell chrome: `AppRail` + `LiveConnectionBand` wired into `ConsoleShellView` — ✅ done

`ConsoleShellView` no longer has a `QPushButton` sidebar: `RailView`/`ConnectionBandView`
(`presentation/shell/`) host `AppRail`/`LiveConnectionBand` in two small QML wrapper files,
each bound to its own data-only ViewModel (`RailViewModel`/`ConnectionBandViewModel`) by a new
`ShellPresenter` — the shell-wide counterpart to `OverviewPresenter`, owning chrome every
screen shares rather than one screen's own state.

- `ShellPresenter` subscribes to `ConsoleConnecting`/`ConsoleAttached`/`ConsoleFailed`/
  `ConsoleDetached`/`SnapshotReceived` and drives `reference/handoff.md` §4's exact 6-state copy
  table (`COLD`/`CONNECTING`/`FAILED`/`IDLE`/`READING`/`STALE` — state name, note, age
  label/value, button label, all reproduced verbatim). The band's `Detach`/`Cancel` and
  `Retry`/`Reconnect` actions call straight through to `ConsoleConnectionExtension.detach()`/
  `.connect_to(self._uri)`, now resolvable off the container (`build_console_app` registers it
  by concrete type — it had no other way to reach the presentation layer). `Attach…` (COLD) and
  `change…` are deliberately no-ops for now: they need §3's connect flow, not built yet.
- Rail badge counts come from `signal_counts.count_signals()`, a pure function over a
  `StateSnapshot` (own test file, no server or Qt needed) — undeclared events, failed
  tasks + broken scheduler jobs, dead letters + rejected transitions, mirroring the exact
  pairings `reference/handoff.md` §7.1/§7.3/§7.5/§7.6 already state for the same data.
  `container`'s own badge is deliberately `0`: "scope leak suspected" needs a trend a single
  snapshot can't show — real detection is subtask D's job, once there's a place to keep history
  across snapshots.
- **A real ordering bug found and fixed, not just plumbing:** `ConsoleConnectionExtension.boot()`
  fires its one-shot, non-retrying connection attempt immediately. `build_console_app()` used
  to boot before `ConsoleShellView` (and therefore `ShellPresenter`) existed to subscribe — a
  fast failure (or a fast attach) would fire and vanish unseen, leaving the band stuck at `COLD`
  forever despite a real attempt having happened. Fixed with `build_console_app(..., boot=False)`
  plus an explicit `app.boot()` call after the shell is constructed, in both `main.py` and every
  test that builds a real shell — see `build_console_app()`'s own docstring.

Verified against a real demo app + real shell, offscreen, not merely read by eye: reaches
`READING` with live badges (4/2/0/0/2), Detach → `STALE` → Reconnect → `READING` again, and
navigating screens self-heals each one's own connection-state display via the next
`SnapshotReceived` (the same self-healing `OverviewPresenter`/`SignalsPresenter` already had).

### 3. Connect flow: address entry + recents, composed from existing primitives — ✅ done

Composed from existing kit primitives, per `EPIC-008A` §5's resolution — no new kit component:
`TextField` + `FieldBackground` for the address field, `StatefulButton` for
Connect/"Connect instead"/Cancel, plain `Rectangle`/`RowLayout` for each recent-address row
(`presentation/shell/qml/ConnectFlow.qml`, bound to a data-only `ConnectFlowViewModel`).

- `ShellPresenter` owns opening/closing the overlay (`ConsoleShellView.set_connect_flow_visible`,
  a `QStackedLayout` over the section body only, per `reference/handoff.md` §5 — the rail and
  band are never covered, and the underlying screen stays mounted so "cancel" needs no restore
  step) and turning a submitted address into a real `connect_to()` call. The overlay closes for
  real once `ConsoleConnecting` actually fires, not at submit time — `connect_to()` runs on a
  background task.
- Two open paths, both routed through the one `_open_connect_flow(changing_target=...)`: the
  band's `Attach…` action (`COLD` only, `changing_target=False`) and `change…` (any attached
  state, `changing_target=True`, pre-filled with the current target per §5's verbatim "Currently
  attached to `<addr>`..." copy). `Cancel` (only shown when `changing_target`) just closes the
  overlay — never touches the connection.
- `RecentAddressesStore` (`presentation/shell/recent_addresses_store.py`) wraps an injected
  `QSettings` rather than constructing its own, so tests never touch a developer's real recent-
  address history; production wiring uses `default_recent_addresses_settings()`. Deliberately
  has no "process · when last used" label yet (`reference/handoff.md` §5) — the store only
  tracks order, and fabricating a label from data it doesn't have would be worse than omitting
  it; the current target's row shows a disabled "attached" button instead of a real timestamp.
- `main.py`'s `uri` CLI argument is now optional (`build_console_app(uri: str | None = None,
  ...)`) — the console can launch cold and the connect flow is how a target gets chosen, closing
  the gap this section's plan originally deferred once there was a UI to supply one.

Verified against a real demo app, offscreen: `Attach…` from `COLD` opens the address entry with
seeded recents, submitting a real address reaches `READING` and closes the overlay, and
`change…` while attached shows the exact "Currently attached to..." copy with the current
target's recents row disabled and marked `attached`.

### 4. Overview restyle — ✅ done

Restyled onto `reference/handoff.md` §7.1/§7.2: two sub-tabs (Status/Modules, local QML state —
no new kit component, same reasoning as the connect flow), three plates (Connection/Lifecycle/
Signals) plus a worker-pools table for Status, a modules table for Modules.

- **A real backend gap closed, not worked around:** the module grid/table need per-module
  name + ready state, which the wire protocol never carried — `LifecycleState` only had
  aggregate counts ("5/5 initialized," never *which* five). Added `ModuleState` (`name`,
  `ready`) and a `LifecycleState.modules` field (`sagittarius_engine/extensions/audit/
  contracts.py`), populated by `LifecycleCollector` from `ExtensionManager.registered_extensions`
  / `initialized_extensions` — by name, matching `WiringInspector`'s own D1 check exactly, so
  "ready" here can never disagree with what `sagittarius-doctor` reports. `LifecycleCollector`
  had no dedicated test file until now (`test_lifecycle_collector.py`, 4 tests).
- **Connection plate** — state name/note colour-matched to the band's own vocabulary, snapshot
  age, and a real "snapshots received N" running tally (`OverviewViewModel.snapshotsReceived`,
  a client-side count reset on every fresh attach — the wire protocol carries no such counter).
- **Lifecycle plate** — phase, `X/Y modules initialized`, and a real module grid (one cell per
  `ModuleState`, filled `accent` when ready, hairline outline when not, hover tooltip
  `"<name> · ready|initializing"`).
- **Signals plate** — reuses `count_signals()` (moved from `presentation/shell/` to `domain/`:
  it has no Qt/shell dependency and `OverviewPresenter` needed the exact same computation
  `ShellPresenter`'s rail badges already used — duplicating it per screen was the thing this
  module exists to avoid). The four-row breakdown and "N open"/"All clear" figure are real; the
  per-row "jump to offending section+sub-tab" click-through is not built — named in
  `OverviewScreen.qml`'s own header comment as depending on cross-screen navigation
  `PresenterManager`'s stack has no channel for today, and on sub-tabs subtasks C-F haven't
  built yet.
- **Worker pools table** — extended with occupancy/submitted/completed columns.
  `AppDataTable`'s `rowAccent` hook (already shipped for `EPIC-007F`, not new here) tints a
  whole row `danger` when occupancy hits 100% or queued exceeds 20, in place of the design's
  per-cell colouring — `AppDataTable` cells are plain text with no per-cell delegate, and adding
  one for a single consumer would be the premature-kit-feature mistake this epic has avoided
  twice already (`EPIC-008A` §5, this file's own §3).
- **Modules table** — built directly in `OverviewScreen.qml` (not `AppDataTable`): the
  `initialized`/`initializing` tag needs real colour (`accent100`/`accent800` vs `danger`,
  matching the handoff's own token names exactly), which again needs a per-cell delegate
  `AppDataTable` doesn't have. A small, fixed-order, non-sortable list has no need for
  `AppDataTable`'s sorting/resizing/zebra machinery anyway.

Verified against a real demo app with seeded faults, offscreen: Status tab shows live
Connection/Lifecycle/Signals plates (3 snapshots received, 5/5 modules, 4 open signals: 2
undeclared events + 2 dead-letter/rejections) and a real, populated pools table; Modules tab
lists all five real extensions by name, each tagged `initialized`.

### Post-completion design review

Two real findings, fixed:

- `ShellPresenter._state` was a bare `str` ("cold"/"connecting"/.../"stale") compared at 15+
  call sites across `_on_action_requested`'s two tuple memberships and `_render()`'s six-way
  dispatch — exactly the "small fixed vocabulary, multiple comparison sites" shape this epic
  already promoted `ConsoleFailed.kind` out of a bare string for (`EPIC-008B`'s own design
  review, first commit). Promoted to a `ConnectionDisplayState(Enum)`, internal only —
  `LiveConnectionBand.qml`'s `state` property still receives the plain `.value` string at the
  QML boundary, where a Python `Enum` can't cross anyway.
- `OverviewViewModel._signal_counts`'s default value hand-typed the same five keys
  `count_signals()` already owns the shape of — a second, hardcoded copy of that shape that
  could silently drift if the function's keys ever changed. Simplified to `{}`; every QML read
  already falls back to `|| 0` for a missing key, so nothing depended on the default being
  fully populated.

Full local CI still green (1474 passed) after both fixes.

## 🧪 Verification & Test Coverage

- §1: `tests/tools/state_console/test_console_connection_extension.py`, all 12 tests against a
  real `TraceServer` (including a real authed one for the `rejected` classification — no
  simulated close code). Full `pytest tests/tools/`, `tests/extensions/state_console/`,
  `tests/extensions/audit/` (182 passed) and the full local CI gate green before pushing.
- §2: `tests/tools/state_console/test_signal_counts.py` (7 tests, pure Python — no server, no
  Qt) and `tests/tools/state_console/test_console_shell_view.py` (14 tests, up from 3: the
  original three rewritten off the removed `_buttons` dict, plus new coverage against both a
  real unreachable target — `FAILED`/`Retry` — and a real `TraceServer` — `READING`, badge
  counts, the band's own `Detach`/`Reconnect` buttons end to end, not the extension called
  directly). Screenshots taken offscreen against a real demo app with seeded faults
  (`examples/student_management -Console -DemoFaults`), attached, `READING`, then navigated to
  Signals and back to Overview — confirms the badge counts, the rail's active-row highlight,
  and every screen's own connection-state self-healing via the next `SnapshotReceived`.
- §3: `tests/tools/state_console/test_recent_addresses_store.py` (6 tests, a real throwaway
  `QSettings` file — ordering, de-duplication-by-moving-to-front, trimming to 5, and the
  single-remaining-entry `str`-vs-`list` round-trip quirk) and 6 new tests in
  `test_console_shell_view.py` (cold → `Attach…` opens the overlay; a real `connect_to()` via
  the flow's own `requestConnect()` reaches `READING`, closes the overlay, and records the
  address; `change…` opens with the current target and `Cancel` leaves the connection
  untouched; recents persist through an injected store) — 20 tests total in that file now.
  Screenshots offscreen against a real demo app: cold `Attach…` view with seeded recents,
  submitting a real address reaching `READING`, and `change…` while attached showing the
  verbatim "Currently attached to..." copy with the current target's row disabled.
- §4: `tests/extensions/audit/test_snapshot_contract.py` (round-trips `ModuleState` and
  `LifecycleState.modules`), `tests/extensions/state_console/test_lifecycle_collector.py`
  (4 new tests — empty, ready-vs-stuck by name, order preserved), and
  `tests/tools/state_console/test_overview_presenter.py` (5 new tests — a `Mock` container +
  real `MemoryEventBus`, no `QApplication`/websocket needed: modules populated from a real
  snapshot, the snapshots-received tally counting up and resetting on reattach, signal counts
  derived from a real snapshot, `_thread_pool_row()`'s occupancy math including the
  zero-`max_workers` guard) plus 3 new tests in `test_overview_screen.py` (Signals plate real
  counts and "All clear", the module grid + Modules tab reflecting ready/stuck by name and
  colour). Screenshots offscreen against a real demo app with seeded faults: Status tab (3
  snapshots received, 5/5 modules, 4 open signals) and Modules tab (five real extensions, each
  tagged `initialized`).

All four subtasks now done. `EPIC-008B` as a whole is complete: `EPIC-008` subtasks C-F
(Events & wiring, Container, Tasks & threads, Signals restyles) are next.
