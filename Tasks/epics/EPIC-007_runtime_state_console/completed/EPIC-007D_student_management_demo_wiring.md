# EPIC-007D — Demo wiring in `examples/student_management`

**Epic:** [EPIC-007 — Runtime State Console](../README.md)
**Status:** ✅ **Done 2026-08-27** — see §Outcome
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
| an `EnrolmentFlow` state machine, driven, including one illegal move | a rejected transition — `transition_to()` raises `InvalidStateTransitionError` (`REF-005`: this row previously said "returns `False` and raises nothing," which was never true of `BaseStateMachine`); the demo catches it |

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

---

# Outcome

**Done 2026-08-27.** `-Console`/`-DemoFaults` on `run.ps1`, a headless `console.py` entry
point, and `DemoFaultsExtension` — one instance of every `§2.2` seed, each independently
verified, not merely asserted to exist.

## What shipped

| Piece | What it is |
| :--- | :--- |
| `examples/student_management/console.py` | Headless entry point: boots with `StateConsoleExtension` (+ `DemoFaultsExtension` if asked), blocks on `SIGINT`/`SIGTERM`, stops cleanly |
| `examples/student_management/infrastructure/demo_faults/extension.py` | `DemoFaultsExtension` — all seven `§2.2` seeds, none reachable from `doctor_target.build()` |
| `examples/student_management/infrastructure/demo_faults/enrolment_flow.py` | `EnrolmentFlow(BaseStateMachine)` — a real, small FSM driven legally then once illegally |
| `run.ps1` | `-Console`, `-ConsolePort` (default 8781), `-ConsoleToken`, `-DemoFaults` — a third mode alongside the existing GUI/`-Cli`, byte-identical when unused |
| `examples/student_management/docs/runtime_state_console_demo.md` | What each seed is, where it surfaces (and where it deliberately does not yet), why |

## Criterion 2, read precisely

"Every section of the schema" is `StateSnapshot`'s seven **collected** sections
(lifecycle/events/container/tasks/thread_pools/bounded/config) — the ones `EPIC-007C`'s
collectors actually fill. All seven are non-empty on any booted app, demo or not, so this
criterion was never in doubt for those. R1, R2, the dead-letter queue,
`ExclusiveAction.held_slot()`, and the FSM's rejections have **no field in that schema
yet** — `EPIC-007F`'s panel, not this milestone's — so "no panel is empty" cannot be judged
against them today. All five are still seeded, and all five are still independently
verified (`RuntimeMonitor.findings()`, `resilient_bus.get_dlq()`,
`exclusive_action.held_slot()`, `rejected_transition`) — real, checkable state, honestly
short of a live wire panel that does not exist yet to check it against.

## Three bugs found and fixed while building the seeds, none of them in this task's own files

Every one of them was found by actually running the seed against a real, booted app or a
real background thread — not by reading the check's own code and assuming it worked.

1. **`WiringInspector`'s D3 check named the wrong attribute.** `_scheduler()` read
   `job.job_func`; `runtime.scheduler.scheduler.ScheduledJob` has always stored its callable
   as `.fn`. Every real dead job this check has ever been run against, in this codebase's
   history, reported as `"anonymous job"`. The one existing test never caught it because its
   fake used the same wrong name. Fixed (`job_func` → `fn`), the fake corrected, and a second
   regression test added against the real `ScheduledJob` class, proving the fix names a real
   function rather than a matching fake.
2. **`WiringInspector` crashed on any constructor using `from __future__ import annotations`
   with a genuinely unbound plain dependency.** `_constructor_dependencies()` read
   `inspect.signature(concrete).parameters[...].annotation` without `eval_str=True`; under
   postponed evaluation that is a literal string, not the class. `annotation in registered`
   was therefore false for every dependency in such a class regardless of whether it was
   bound, and the one finding that reached formatting crashed on `str.__name__`. Latent
   until `DemoFaultsExtension`'s own `_ReportService` (which does use postponed annotations)
   became the first transient, uninstantiated registration in this codebase's own tests or
   examples to have any constructor-injected dependency at all. Fixed with `eval_str=True`,
   `NameError` added to the pre-existing catch for an unresolvable forward reference.
3. **`Scheduler._run()` crashed its own background thread on a job with `next_run=None`.**
   `if job.next_run <= now` compared `None` against a `datetime`, unhandled — the daemon
   thread died silently, no log line, no supervision, the rest of the app none the wiser.
   Found by literally doing what `EPIC-007D`'s own seed table asks (seed a job with no next
   run) against the real, running `Scheduler`. Fixed: a job with `next_run is None` is now
   dropped rather than compared. A second, independent consequence of the same
   investigation: even fixed, appending a dead job to the *live* scheduler is useless for a
   demo — `add_job()` wakes the thread immediately, and its very next pass drops the job
   again, typically within milliseconds. `DemoFaultsExtension.dead_scheduled_job` is
   therefore a standalone `ScheduledJob`, never appended to `context.scheduler.jobs`, kept
   as the stable object a test (or `sagittarius-doctor`, pointed at it directly) reads.

All three are reproduced-then-fixed, not read-and-assumed: each was confirmed by reverting
the fix and watching the regression test fail for the stated reason, then restored and
confirmed green — the same standard `EPIC-007B`/`C`'s deadlock and readiness-race findings
were held to.

## Verified

| Gate | Result |
| :--- | :--- |
| `pytest examples/student_management/tests/infrastructure/demo_faults/` | 12 passed — every seed asserted on its own effect |
| `pytest tests/extensions/diagnostics/` | 106 passed, incl. the new D3-real-`Scheduler` and doctor-gate-unaffected regression tests |
| `pytest tests/runtime/scheduler/` | 10 passed, incl. the new dead-job-does-not-crash-the-thread regression test |
| `pytest tests/ examples/student_management/tests/` (minus `pyside_mvc`/`ui_state`/GUI-only, PySide6 absent here) | **1045 passed**, same 9 pre-existing environmental failures as every prior checkpoint |
| `ruff check` / `ruff format --check` (whole repo) | clean |
| `mypy sagittarius_engine tests examples tools` (CI's exact invocation) | clean except the documented `thread_affinity.py:124` PySide6-absent false positive |
| `sagittarius-doctor examples.student_management.doctor_target:build --handler-package examples.student_management --strict` | `EXIT_OK`, with `DemoFaultsExtension` imported and constructed in the same test |
| `console.py --demo-faults`, then `sagittarius-trace snapshot` from a second process | manually run; `demo.roster_syncd [UNREGISTERED]`, `demo.student_deleted [UNREGISTERED]`, and `_ReportService [transient] not instantiated` all visible on the wire |
| `console.py --port 0`, `SIGTERM` mid-run | clean exit 0, prints the real bound port (not the literal `0` requested) |
| Deadlock-shaped bugs 1–3 above | each reverted, regression test confirmed to fail for the stated reason, restored, confirmed green |

## Run it

```bash
.venv/bin/python -m pytest examples/student_management/tests/infrastructure/demo_faults/ tests/extensions/diagnostics/ tests/runtime/scheduler/ -v
```
