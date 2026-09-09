# EPIC-008B: Shell rebuilt on the new kit

- **Status**: 🔄 In Progress
- **Category**: Tooling (`tools/state_console`)
- **Started Date**: 2026-09-09

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

### 2. Shell chrome: `AppRail` + `LiveConnectionBand` wired into `ConsoleShellView`

Not started. `ConsoleShellView` (`tools/state_console/presentation/shell/
console_shell_view.py`) is currently a plain `QWidget`/`QPushButton` sidebar with no status
band at all. Plan:

- Replace the `QPushButton` sidebar with a `QmlHostView`-hosted `AppRail`, fed `sections` from
  `SCREENS` (already a route-name/label list) plus a badge count per route — the badge counts
  themselves need a source; likely a small aggregation the shell (or a new shell-level
  view-model) computes per screen from whatever signal-count each screen's own view-model
  already tracks, not a new snapshot field.
- Add a `LiveConnectionBand`-hosted status strip above the stack, driven by a new shell-level
  presenter subscribing to `ConsoleConnecting`/`ConsoleAttached`/`ConsoleFailed`/
  `ConsoleDetached`/`SnapshotReceived` — this is genuinely new (today only `OverviewPresenter`
  subscribes to connection events, and only for its own three-state summary, not for shell-wide
  chrome every screen must show).
- `OverviewViewModel`'s 3-state model (`ATTACHED_IDLE`/`ATTACHED_READING`/`NOT_ATTACHED`) needs
  to grow to the 6 states `ConsoleFailed`/`ConsoleConnecting` now make representable
  (`COLD`/`CONNECTING`/`FAILED`/`IDLE`/`READING`/`STALE`) — likely lives on the new shell-level
  presenter instead of duplicating onto every screen's own view-model.

### 3. Connect flow: address entry + recents, composed from existing primitives

Not started. Per `EPIC-008A` §5's resolution: no new kit component. `TextField` +
`FieldBackground` for the address field (already the gallery's own established pattern),
`StatefulButton` for Connect/Cancel/Retry/Reconnect, plain `Rectangle`/`RowLayout` for each
recent-address row. Recent-address persistence via `QSettings`, owned here (tier 3).

`main.py`'s `uri` CLI argument needs to become optional (`build_console_app(uri: str | None =
None, ...)`) so the console can launch cold and the connect flow is how a target is chosen —
deliberately not touched in this file's own first commit, to avoid shipping a half-wired state
(CLI accepts no URI, but there is no UI yet to supply one).

### 4. Overview restyle

Not started — depends on §2's shell chrome existing first.

## 🧪 Verification & Test Coverage

- §1: `tests/tools/state_console/test_console_connection_extension.py`, all 12 tests against a
  real `TraceServer` (including a real authed one for the `rejected` classification — no
  simulated close code). Full `pytest tests/tools/`, `tests/extensions/state_console/`,
  `tests/extensions/audit/` (182 passed) and the full local CI gate green before pushing.
- §2-4: gallery/screenshot proof once implemented, per `EPIC-008`'s own milestone table
  ("every subtask ends in a command a reader can run and a screenshot of what it produces").
