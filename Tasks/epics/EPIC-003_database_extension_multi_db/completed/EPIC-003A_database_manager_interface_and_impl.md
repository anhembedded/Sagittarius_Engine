# EPIC-003A — `IDatabaseManager` Interface + `SqlAlchemyDatabaseManager` Implementation

**Epic:** [EPIC-003 — `DatabaseExtension` Multi-Database Support](../README.md)
**Status:** ✅ Completed (2026-08-23)
**Category:** Persistence / Extensions
**Priority:** P2
**Depends on:** nothing (first subtask)

---

## 🎯 Summary & Objective

Build the abstraction that lets one `DatabaseExtension` own more than one named database,
without touching `IContainer`'s core type-keyed resolution — the container only supports one
singleton per type, and no extension in the repo does keyed/multi-instance registration, so
changing it would ripple through every extension for one feature's benefit.

## What was built

- `sagittarius_engine/extensions/persistence/i_database_manager.py` — `IDatabaseManager(ABC)`:
  `add_database(name, url)`, `remove_database(name)`, `get_session(name=DEFAULT_DB)`,
  `get_engine(name=DEFAULT_DB)`, `names()`. Plus `DatabaseNotFoundError(KeyError)`, naming the
  requested key and known keys in its message.
- `sagittarius_engine/extensions/persistence/database_manager.py` — `SqlAlchemyDatabaseManager`,
  thread-safe (`threading.RLock`, matching `StdLibContainer`'s own locking pattern) around an
  internal `dict[str, _DatabaseEntry]` (engine + `SQLAlchemySessionAdapter` pair per name). The
  single-database case is just the multi-database case with one entry keyed `"default"` — this
  is what lets the legacy config path and the new shards path share one implementation.
- `tests/extensions/persistence/test_database_manager.py` — 7 direct unit tests: add/get
  round-trip, duplicate-name rejection, dispose-on-remove + subsequent lookup failure,
  unknown-name error on remove, error message names known databases, `names()` reflects
  add/remove sequence, and a 20-thread concurrent-add smoke test.

## Verification

- `pytest tests/extensions/persistence/test_database_manager.py -v` — 7/7 passed.
- `ruff check`/`ruff format --check` clean on both new files.
- `mypy sagittarius_engine tests --ignore-missing-imports --follow-imports=skip` — clean
  (no new errors introduced against the pre-existing 0-error baseline).
