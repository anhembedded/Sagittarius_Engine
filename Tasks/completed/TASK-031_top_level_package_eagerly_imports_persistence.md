# TASK-031: `sagittarius_engine/__init__.py` eagerly imports `extensions.persistence`

> **Closed 2026-08-23 — the original diagnosis in this file was incomplete, and the fix
> attempt caught it.**
>
> Requirement 1's decision, made and then revised: initially decided to drop `BaseRepository`
> but keep `ICommand`/`IQuery`, reasoning that `extensions.cqrs` "carries none of
> `extensions.persistence`'s optional-dependency baggage." That reasoning turned out to be
> irrelevant to the actual mechanism — implementing just that partial removal and writing the
> regression requirement 3 asks for, the test **failed**. `sagittarius_engine.extensions` is a
> barrel (`extensions/__init__.py`) that eagerly imports every extension's public symbols,
> persistence's `ISession` included (via `.health.health_check_query`) — and Python always
> executes a parent package's `__init__.py` before any of its submodules, so importing
> `extensions.cqrs` alone was enough to trigger the whole barrel regardless of which name was
> asked for. There is no partial import possible through this package structure; keeping
> `ICommand`/`IQuery` at the top level cannot avoid pulling in persistence.
>
> Revised requirement 1's decision accordingly: **all three** (`BaseRepository`, `ICommand`,
> `IQuery`) removed from `sagittarius_engine/__init__.py`'s re-export list. Verified zero usage
> of any of the three via the top-level path anywhere in this repo (source, tests, examples) —
> every real usage already imports from `extensions.cqrs` / `extensions.persistence` directly,
> both unchanged.
>
> - **Req 2 — done.** No hits for any of the three names via the top-level path anywhere in
>   `.agents/`, `examples/`, `tests/`, `tools/`.
> - **Req 3 — done, strengthened.** The test asserts the stronger, more honest claim: that bare
>   `import sagittarius_engine` does not pull in `sagittarius_engine.extensions` **at all**, not
>   just persistence specifically — since the actual mechanism is barrel-wide, not
>   persistence-specific. `tests/test_architecture.py::test_bare_import_does_not_pull_in_any_extension`.
>
> **Filed, not fixed:** the barrel design itself —
> [`TASK-034`](TASK-034_extensions_barrel_eager_imports_everything.md). Making
> `extensions/__init__.py` lazy so individual extensions are actually independently importable
> is a larger, separate architecture decision than this task's original scope.

## Description

`sagittarius_engine/__init__.py` (the package root — imported the moment anyone does
`import sagittarius_engine` or `from sagittarius_engine.kernel import App`, since Python
imports parent packages first):

```python
from sagittarius_engine.extensions.cqrs import ICommand, IQuery
from sagittarius_engine.extensions.persistence import BaseRepository
from sagittarius_engine.interfaces.i_extension import ExtensionDescriptor, IExtension
from sagittarius_engine.kernel.app import App
from sagittarius_engine.kernel.context import EngineContext

__all__ = ["App", "EngineContext", "IExtension", "ExtensionDescriptor", "ICommand", "IQuery", "BaseRepository"]
```

The `from sagittarius_engine.extensions.persistence import BaseRepository` line means every
consumer of this library pulls in the persistence extension's four modules
(`database_module.py`, `i_session.py`, `repository.py`, `sqlalchemy_session_adapter.py`) on
package import, whether or not they use persistence at all — the exact coupling `TASK-017`
issue 3 ("Core Middleware Coupled to Extension") was filed to remove.

## Why this is separate from `TASK-017`

`TASK-017` issue 3 was specifically about `TransactionMiddleware` living in core `middleware/`
— that part is already fixed (it lives in `extensions/persistence/transaction_middleware.py`,
and core `middleware/__init__.py` has zero reference to persistence). Verified while closing
that issue: `database_module.py` guards its own `sqlalchemy` import in a `try/except ImportError`,
so this eager top-level import does **not** currently raise `ImportError` even with `sqlalchemy`
uninstalled (confirmed with `sys.modules['sqlalchemy'] = None` in a subprocess) — so it does not
reproduce `TASK-017`'s literal, stated test requirement ("no ImportError occurs"), which is why
it wasn't rolled into that task's fix.

It is nonetheless the same coupling one layer up: the package root, not just one middleware
class, still hard-depends on an optional extension. Left as its own task because fixing it means
removing `sagittarius_engine.BaseRepository` as a top-level re-export (a public-API-surface
change, not just an internal move) — `BaseRepository` would remain reachable at
`sagittarius_engine.extensions.persistence.BaseRepository` / `sagittarius_engine.extensions.BaseRepository`,
just not at the shortest path — which needed its own decision rather than being folded silently
into `TASK-017`'s close-out.

## Requirements

1. Decide whether `sagittarius_engine.BaseRepository` is meant to be part of the top-level public
   API (convenience re-export) or whether that was accidental drift. `ICommand`/`IQuery` (from
   `extensions.cqrs`) are re-exported the same way — if those are intentionally core-adjacent
   enough to keep at the top level, say why persistence isn't in the same category, or extend the
   same reasoning to it.
2. If removed: drop the import and the `__all__` entry, grep `.agents/`, `examples/`,
   `tests/`, `tools/` for `sagittarius_engine.BaseRepository`/`sagittarius_engine import BaseRepository`
   usage and update any hit (per `rules/doc-code-sync.md`).
3. Add a test mirroring `TASK-017`'s but for this exact case: import bare `sagittarius_engine`
   in a subprocess and assert `'sagittarius_engine.extensions.persistence'` is not pulled into
   `sys.modules` as a result — the stricter bar this task's own investigation used, which the
   package root currently fails.

## Priority

P3 — no runtime error today (the `sqlalchemy` guard already prevents that), so no urgency; this
is a structural/API-boundary cleanup, not a live defect.

## Category

Architecture / Package Boundaries

## Related

- [TASK-017](../completed/TASK-017_production_readiness_hardening.md) — issue 3, whose
  regression test (`tests/middleware/test_middleware.py::test_core_boot_does_not_require_persistence_extension`)
  found this while verifying the fix was complete.
