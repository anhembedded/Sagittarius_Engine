# EPIC-007E — The QML client, and `scripts/run-console.ps1`

**Epic:** [EPIC-007 — Runtime State Console](../README.md)
**Status:** 🟠 Not started
**Category:** Tooling / UI
**Priority:** P2
**Depends on:** EPIC-007C, EPIC-007D
**Decided by:** [`ADR-002`](../../../decisions/ADR-002_state_console_client_ui_framework.md)

---

## 1. Scope

A PySide6 + QML client in `tools/state_console/`, composing the engine's own kit, plus one
PowerShell script that launches it — and, in demo mode, launches the app it observes too.

Design: <https://claude.ai/code/artifact/29b45155-8fb3-4b54-a6ce-2440f51d8330>. Those
artboards are information architecture, not a build target: no QML was written for them, and
they say what the kit must be able to express, not how it will.

## 2. Packaging — three rules, each from a shipped defect

`EPIC-005` §2's D6 and D7 are what happens when any of these is missed. All three are
already solved elsewhere in this repo; this milestone copies, it does not invent.

1. **`tools/`, never `sagittarius_engine/`.** The engine must not gain a UI dependency
   (`ADR-001` §2.10).
2. **`PySide6` imported inside `main()`,** never at module scope. D7 is literally this: a
   module-level `import PySide6.QtWidgets` in a zero-dependency wheel produced a command
   that died on `ModuleNotFoundError` before reaching any of its own code. The working
   precedent is `extensions/audit/cli.py`, which needs `websockets` and imports it inside
   the function that connects.
3. **A `dashboard = ["PySide6>=6.5"]` extra,** not a bare dependency, and every console
   script it declares resolves under `scripts/verify_wheel_importable.py` step 3 — the guard
   `TASK-039` added *because* an entry point shipped broken for two releases.

## 3. Screens

Six, matching the artboards. Each composes kit components rather than authoring primitives:
`AppDataTable` for the event, container and task tables; `LogPanel` for findings;
`StatefulButton`, `AppModal`, `BaseCard` derivations for the rest.

| Screen | Shows |
| :--- | :--- |
| Overview | verdict line, lifecycle strip, subsystem cards, findings preview |
| Events & wiring | the declared ⋈ subscribed join, with a detail pane per event |
| Container | registrations, lifetimes, what is built, unbound dependencies, cycles |
| Tasks & threads | task table, pool saturation, queue depth, exclusive slots, scheduler |
| Signals | dead-letter queue and state machines — `EPIC-007F` |
| Not attached | the honest disconnected state — §4 |

### 3.1 The console supplies its own palette

`ADR-002` §2.2. It fills the 11 required colour tokens with its own values and binds
`Theme.<name>` exclusively — no literal colour, spacing, radius or duration in its QML,
enforced by `tokens.qml_literal_guard` the same way any consumer is.

It does **not** inherit `examples/student_management`'s palette: a diagnostic console that
looks like one of the apps it inspects is confusing when both are on screen.

### 3.2 Kit gaps are promoted, not re-derived

This workload — dense tables, severity chips, state-graph nodes, saturation bars — is not
what the kit was measured against, so `ui-architecture.md` §1.1 escape hatches are expected.
Its rule applies unchanged: each escape is named and justified at the call site, and **a
repeated escape is a signal to promote the shape into the kit**, not to keep re-deriving it.

That is the point of `ADR-002` §2.1's third reason. If this milestone ends with three
undocumented escapes and no kit additions, the "second consumer" benefit was not collected.

## 4. The disconnected state is a designed screen, not a fallback

`EPIC-005` §2's **D1**: the old CLI polled HTTP against a socket that only ever spoke
WebSocket, rendered a connection error on every refresh, and showed an empty panel that read
as *"nothing is happening"*. It shipped that way in v2.1.0 and v2.2.0.

The console therefore distinguishes three states that a naive client renders identically:

- **not attached** — nothing is being read; any data on screen is the last snapshot, frozen,
  and labelled with its age
- **attached, idle** — connected, nothing requested yet
- **attached, reading, nothing wrong** — the genuinely-green case

A client that cannot tell the first from the third is the defect this whole epic descends
from.

## 5. `scripts/run-console.ps1`

House style is `examples/student_management/run.ps1` and `scripts/show-gallery.ps1`; this
follows it without exception. `#Requires -Version 5.1`, comment-based help with SYNOPSIS /
DESCRIPTION / one PARAMETER block per switch / an EXAMPLE per mode,
`$ErrorActionPreference = "Stop"`, `-Python` → `.venv` → PATH interpreter search,
`PYTHONPATH` set to the repo root so the working tree is what runs, **two-argument
`Join-Path` only**, and a trailing `$LASTEXITCODE` check that throws with the child's name.

Three modes:

| Mode | Does |
| :--- | :--- |
| `-Attach <uri>` | Opens the console against an already-running app. The everyday mode. |
| `-Demo` | Starts `run.ps1 -Console -DemoFaults`, **waits for the port to accept**, opens the console against it, and stops both when the console closes. One command, one keystroke. |
| `-Snapshot` | No window: prints one text snapshot and exits. The CI/SSH path, `EPIC-007C`'s renderer. |

`-Demo` is the mode this milestone is judged on, and its two hard parts are both failure
modes rather than features:

- **Wait for the port, never sleep a fixed number of seconds.** Poll the TCP connect until
  it succeeds, with a timeout that throws a message naming the port. A fixed sleep is a race
  that passes on the author's machine and fails on a slower one.
- **Always stop the child.** The sample app is started by this script and must not outlive
  it — including when the console throws. `try/finally`, and the app's process object kept
  so it can actually be stopped rather than hoped about.

## 6. How to run it

```powershell
# the whole demo — sample app with seeded faults, plus the console, one command
.\scripts\run-console.ps1 -Demo

# attach to an app someone else started
.\scripts\run-console.ps1 -Attach ws://127.0.0.1:8781

# with a token, as a consumer would
.\scripts\run-console.ps1 -Attach "ws://127.0.0.1:9001?token=dev-only"

# no display server: one text snapshot, then exit
.\scripts\run-console.ps1 -Snapshot -Attach ws://127.0.0.1:8781
```

Tests:

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/tools/state_console -v
```

## 7. Done when

1. **`.\scripts\run-console.ps1 -Demo` opens a window showing the seeded app**, and closing
   the window leaves no orphaned Python process — asserted, not observed once.
2. Every screen constructs under `QT_QPA_PLATFORM=offscreen` with **zero QML warnings and
   zero unbound-property errors**, in CI, on every push (`ui-architecture.md` §6.1).
3. The three states of §4 are distinguishable on screen, and a test asserts the
   not-attached one renders its staleness rather than an empty panel.
4. `tokens.qml_literal_guard` and `kit.raw_primitive_guard` both pass over
   `tools/state_console/`.
5. `PySide6` appears in **no** module-scope import under `tools/state_console/` — a static
   test, in the shape of `import_boundary.find_deep_imports()`.
6. `scripts/verify_wheel_importable.py` resolves every entry point this milestone declares.
7. `run-console.ps1` runs under PowerShell 5.1.
8. Any escape hatch used against the kit is named at its call site, and repeated ones are
   listed here as kit-promotion candidates.
