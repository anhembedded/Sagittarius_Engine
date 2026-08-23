# Changelog

All notable changes to Sagittarius Engine.

This file starts at `2.0.0`. Earlier versions (`1.0.0`–`1.5.0`) were released without one;
their history is in `git log`.

---

## [2.3.0] — 2026-08-23

Makes `DatabaseExtension` able to own more than one database (`EPIC-003`), then absorbs a
consuming app's hand-rolled sharded-SQLite layer into the engine as reusable infrastructure
(`EPIC-004`). No breaking changes for single-database consumers.

### Added

- **`IDatabaseManager` + `SqlAlchemyDatabaseManager`** (`EPIC-003A/B`). `DatabaseExtension`
  previously supported exactly one database — one `database.url`, one `ISession` singleton — and
  never exposed the SQLAlchemy `Engine` it built (`TASK-019`, now superseded). It now always
  registers an `IDatabaseManager`, which owns a *named* map of engines/sessions and is the
  sanctioned way to reach a raw `Engine` for schema creation, DDL, or reflection.

  A new `database.shards` config key (a `dict[str, str]` of name → URL) registers several
  databases at once. In that mode `ISession`/`Engine` are deliberately **not** registered as
  container singletons — which shard would `resolve(ISession)` mean? — so shard consumers go
  through `IDatabaseManager.get_session(name)` / `get_engine(name)`. The legacy `database.url`
  path is untouched and still registers both singletons.

- **`SqliteShardManager` + `SqliteShardConfig`** (`EPIC-004A`) — one SQLite file per shard name,
  created lazily on first use, with the parts that are easy to get wrong built in: WAL +
  `synchronous=NORMAL` pragmas applied per connection (not once at engine creation, which is the
  common bug), `check_same_thread=False` and a lock timeout so pooled connections survive
  threads, shard-name validation, path-traversal containment, and `list_shards`/`remove_shard`/
  `purge_all`/`vacuum`/`dispose_all` file management. Generalized from
  `Sagittarius_Elite_Warrior`'s own `DatabaseManager`, which sharded per traded symbol; nothing
  in it is trading-specific.

- **`ISession.connection()`** — the Core-connection escape hatch. Without it an `ISession`
  consumer had no way to drive a bulk `INSERT … ON CONFLICT` without per-row ORM overhead.

- **`IDatabaseManager.dispose_all()`** — closes every engine at shutdown or test teardown.
  Previously each database had to be removed one at a time, and forgetting left SQLite handles
  open (`ResourceWarning: unclosed database`).

### Changed

- **`IDatabaseManager.add_database()` accepts `**engine_options`**, forwarded to
  `create_engine`. Without this a caller could not set `connect_args`, so SQLite's
  `check_same_thread`/`timeout` were unreachable — unusable for any threaded app. This changes
  the signature of an interface added earlier the same day and never released.

## [2.2.0] — 2026-08-23

Ships the PEP 561 marker (`TASK-027`), so consumers finally get the engine's types. Also fixes a
packaging defect found while verifying that — one that affected **every wheel built from this
repo, including `2.0.0` and `2.1.0`**.

### Added

- **`sagittarius_engine/py.typed`.** The package is fully annotated and enforces strict typing on
  itself, but under PEP 561 none of that reached consumers: without this marker a type checker
  ignores an installed package's inline annotations and treats the whole library as `Any`.

  Expect your own type checker to surface **new errors in your code** after upgrading. They were
  always there — engine symbols were `Any`, so nothing could be checked against them. The primary
  consumer carries an explicit `ignore_missing_imports` override for `sagittarius_engine` whose
  own comment notes the failure "cascades into dependents", quietly shrinking how many of its
  files were fully checked. That override can now be dropped — verified by removing it and
  running `Sagittarius_Elite_Warrior`'s own mypy invocation against the real installed `2.2.0`:
  **`Success: no issues found in 134 source files`**. Its own runtime check (`ci-local.ps1
  -Full`) also passes clean on the same install: `RESULT: PASS`, 1776 tests, all 282 engine
  symbols it imports still resolve.

### Fixed

- **Wheels shipped stale files that do not exist in the source tree.** `setuptools` copies
  `build/lib/` into the wheel wholesale; `package-data` governs what is copied *into* that
  directory, but never removes what an earlier build left behind. Because `build/` is gitignored,
  this was invisible to `git status` and persisted indefinitely.

  Measured on 2026-08-23: a wheel built without cleaning contained **9 stale assets** under
  `extensions/pyside_mvc/QmlShared/` — `BaseCard.qml`, `LogPanel.qml`, `StatefulButton.qml`,
  `StyledCheck.qml`, `TimeRangeCard.qml`, `DateTimePicker.qml`, `FieldBackground.qml`,
  `OverlayHost.qml` and `qmldir` — all left over from the `2.0.0` rename that deleted them, and
  none present in the source tree. `rm -rf build dist` before building drops that to **0**.

  The practical effect: a wheel was not reproducible from its source, and it re-registered the
  `QmlShared` QML module that `2.0.0` explicitly removed — partially undoing the documented
  rename for anyone installing the wheel. `2.0.0` and `2.1.0` wheels are affected if they were
  built on a dirty tree; **rebuild them clean if you distributed either.**

  Guarded now by `tests/test_py_typed_marker.py`, which asserts both that the marker reaches the
  wheel and that no stale `QmlShared` asset does.

### Internal / tooling

- **New rule: `.agents/rules/release.md`** — the release process, with each step tied to the
  failure that motivated it: choose the version from `git diff <last-tag>..HEAD` rather than from
  memory (how `2.0.0` missed its own largest breaking change), always build clean (above), verify
  the wheel's contents instead of trusting `package-data`, and push tags explicitly because
  `git push` does not push them (how `v2.1.0` ended up local-only while its release commit was
  public). Routed from `ONBOARDING.md` §5.

### Known issues

> **Correction, same day.** The mypy line below was accurate when this entry was drafted, then
> `TASK-032` merged into `main` — landing on top of this release's own commit in the branch
> history — before this entry was actually released. Left as written rather than silently
> edited, per this file's own precedent (see `2.0.0`'s correction). Same lesson one level
> deeper this time: quoting a count from the moment a changelog entry is *drafted* isn't enough
> either — verify against the exact commit a tag actually points at, right before pushing that
> tag.

- ~~The gate's mypy step now reports **20** errors in 8 files, down from 24 at `2.1.0`~~ — `BUG-003`
  fixed the four `union-attr` errors in `kernel/dispatcher.py` that came from a `ILogger | None`
  annotation contradicting `IEngineContext`'s non-`None` guarantee, and `TASK-032` cleared the
  remainder the same day. **The mypy baseline is gone — `Success: no issues found in 260 source
  files`**, measured on this release's actual merged tree with the gate's exact invocation,
  `mypy sagittarius_engine tests --ignore-missing-imports --follow-imports=skip`. A red mypy
  step from here on is a real regression, not inherited debt — there is none left to blame.
- The gate can still report `RESULT: FAIL` on **one** test,
  `test_gallery_emits_no_qml_runtime_warnings`, on a machine whose PySide6 install ships no
  fonts (`QFontDatabase: Cannot find font directory ...`). This is **local-environment noise,
  not a repo defect** — nothing in this release touches QML, and the failure is about the host
  machine's Qt installation, not the package.
- Unchanged: no `LICENSE` despite `pyproject.toml` declaring MIT (`TASK-022`), `mkdocs.yml` points
  at a deleted tree (`BUG-002`), and the package root eagerly imports `extensions.persistence`
  (`TASK-031`).

`TASK-027`'s remaining requirement — dropping the `sagittarius_engine` override from the
consuming app's `pyproject.toml` and fixing what that reveals — is **not** done here: that is a
different repository, and this repo never writes to it (`ONBOARDING.md` §8). Checked from this
side, without modifying anything in that repo: a throwaway local copy of its `pyproject.toml`
with the override removed, run against the real installed `2.2.0`, reports **zero** new errors
across all 134 of its source files — dropping the override should be safe whenever that repo's
own maintainer chooses to do it.

---

## [2.1.0] — 2026-08-23

Production-readiness hardening (`TASK-017`): seven reliability and security issues, each with a
regression test (suite 698 → 706). Additive for anyone using the documented entry points — every
new parameter has a default preserving the previous behaviour. One narrow removal, below.

Each checklist item was re-verified against the tree before being changed, and two of the seven
did not match their own description: **issue 3 was already fixed** (`TransactionMiddleware` had
already moved to `extensions/persistence/`), and **issue 6's premise was wrong** — the audit
WebSocket already bound to `127.0.0.1`, not `0.0.0.0`.

### ⚠️ Breaking (narrow)

- **`DaemonThreadPoolExecutor` is removed** from `sagittarius_engine.runtime.tasks.task_manager`.
  It appears in no `__all__` and was an implementation detail of `TaskManager`, so consumers using
  the documented surface are unaffected — but a direct
  `from sagittarius_engine.runtime.tasks.task_manager import DaemonThreadPoolExecutor` now raises
  `ImportError`. There is no replacement: `TaskManager` uses the standard library's
  `ThreadPoolExecutor` directly.

  It subclassed `ThreadPoolExecutor` to start *daemon* worker threads by calling private CPython
  internals (`concurrent.futures.thread._worker`, `._threads_queues`), justified as making
  background threads "safe to kill on exit."

  **Measured on 2026-08-23, that justification did not hold.** A process that spawns a background
  task and exits without calling `TaskManager.shutdown()` blocks for the task's full duration —
  *identically* with the old class and with the plain stdlib executor (20s for a 20s task, both
  measured against the pre-change commit in a separate worktree). `concurrent.futures.thread._python_exit`
  joins every thread registered in `_threads_queues`, and the old class registered into it too, so
  the daemon flag never influenced interpreter shutdown at all. The class was reaching into
  private internals to achieve nothing. Exit-hang behaviour is therefore **unchanged** by this
  release — if you relied on `shutdown()` being called, you still must call it.

### Added

- **`App.stop(step_timeout: float = 10.0)`.** Each of the six shutdown steps now runs on its own
  bounded daemon thread. Previously a single extension whose `stop()` hung blocked every later
  step forever; now the step is logged as timed out and shutdown continues. Default preserves
  prior behaviour for anything that stops promptly.
- **`WebsocketBroadcaster(..., auth_token: str | None = None)`.** When set, a client must supply a
  matching `?token=...` query parameter; otherwise the connection is closed with code `4401`
  before any telemetry is sent. Defaults to `None` (accept any client), so existing deployments
  are unchanged — **set it explicitly for anything reachable beyond localhost.**
- **`IPCBroker(..., subscriber_put_timeout: float = 0.1)`.** Bounds how long the broker will wait
  on one subscriber's queue.
- **`task_manager.max_retained_tasks` configuration key**, read via `IConfig`, replacing a
  hardcoded cap of 50 finished tasks. Resolved lazily (`IConfig` is registered during boot, after
  `TaskManager.__init__` has run) and memoised; falls back to 50 when no `IConfig` is registered.

### Fixed

- **IPC broker deadlock.** `IPCBroker._run` called `sub_queue.put(...)` with no timeout while
  holding the broker lock. One full or hung subscriber blocked the broadcast loop indefinitely,
  starving every *other* subscriber as well as `add_subscriber`/`remove_subscriber`. The put is
  now bounded and `queue.Full` is caught.
- **DI container permanently losing a factory on a failed resolve.** `StdLibContainer.singleton()`
  registers a class as a lazy factory that pops itself first to break the `abstract == concrete`
  cycle. If `_resolve()` then raised — a dependency temporarily unavailable, say — the
  registration was gone for good and every later `resolve()` failed with "unregistered
  dependency". The factory is now restored on failure, so the call is retryable.
- **`HealthExtension`/task-manager cleanup paths** no longer depend on the removed executor hack.

### Changed — behaviour

- **The IPC broker now drops an event destined for a full subscriber queue**, logging a `WARNING`,
  rather than blocking until space is available. This is the deadlock fix, but it is an observable
  change: under sustained backpressure delivery is no longer guaranteed. Raise
  `subscriber_put_timeout` if a slow subscriber should be waited on rather than skipped.

### Known issues

Carried forward from `2.0.0`, none introduced here:

- The gate's own mypy step (`mypy sagittarius_engine tests --ignore-missing-imports
  --follow-imports=skip`) reports **24** errors across 9 files. None are in a file this release
  touched — verified. Tracked in `TASK-032`, split out of `TASK-021` req. 5;
  `scripts/ci-local.ps1` fails on this step.

  Note the number: `TASK-032` is titled "the 27-error mypy baseline" and states 27 "re-verified
  today", but the gate command measures **24** — confirmed three separate times on 2026-08-23,
  including on this release's merged tree. The 12-error figure elsewhere is `sagittarius_engine`
  alone, without `tests`. Whoever picks up `TASK-032` should re-measure with the gate's exact
  invocation before trusting any of these counts.
- No `py.typed` marker (`TASK-027`); no `LICENSE` file though `pyproject.toml` declares MIT
  (`TASK-022`); `mkdocs.yml` points at a deleted `docs/` tree (`BUG-002`).
- `sagittarius_engine/__init__.py` eagerly imports `extensions.persistence` for its
  `BaseRepository` re-export, so the package root pulls in an optional extension on any import
  (`TASK-031`). No error today — the extension guards its own `sqlalchemy` import.

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
