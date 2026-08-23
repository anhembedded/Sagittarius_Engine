# TASK-025: `infrastructure/persistence/` is an unimportable dead package

> **Closed 2026-08-23.** Requirement 1 done — directory deleted. Requirement 2 done — audited
> `Sagittarius_Elite_Warrior` (31 engine modules, 281 symbols) and confirmed no reference to
> it. Requirement 3 done — `tests/test_all_modules_importable.py` now imports every module in
> the package (159 parametrised cases) and additionally forces annotation resolution on the
> public interfaces, catching the sibling `ITaskHandle` class of bug. Verified against a
> deliberately reintroduced defect.

## Description

`sagittarius_engine/infrastructure/persistence/` contains exactly one file, and importing the
package raises:

```
ModuleNotFoundError: No module named
'sagittarius_engine.infrastructure.persistence.i_thread_manager'
```

The whole of `__init__.py`:

```python
from .i_thread_manager import IThreadManager

__all__ = [
    "IThreadManager",
]
```

Commit `85e5576` ("refactor: Move misplaced interfaces from infrastructure to interfaces
layer") moved `i_thread_manager.py` to `sagittarius_engine/interfaces/`, but left this
re-export behind pointing at the old location. `IThreadManager` now lives at
`sagittarius_engine/interfaces/i_thread_manager.py:7`.

Found by walking every module in the package and importing it — 1 failure out of the whole
tree, this one.

## Why it survived

Nothing imports it. `grep` across `sagittarius_engine/`, `examples/`, `tools/`, and `tests/`
finds no importer (the hits for "persistence" are all `extensions/persistence/` or the sample
app's own `examples/student_management/infrastructure/persistence/`, both unrelated). So it
breaks nothing today — it is a landmine, not a fire: the first consumer to write
`from sagittarius_engine.infrastructure import persistence` gets an ImportError with a
confusing message about a file that hasn't existed since `85e5576`.

It also means **no test imports every engine module.** That absence is the more interesting
finding; see requirement 3.

## Requirements

1. **Delete the directory.** Commit `85e5576`'s stated intent was that interfaces do not belong
   in `infrastructure/`; finishing that move means removing the husk, not repairing the
   re-export. (Repairing it — pointing `__init__.py` at `interfaces.i_thread_manager` — would
   re-create exactly the misplaced re-export that commit set out to remove.)
2. Confirm no external consumer depends on the path before deleting. Given it has raised
   ImportError since `85e5576`, no working consumer *can* depend on it — but check the
   `Sagittarius_Elite_Warrior` app, which is this engine's main real consumer.
3. **Add a test that imports every module under `sagittarius_engine/`** and fails on any
   ImportError. It is ~10 lines with `pkgutil.walk_packages`, it would have caught this the day
   `85e5576` landed, and it catches the entire class of "refactor left a dangling re-export."
   This is the durable part of the task.

## Priority

P2 — nothing is broken right now, but it is a trap with a misleading error message, and
requirement 3 pays for itself.

## Category

Infrastructure / Cleanup

## Related

- [TASK-023](../backlog/TASK-023_ci_matrix_hides_312_313_breakage.md) — the import-everything test asked
  for here would also catch 3.12-only import failures, if run on the full version matrix.
