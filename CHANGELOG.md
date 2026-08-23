# Changelog

All notable changes to Sagittarius Engine.

This file starts at `2.0.0`. Earlier versions (`1.0.0`–`1.5.0`) were released without one;
their history is in `git log`.

---

## [2.0.0] — 2026-08-23

Major bump because two changes break consumers at import/install time. Everything else in this
release is additive or internal.

### ⚠️ Breaking

- **Python floor raised to 3.14** (`requires-python = ">=3.14"`, was `>=3.12`). `pip` will
  refuse to install on 3.12/3.13. The previous declaration was never actually verified — CI's
  test matrix only ever ran `3.14-dev`, and the engine did in fact contain a construct that
  raised `NameError` on ≤3.13 (see the `ITaskHandle` fix below). Narrowing the claim to what is
  tested, rather than widening CI to defend a claim nobody needed.
- **The scaffolding feature is removed entirely** — the `sagittarius_engine.sdk` package (its
  `cli`, `project_generator`, `template_loader`, `template_renderer`, and all four project
  templates), the `tools/scaffold.py` script, and the `sagittarius` console-script entry point
  declared in `pyproject.toml`. Both documented invocations were broken and had been for some
  time: `tools/scaffold.py` generated projects importing `LoggerModule`/`DatabaseModule`/
  `HealthModule`, all renamed to `*Extension` long before; the SDK CLI's documented flag
  (`--template`) did not exist; and `sdk/templates/` was never listed in `package-data`, so a
  pip-installed engine could not scaffold at all. No replacement is planned.
- **`sagittarius_engine.infrastructure.persistence` removed.** Nominally breaking, practically
  not: the package's `__init__.py` re-exported `IThreadManager` from a module moved to
  `sagittarius_engine/interfaces/` in commit `85e5576`, so `import`ing it has raised
  `ModuleNotFoundError` ever since. `IThreadManager` is at
  `sagittarius_engine.interfaces.i_thread_manager`.

### Fixed

- **`TaskManager.get_active_tasks()` annotation referenced an unimported name.**
  `runtime/tasks/task_manager.py` annotated `-> list[ITaskHandle]` without importing
  `ITaskHandle` and without `from __future__ import annotations`. Python 3.14's deferred
  annotation evaluation (PEP 649) hid this at import time, but any `typing.get_type_hints()`
  call on it raised `NameError` — and on Python ≤3.13, where annotations evaluate eagerly at
  `def` time, importing the module failed outright. `app.boot()` imports this module.
- **`PydanticValidationMiddleware` silently skipped validation.** A bare `except: pass` around
  `typing.get_type_hints()` meant that any handler whose hints could not be resolved — including
  handlers using the `TYPE_CHECKING` idiom this engine's own architecture rules encourage —
  proceeded entirely unvalidated, with no log or error. Now falls back to raw
  `inspect.signature()` annotations first (mirroring `StdLibContainer`), then logs a `WARNING`
  naming the handler, and an `ERROR` at the point validation is actually skipped. Policy is
  fail-open-loudly rather than fail-closed, because the middleware is typically registered
  globally and raising would break unrelated handlers.
- **`HealthExtension.boot()`** had the same silent-swallow shape; now logs via
  `logger.exception()`. Still does not re-raise, so a failing health check cannot abort
  bootstrap.

### Internal / tooling

Not consumer-facing, but relevant if you build against this repo:

- Ruff configuration consolidated into `pyproject.toml`. A root `ruff.toml` had been shadowing
  it entirely (ruff picks one config file; it does not merge), so the intended rule set had
  never run. Now uses `select` rather than `extend-select`, making the rule set independent of
  the installed ruff version. ~170 findings surfaced and were fixed.
- `pre_commit.ps1` replaced by `scripts/ci-local.ps1`: captures a full run transcript to
  `logs/`, runs every step instead of stopping at the first failure, scans the test log for
  `WARNING`/`ERROR`/`CRITICAL` records, and prints a machine-readable result block. Also fixes
  a false-positive where a tool missing from `PATH` was reported as a passing step.
- Two new guard tests: `tests/test_all_modules_importable.py` (every module must import; public
  interface annotations must resolve) and `tests/test_agents_docs_resolve.py` (documentation
  claims must resolve against the real tree).
- `.agents/` documentation rewritten against a real sample app (`examples/student_management/`)
  rather than from memory — see `Tasks/epics/EPIC-002_engine_sample_app_and_doc_rewrite/`.

### Known issues

- `mypy sagittarius_engine tests` reports ~27 pre-existing errors. Verified present before this
  release's work; tracked in `Tasks/backlog/TASK-021`. `scripts/ci-local.ps1` fails on this step.
- No `py.typed` marker, so consumers get no type information despite the codebase being fully
  annotated (`TASK-027`).
- No `LICENSE` file, though `pyproject.toml` declares MIT (`TASK-022`).
- `mkdocs.yml` still points at a `docs/` tree deleted in `a338d42` (`BUG-002`).
