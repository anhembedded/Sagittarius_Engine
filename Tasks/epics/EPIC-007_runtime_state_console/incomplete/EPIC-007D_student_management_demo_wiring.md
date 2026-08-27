# EPIC-007D — Demo wiring in `examples/student_management`

**Epic:** [EPIC-007 — Runtime State Console](../README.md)
**Status:** 🟠 Not started
**Category:** Sample App / Developer Experience
**Priority:** P2
**Depends on:** EPIC-007C

---

## 1. Why the demo needs its own milestone

A console attached to a correctly-wired application shows eight green panels and proves
nothing. Worse, a client built against that application has **every empty and error state
untested** — which is `EPIC-005` D1 rebuilt in a new frame: a panel that looks fine because
it has never been given anything to be wrong about.

So the sample app has to be able to be *deliberately wrong*, on demand, in exactly the ways
the console claims to detect. That is a feature with a blast radius, and it gets a milestone
so the radius is bounded on purpose rather than discovered later.

## 2. Scope

### 2.1 `-Console` on `run.ps1`

A switch on `examples/student_management/run.ps1` that passes
`StateConsoleExtension(port=…)` through `build_app(extra_extensions=…)` — the same seam
`gui.py` already uses for `PySideMvcExtension`, so no new wiring concept is introduced.

Adds `-ConsolePort` (default `8781`) and `-ConsoleToken`. Follows the script's existing
conventions without exception: `#Requires -Version 5.1`, comment-based help with an
`.EXAMPLE` per mode, `$ErrorActionPreference = "Stop"`, the `-Python` → `.venv` → PATH
interpreter search, `PYTHONPATH` set to the repo root, **two-argument `Join-Path` only**
(the three-argument form is PowerShell 7+ and silently breaks the 5.1 compatibility the
script declares), and the trailing `$LASTEXITCODE` check.

### 2.2 `-DemoFaults`: the seeded conditions

A separate switch, off by default, that adds a `DemoFaultsExtension` planting one instance
of each thing the console detects — so every panel has real content and no state is drawn
from imagination:

| Seeded | Produces |
| :--- | :--- |
| a handler subscribed to `student.updatd` | **A2** — the flagship typo, with its `difflib` near-match hint |
| a handler on `student.deleted` that raises `KeyError` | **R2**, and a dead letter once retries are spent |
| an emit of `roster.exported` with nobody listening | **R1**, with the emit site |
| a `ReportService` needing an unbound `SystemClock` | **C2** — the silent one: the container builds the stand-in and the app just behaves wrongly |
| a scheduled `nightly_report` with no next run time | **D3** |
| an `ExclusiveAction` slot taken and never released | a held slot with a visibly absurd age |
| an `EnrolmentFlow` state machine, driven, including one illegal move | a rejected transition — `transition_to()` returns `False` and raises nothing |

### 2.3 `ResilientEventBus` — demo mode only, and here is why

`build_app()` wires a bare `MemoryEventBus`, which has no dead-letter queue. `EPIC-007F`'s
panel therefore has nothing to show unless the bus is wrapped.

**Decision: `-DemoFaults` wraps it; the default build does not.** Wrapping by default is
arguably an improvement to the reference app — it demonstrates a real engine feature the
sample currently ignores — but it changes the behaviour of the thing this repository holds
up as how to build on the engine, and it does so as a side effect of a diagnostics epic.
That is the shape `design-discipline.md` calls routing around a decision instead of making
one.

If the wrap proves valuable, promoting it is a small follow-up task with its own reasoning,
not a line buried in this one.

## 3. ⚠️ The single easiest way for this epic to break CI

CI runs, with `--strict`, so that a **warning** fails the build:

```yaml
- name: Wiring inspection (sagittarius-doctor)
  run: |
    sagittarius-doctor \
      examples.student_management.doctor_target:build \
      --handler-package examples.student_management \
      --strict
```

Every fault in §2.2 is exactly what that gate exists to catch. Seeding any of them into the
default wiring turns the build red immediately and correctly.

**What keeps it green:** `doctor_target.build()` calls `build_app(db_url=…)` with **no**
`extra_extensions`. Faults reach the app only through that parameter, so the doctor's factory
never sees them. This is a property to *test*, not to remember:

> A test asserts that `doctor_target.build()` produces a report with **zero errors and zero
> warnings** while `DemoFaultsExtension` exists in the tree.

Without that test the coupling is a convention, and `EPIC-005` §9's lesson is that a
convention with nothing automated behind it is how `TASK-002` got marked ✅ Completed without
an end-to-end check.

## 4. How to run it

```powershell
# the sample app, console attached, correctly wired — every panel green
.\examples\student_management\run.ps1 -Console

# the same app with one of everything wrong — every panel populated
.\examples\student_management\run.ps1 -Console -DemoFaults

# non-default port, and a token, as a consumer would run it
.\examples\student_management\run.ps1 -Console -ConsolePort 9001 -ConsoleToken dev-only
```

Read it from the other terminal (`EPIC-007C`):

```bash
.venv/bin/sagittarius-trace snapshot ws://127.0.0.1:8781 --watch 1s
```

And the gate that must stay green:

```bash
.venv/bin/sagittarius-doctor examples.student_management.doctor_target:build \
  --handler-package examples.student_management --strict
```

## 5. Done when

1. `-Console` boots the sample app with the console attached, and `sagittarius-trace
   snapshot` reads it.
2. `-DemoFaults` produces **at least one real entry in every section** of the schema — no
   panel is empty in the demo, because an empty panel in a demo teaches nothing about
   whether it works.
3. **`sagittarius-doctor --strict` reports 0 errors and 0 warnings** for
   `doctor_target:build`, asserted by a test, with `DemoFaultsExtension` present in the tree.
4. The default `run.ps1` behaviour — no switches — is byte-for-byte what it is today.
5. `run.ps1` still runs under PowerShell 5.1. The three-argument `Join-Path` regression is
   already commented in that file; do not reintroduce it.
6. The demo is documented in `examples/student_management/docs/` alongside the existing
   bootstrap and lifecycle notes, not only in this task file.
