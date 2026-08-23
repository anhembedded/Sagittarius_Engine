# Changelog

All notable changes to Sagittarius Engine.

This file starts at `2.0.0`. Earlier versions (`1.0.0`–`1.5.0`) were released without one;
their history is in `git log`.

---

## [2.0.0] — 2026-08-23

38 commits since `1.5.0`, and the release is genuinely breaking in several directions. **If you
consume `pyside_mvc`, read the QML module rename first — it will break every QML file you have.**

> **Correction, same day.** The first version of this entry listed only three breaking changes.
> It was written from *this session's* commits rather than from everything unreleased since
> `1.5.0`, and so missed the largest one: the QML module rename. That omission was caught the
> only way it could have been — by actually installing 2.0.0 into
> `Sagittarius_Elite_Warrior` and running its test suite, which went from green to **69
> failures**. A changelog assembled from recent memory instead of `git diff <last-tag>..HEAD`
> is exactly the kind of unverified claim this project keeps getting bitten by.

### ⚠️ Breaking

- **The QML module `QmlShared` is renamed to `Sagittarius.UI`, and the old name is gone.**
  This is the change most likely to break you. Every QML file that does:

  ```qml
  import QmlShared 1.0
  ```

  must become:

  ```qml
  import Sagittarius.UI 1.0
  ```

  Component names are unchanged (`BaseCard`, `LogPanel`, `TimeRangeCard`, `StatefulButton`,
  `StyledCheck`, `FieldBackground`, `DateTimePicker`), so the migration is a mechanical
  find-and-replace of the import line. Two components were added: `AppDataTable` and `AppModal`.

  Symptom if you miss it: `module "QmlShared" is not installed`, followed by a cascade of
  `TypeError: Cannot read property '<token>' of null` as every themed property fails to resolve,
  and `AttributeError: 'NoneType' object has no attribute ...` in any test that walks the QML
  item tree. The UI does not render.

  `1.5.0` shipped `extensions/pyside_mvc/QmlShared/*.qml` + `qmldir`; `2.0.0` ships
  `extensions/pyside_mvc/Sagittarius/UI/<Component>/<Component>.qml` + `qmldir` instead. The
  rename landed in commit `a4a3bdb`, after `1.5.0` was cut, so this is its first release.

- **`pyside_mvc`'s Python layout is reorganized by concern.** Most consumers are unaffected —
  the extension's top-level re-exports (`from sagittarius_engine.extensions.pyside_mvc import
  BasePresenter, QmlHostView, configure_app_qml, ...`) are unchanged and remain the supported
  entry point. But direct deep imports of moved modules will break:

  | Was | Now |
  | :--- | :--- |
  | `pyside_mvc.base_presenter` | `pyside_mvc.mvc.base_presenter` |
  | `pyside_mvc.presenter_manager` | `pyside_mvc.mvc.presenter_manager` |
  | `pyside_mvc.thread_affinity`, `thread_bridge`, `ui_action_events`, `ui_matrix_mixin`, `ui_watchdog` | `pyside_mvc.safety.<same>` |
  | `pyside_mvc.QmlShared.state_tokens`, `theme_bridge` | `pyside_mvc.tokens.<same>` |
  | `pyside_mvc.QmlShared.base_view_model`, `icon_image_provider`, `overlay_host`, `qml_host_view`, `qml_style`, `qml_value_normalizer` | `pyside_mvc.runtime.<same>` |

  `pyside_mvc.QmlShared.log_list_model` is deliberately kept as a compatibility shim, because
  the reference consumer imports it directly. Nothing else under `QmlShared` survives.

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

### Upgrade checklist

Verified against `Sagittarius_Elite_Warrior` on 2026-08-23:

1. You are on Python 3.14+. `pip` will refuse otherwise.
2. Replace `import QmlShared 1.0` with `import Sagittarius.UI 1.0` in **every** `.qml` file.
3. `grep` your Python for deep imports into `pyside_mvc.QmlShared.*` and the moved top-level
   modules; repoint per the table above, or switch to the top-level re-exports.
4. You were not using the scaffolding CLI (`sagittarius new ...` / `python -m tools.scaffold`).
   If you were, it is gone with no replacement.
5. Run your own test suite. On the reference consumer, steps 1–3 were what separated
   "69 failures" from a clean run.

### Known issues

- `mypy sagittarius_engine tests` reports ~27 pre-existing errors. Verified present before this
  release's work; tracked in `Tasks/backlog/TASK-021`. `scripts/ci-local.ps1` fails on this step.
- No `py.typed` marker, so consumers get no type information despite the codebase being fully
  annotated (`TASK-027`).
- No `LICENSE` file, though `pyproject.toml` declares MIT (`TASK-022`).
- `mkdocs.yml` still points at a `docs/` tree deleted in `a338d42` (`BUG-002`).
