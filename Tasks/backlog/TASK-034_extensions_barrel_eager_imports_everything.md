# TASK-034: `extensions/__init__.py` is a barrel that eagerly imports every extension

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

- [TASK-031](../completed/TASK-031_top_level_package_eagerly_imports_persistence.md) — the
  narrower fix (package root) that surfaced this broader question.
