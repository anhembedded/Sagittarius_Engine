# TASK-033: `tools/` has 9 mypy errors and is excluded from the type-check scope

## Description

`TASK-021` req. 4 brought `examples/` and `tools/` into the **ruff** scope (both now lint and
format clean, in CI and in `scripts/ci-local.ps1`). It brought only `examples/` into the **mypy**
scope, because `examples/` was already clean while `tools/` was not:

```
mypy examples --ignore-missing-imports --follow-imports=skip
  Success: no issues found in 56 source files

mypy tools --ignore-missing-imports --follow-imports=skip
  Found 9 errors in 4 files (checked 13 source files)
```

Adding `tools/` at that moment would have re-broken the zero-error baseline
[`TASK-032`](../completed/TASK-032_mypy_baseline_cleanup.md) had just established, on the same
day it was achieved — and 9 distinct type errors is a triage job, not a line in a config task.
This is the same split `TASK-032` itself was created by, for the same reason.

## Requirements

1. Triage the 9 errors individually. As with `TASK-032`, do not reach for a blanket
   `--ignore-missing-imports` widening or file-level `# type: ignore` — each needs its own look.
   Note that some may be genuine `PySide6` stub gaps rather than defects in this repo's code;
   say which is which rather than treating all 9 the same.
2. Once clean, add `tools` to the mypy invocation in **both** places, which must stay in step:
   `.github/workflows/ci.yml` (the "mypy — type check" step) and `scripts/ci-local.ps1`.
3. Update `.agents/context/lint.md`, which currently documents the exclusion and points here.

## A related landmine found while doing `TASK-021` — decide it here

`tools/` contains **both** `audit_dashboard.py` (a module) and `audit_dashboard/` (a directory),
and they are two different applications sharing one name:

- `tools/audit_dashboard.py` — a `rich`-based terminal dashboard.
- `tools/audit_dashboard/` — the PySide6 desktop app that
  `.agents/context/architectures/architecture.md` documents as the Clean Architecture reference
  (`Domain/entities.py`, `application/receive_audit_use_case.py`,
  `infra/websocket_connector.py`, `presentation/main_window.py`).

**`import audit_dashboard` resolves to the `.py` module, not the package** — verified 2026-08-23:

```
>>> import audit_dashboard; audit_dashboard.__file__
'...\tools\audit_dashboard.py'
```

This is the opposite of the usual expectation that a package shadows a module, and the reason is
worth knowing: `tools/audit_dashboard/` has **no `__init__.py`**, so it is a *namespace* package,
and namespace packages rank **below** regular modules in `sys.path` resolution. The directory the
architecture docs treat as canonical is therefore unreachable under its own name; it works today
only because it is launched by path (`tools/audit_dashboard/main.py`, `run_dashboard.ps1`) rather
than imported.

Nothing is broken right now, which is exactly what makes it a landmine — the same shape as
[`TASK-025`](../completed/TASK-025_dead_infrastructure_persistence_package.md)'s dead package.
Decide deliberately: rename one of the two, add `__init__.py` to the package (which would flip
resolution and silently change which app `import audit_dashboard` returns — a behaviour change,
not a cleanup), or delete whichever is obsolete.

## Priority

P3 — no runtime impact. `tools/` is not part of the installable package
(`.agents/ONBOARDING.md` §2: "Standalone utilities on top of the engine"), so these errors reach
no consumer.

## Category

Tooling / Typing

## Related

- [TASK-021](TASK-021_ruff_config_shadowing.md) — brought `tools/` into the ruff scope and
  deferred the mypy half here.
- [TASK-032](../completed/TASK-032_mypy_baseline_cleanup.md) — the baseline cleanup this
  deliberately avoids undoing.
