# EPIC-006E — `sagittarius-doctor`, generated wiring document, docs

**Epic:** [EPIC-006 — Wiring & Readiness Diagnostics](../README.md)
**Status:** ✅ Completed 2026-08-25
**Category:** Tooling / Developer Experience
**Priority:** P2
**Depends on:** EPIC-006C (needs a readiness milestone to inspect at)

---

## 🎯 Objective

Make the inspection reachable without writing code, and reviewable in a diff.

`EPIC-006B` produces a `WiringReport`; everything here is a rendering of it.

## Requirements

1. **`sagittarius-doctor`** — boots the application, prints the report, exits non-zero on
   errors. CI is where it earns most of its value: a mis-wiring becomes a red build rather than
   a runtime surprise.
2. **A generated wiring document**, in the shape `EVENT_CATALOG.md` already establishes:
   committed, diffable, and guarded by a test. An unintended change to the wiring then shows up
   in review, which is a different and often earlier signal than a failing check.
3. `.agents/context/` updated. Per `doc-code-sync.md` this is not optional.

## Constraint carried from `TASK-039`

The wheel guard now resolves every declared console script and asserts it is callable. This
entry point is covered by it from the moment it is declared — which is the reason `TASK-039` was
done ahead of this epic rather than alongside it.

`sagittarius-audit` is the cautionary tale: it shipped in `v2.1.0` and `v2.2.0` advertising a
command that had never run, in three independent ways at once.

## Open question

Does this justify a **second** console script alongside the one `EPIC-005` Milestone D will
re-add, or should there be a single `sagittarius` command with subcommands? Two scripts is the
smaller change now; one command with subcommands is the smaller surface later. Decide before
either ships, because the entry point is published metadata and consumers pin to it.


---

## ✅ Outcome — 2026-08-25

### `sagittarius-doctor`

```bash
sagittarius-doctor myapp.main:build_app --handler-package myapp.application --strict
```

Exit codes are three, not two: `0` clean, `1` findings, `2` the doctor could not run. That
distinction cost a real fix — the first draft raised `SystemExit(str)`, which always exits `1`
and would have made "your wiring is wrong" indistinguishable from "the tool never started" while
the constants in the file claimed otherwise. CI needs those to mean different things.

Two defects were found by running it rather than by reading it:

- **The command could not import a factory in the current directory.** A console script does not
  inherit cwd on `sys.path` the way `python script.py` does, so `cd myproject && sagittarius-doctor
  myapp.main:build_app` failed with `No module named 'myapp'`. That is *the same fault class* that
  kept `sagittarius-audit` from ever running (`TASK-039`) — found here in minutes because the
  command was actually invoked.
- **`--json` output was unparseable.** The engine's logger writes to stdout, so boot noise landed
  in the middle of the document. Boot output is now redirected to stderr: diagnostics on stderr,
  payload on stdout.

### Runs in CI

The `Reference Applications` job installs the package and runs the real command against
`examples/student_management`, through a three-line `doctor_target.py` shim — `build_app()` takes
arguments and the CLI calls a zero-argument factory, and every application will write the same
shim rather than the CLI's contract being loosened. In-memory database on purpose: inspecting
wiring must not touch whatever the real configuration points at.

`--strict` there, deliberately. The sample app is what this repository holds up as how to build
on the engine, so a warning in it is a defect in the example. Two tests cover the same ground, so
a break is a red test before it is a red build.

### The generated wiring document was dropped

This file asked for a committed, diffable wiring document "in the shape `EVENT_CATALOG.md` already
establishes". Determinism was measured first — three runs, identical `md5` — so it was feasible.
It was dropped anyway, on what it would have been rather than whether it could exist:

`EVENT_CATALOG.md` documents **the engine's** events and is useful to a consumer. A wiring report
of the demo app documents **the demo app**, and would need regenerating every time an engine event
is added — noise on unrelated changes, in exchange for a signal `sagittarius-doctor --strict` in
CI already gives more directly. It would have been a test wearing a document's clothes.

What the requirement actually asked for — "an unintended change to the wiring shows up" — is met
by the CI job and by `test_the_reference_application_report_is_deterministic`, which pins that a
report cannot vary between runs.

### Documentation

`.agents/context/diagnostics.md` — new, and the place to start: what it is for, how to run it
both ways, the full check table, the silent unbound-plain-dependency case, and what the checks
refuse to do. `events.md` §8 and `modules.md` link to it, so someone reading about events or
extensions finds it.

One entry added to `IGNORE_TOKENS` in `test_agents_docs_resolve.py`: `NameError`, a Python
builtin quoted in prose about why a class-based subscription cannot be misspelled. Added with a
reason, per that test's own instruction, rather than the doc claim being deleted to silence it.

### Verification

**1258 passed, 8 skipped** (was 1243) on Python 3.12 — 14 new CLI tests. `ruff`,
`ruff format --check`, `mypy` (343 files) clean.

**The wheel guard now actively covers this entry point**, which is why `TASK-039` was done ahead
of the epic:

```
[3/3] resolving declared console scripts
  ok   sagittarius-doctor = sagittarius_engine.extensions.diagnostics.cli:main
```

### The open question, answered

*"A second console script, or one `sagittarius` command with subcommands?"* — a second script,
for now. There is exactly one command; inventing a subcommand namespace for a single verb is
structure without content. Revisit when `EPIC-005` Milestone D adds its own: two is the point at
which the namespace starts paying for itself, and it is a cheap change while both are new.

### Version impact

No bump, per `release.md` §1. `a` bump when a release is cut — new feature. The changelog should
name the new console script: `[project.scripts]` is published metadata that consumers see.

---

## Correction (2026-08-25): the exit-code contract was not true

Found by running the tool, not by reading it — while demonstrating it on a
deliberately mis-wired application, two of my own mistakes in the demo produced
this:

```
$ sagittarius-doctor app:build --handler-package app
Traceback (most recent call last):
  ...
TypeError: EventRegistry.register_named() missing 1 required keyword-only argument: 'module'
$ echo $?
1
```

Exit `1` is `EXIT_FINDINGS`, which this file's own design defines as *"the wiring was
inspected and errors were found"*. Nothing had been inspected — the application had not
finished importing. The build gets a false statement, and `--json` consumers get an empty
stdout with a traceback on stderr rather than either a document or a clean usage error.

`EXIT_USAGE = 2` exists precisely to carry this case. Two gaps let it through:

1. `load_factory()` caught only `ImportError`. But `importlib.import_module()` runs the
   module's **top-level code**, which is arbitrary application code and can raise anything.
2. `main()` called `factory()` unguarded. A factory that dies before returning an `App` —
   an unreachable database, a missing config key — is ordinary, not exceptional.

Both were documented as impossible. `load_factory`'s docstring claimed *"every failure here
is a mistyped argument, not a defect in the application under inspection"*, and `UsageError`'s
said *"the operator mistyped an argument"*. Neither survives contact with an application that
does work at import time, which is most of them.

### What changed

- `TargetError(UsageError)` — the target was named correctly but running it failed. A subclass,
  so a caller asking only *"is there a report?"* keeps catching `UsageError`, while the message
  can still separate a typo from a crash. Those need different next actions from an operator.
- `load_factory()` catches a raising import and reports which module and which exception.
- `main()` guards `factory()`, prints the **full traceback** — it names the line that actually
  broke, and no message this tool composes could beat that — then a line saying nothing was
  inspected, and returns `EXIT_USAGE`.
- `EXIT_USAGE`'s comment now records that its name is narrower than its meaning, and why it was
  not renamed: it is the published contract of a shipped console script.

### Verified

Four regression tests added to `tests/extensions/diagnostics/test_doctor_cli.py`, each checked
to **fail without the fix** (stash the `cli.py` change, re-run: 4 failed) and pass with it:

| Case | Before | After |
|---|---|---|
| module raises during import | bare traceback, exit `1` | `EXIT_USAGE`, names module + exception |
| factory raises | bare traceback, exit `1` | `EXIT_USAGE`, traceback + "nothing was inspected" |
| `--json` with a failing factory | half-stream + traceback | stdout empty |
| `TargetError` is a `UsageError` | n/a | holds |

Reference application still `EXIT_OK` under `--strict`. Full suite: **1262 passed, 8 skipped**,
coverage 90.70%; `ruff`, `ruff format --check`, `mypy` clean over CI's scope.

`.agents/context/diagnostics.md` corrected in place — it repeated the same "(a mistyped
argument)" claim.
