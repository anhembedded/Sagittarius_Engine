# TASK-034: `extensions/__init__.py` is a barrel that eagerly imports every extension

- **Status**: ✅ Completed
- **Completed Date**: 2026-08-24

## Description

`sagittarius_engine/extensions/__init__.py` unconditionally imports every extension's public
symbols at module load time:

```python
from .audit import AuditExtension, AuditService
from .cqrs import ICommand, IQuery
from .health.health_check_query import HealthCheckDTO, HealthCheckQuery
from .health.health_module import HealthExtension, HealthUpdatedEvent
from .logger.logger_module import LoggerExtension
from .persistence import (
    BaseRepository, DatabaseExtension, ISession,
    SqlAlchemyExtension, SQLAlchemySessionAdapter,
)
from .thread_manager.thread_manager_module import ThreadManagerModule
```

Because Python always fully executes a package's `__init__.py` before any of its submodules,
**this makes all six extensions inseparable from each other.** `import
sagittarius_engine.extensions.cqrs` — needing nothing but `ICommand`/`IQuery` — runs every line
above first, including `.persistence`'s `SQLAlchemySessionAdapter` (guards its own `sqlalchemy`
import, so this doesn't crash) and `.thread_manager`. There is no way to import one extension
without importing all of them through this package structure.

## How this was found

Found 2026-08-23 while closing [`TASK-031`](../completed/TASK-031_top_level_package_eagerly_imports_persistence.md).
That task's original diagnosis was that `sagittarius_engine/__init__.py`'s
`from sagittarius_engine.extensions.persistence import BaseRepository` line alone caused bare
`import sagittarius_engine` to pull in the persistence extension. Removing only that line did
not fix it — a regression test written to prove the fix failed, which is what surfaced this. The
real chain: `sagittarius_engine/__init__.py` also did `from sagittarius_engine.extensions.cqrs
import ICommand, IQuery`, and importing any name from `extensions.cqrs` forces
`extensions/__init__.py` to execute in full first, which imports `.health.health_check_query`,
which imports `ISession` from `.persistence` directly. `TASK-031` was closed by removing all
three re-exports (`BaseRepository`, `ICommand`, `IQuery`) from the package root — sidestepping
the barrel rather than fixing it, since fixing the barrel itself is a larger, separate question.

## Why it might matter

Today, mostly a distribution-size and clarity issue, not a functional one — every extension's
own imports are individually guarded where they have optional dependencies (`persistence`
guards `sqlalchemy`), so nothing crashes. But:

- A consumer who wants only `ThreadManagerModule` pays the import cost of `audit`, `cqrs`,
  `health`, `logger`, and `persistence` too, every time.
- It works against the extension model `architecture.md` describes (opt-in feature packages,
  each independently composable) — the package structure currently contradicts that by wiring
  every extension's import together at the barrel level, even though each extension's own
  runtime behavior (via `IExtension.register`) is correctly opt-in.
- `health_check_query.py` importing `persistence.ISession` directly is itself a smaller instance
  of the same shape one level down — the health extension optionally checking database health
  is reasonable, but doing so via a hard top-level import means health is never really optional
  either, import-wise.

## Requirements

1. Decide whether `extensions/__init__.py` should become lazy (e.g. `__getattr__`-based PEP 562
   lazy attribute access, resolving each name to its owning submodule only on first use) or
   whether the barrel convenience is worth keeping as-is, given nothing crashes today.
2. If made lazy: verify every existing import path still works
   (`from sagittarius_engine.extensions import HealthExtension`, deep imports, etc.), and add a
   regression test that imports exactly one extension submodule and asserts the others are not
   in `sys.modules` — the same shape as `TASK-031`'s guard, one level down.
3. Consider `health_check_query.py`'s direct `ISession` import from `persistence` on its own
   merits regardless of the barrel decision — health checking a database is optional
   functionality gated by whether `ISession` is registered in the container at runtime, but the
   import itself is not optional today.

## Priority

P3 — no runtime error, and every extension's own dependency is individually guarded. Structural
cleanup, not a live defect.

## Category

Architecture / Package Boundaries

## Related

- [TASK-031](TASK-031_top_level_package_eagerly_imports_persistence.md) — the
  narrower fix (package root) that surfaced this broader question.

## Implementation

1. **`extensions/__init__.py` is now lazy** — PEP 562 `__getattr__`/`__dir__`, resolving each
   name in `__all__` against a `_LAZY_ATTRS: dict[str, str]` map (name → owning submodule) and
   importing only that submodule on first access, caching the result in `globals()`. `__all__`
   itself is unchanged (still the exhaustive public surface); only how each name gets populated
   changed. Chose lazy over "keep as-is" (requirement 1): `grep` across both this repo's own
   source/tests/examples/tools and `Sagittarius_Elite_Warrior` confirmed zero real usage of the
   barrel import path (`from sagittarius_engine.extensions import X`) anywhere — every real
   caller already imports the deep submodule path directly, unaffected by this change — so the
   eager barrel had a real cost (importing all six extensions' modules, guarded-persistence
   included, for anyone touching any one of them) and no offsetting benefit.
2. **`health_check_query.py`** (requirement 3) now imports `ISession` from the leaf module
   `sagittarius_engine.extensions.persistence.i_session` instead of the `persistence` package
   `__init__`, which itself eagerly imports `database_module.py` and
   `sqlalchemy_session_adapter.py` — unnecessary for a health check that only needs the pure
   interface for DI resolution/typing. `transaction_middleware.py` has the same package-level
   import but was left as-is: it already lives inside `extensions/persistence/`, so it pays that
   cost anyway as a side effect of being a sibling submodule — the leaf import only saves
   anything for a caller outside the package, which `health_check_query.py` is and
   `transaction_middleware.py` is not.
3. **Four new tests** in `tests/test_architecture.py` (requirement 2), next to `TASK-031`'s own
   guard: `test_extensions_barrel_imports_only_the_requested_submodule` (subprocess-isolated —
   deep-importing `.cqrs` alone must not pull in `.audit`/`.health`/`.logger`/`.persistence`/
   `.thread_manager`), `test_extensions_getattr_lazy_resolves_only_the_owning_submodule`
   (same shape, via the barrel-attribute path `__getattr__` itself exists for),
   `test_extensions_lazy_attrs_cover_all_public_names_and_resolve` (`_LAZY_ATTRS` and `__all__`
   can't drift apart, and every entry actually resolves), and
   `test_extensions_getattr_unknown_name_raises_attribute_error` (PEP 562's contract — a name
   this module doesn't own must raise `AttributeError`, not return `None`).
4. **Doc-code-sync**: `sagittarius_engine/__init__.py`'s own comment (from `TASK-031`) described
   the barrel as eager in the present tense — updated to past tense plus a pointer at this task,
   since that claim would otherwise go stale the moment this file shipped. `test_architecture.py`'s
   `test_bare_import_does_not_pull_in_any_extension` docstring updated the same way.

## Verification

Full `pwsh ./scripts/ci-local.ps1` run (after installing this repo's own declared
`PySide6-Fluent-Widgets` dependency — see Surprising Findings below): ruff lint ✅, ruff format
✅, mypy (371 files) ✅, Architecture Tests (8/8, including the four new ones) ✅. Pytest full
suite: 888 passed, 10 skipped, 1 failed, 88.22% coverage (gate is 80%). The one failure
(`test_gallery_emits_no_qml_runtime_warnings`, a missing-system-font Qt warning) was verified
via `git stash` to occur identically with none of this task's changes applied — pre-existing,
unrelated, not fixed here (see Surprising Findings).

## Surprising Findings (`surprising-findings.md`)

- **The full test suite could not run at all on this machine before this session**, for a
  reason unrelated to this task: `requirements.txt` declares `PySide6-Fluent-Widgets`
  (`qfluentwidgets`, added in `TASK-037` for `examples/student_management`'s Fluent-styled
  QtWidgets backend) but this checkout has no `.venv` and the system Python it fell back to
  never had that package installed — collection failed on the two `qfluentwidgets`-based
  example test files with no summary line at all. Installed it (`pip install
  PySide6-Fluent-Widgets`, no version bump to the already-installed `PySide6==6.11.1`) to get a
  real gate run; not a code fix, just completing this session's own environment setup per
  `install-rule.md` §1.
- **One pre-existing, unrelated test failure remains**: `test_gallery_emits_no_qml_runtime_warnings`
  fails on `main` with or without this task's changes (confirmed via `git stash`) — Qt reports
  `QFontDatabase: Cannot find font directory .../PySide6/lib/fonts` because "Qt no longer ships
  fonts." Not filed as a bug anywhere in `Tasks/`; flagged separately rather than fixed here,
  since it's an environment/deployment question (which fonts, deployed how) outside this task's
  scope.
