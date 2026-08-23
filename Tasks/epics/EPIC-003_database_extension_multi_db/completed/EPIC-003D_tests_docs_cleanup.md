# EPIC-003D — Test Suite Expansion, Docs, Cleanup, Bookkeeping

**Epic:** [EPIC-003 — `DatabaseExtension` Multi-Database Support](../README.md)
**Status:** ✅ Completed (2026-08-23)
**Category:** Persistence / Extensions / Documentation
**Priority:** P2
**Depends on:** [EPIC-003C](EPIC-003C_runtime_add_remove_verification.md)

---

## 🎯 Summary & Objective

Close out the epic: bring `DatabaseExtension`'s own test coverage from 1 test to real
coverage of both config paths, document the new `database.shards` shape where a future
session will actually look for it, delete the `TASK-019` workaround now that the real fix
exists, and update the task board.

## What was done

- **`tests/extensions/test_database_module.py`** — expanded from 1 test (sqlalchemy-not-
  installed warning) to 9: legacy `database.url` registers `ISession`+`Engine`+manager
  correctly (and the manager's `get_session("default")` is identity-equal to
  `resolve(ISession)`, proving the bridge rather than parallel construction); missing-url
  falls back to in-memory SQLite in development; missing-url raises in production;
  `database.shards` registers the manager **without** default `ISession`/`Engine` singletons
  (asserted via `DependencyResolutionError`, locking in the documented ambiguity trade-off);
  missing shard key raises `DatabaseNotFoundError`; `IConfig`-resolution failure falls back in
  development and raises in production; logger receives an info message on success.
- **`.agents/context/configuration.md`** — new section documenting `database.url` vs
  `database.shards`, including why `ISession`/`Engine` aren't registered in the shards case.
- **`examples/student_management/infrastructure/persistence/extension.py`** — deleted the
  `TASK-019` workaround (a second, throwaway `Engine` + a `ValueError` guard against
  `:memory:`); replaced with `context.container.resolve(Engine)`. Confirmed via 37 sample-app
  tests still passing.
- **`examples/student_management/docs/persistence_and_transactions.md`** — rewrote the
  "schema-creation gap" section to describe the fix instead of the workaround.
- **`Tasks/README.md`** — removed `TASK-019`'s backlog row, added `EPIC-003`'s link row.
- **`Tasks/backlog/TASK-019_database_extension_expose_engine.md`** — moved into
  `Tasks/epics/EPIC-003_database_extension_multi_db/` with a "Superseded by EPIC-003B" header,
  kept as historical record rather than deleted.
- This epic's own `README.md` and all four subtask files (`EPIC-003A`–`D`) written.

## Verification

- `pytest tests/extensions/test_database_module.py -v` — 9/9 passed.
- `pytest tests/ --ignore=tests/runtime/benchmark_runtime.py -q` — full suite green.
- `pwsh -NoProfile -File scripts/ci-local.ps1 -Full` — `RESULT: PASS`, verified against the
  actual log file (grepped for `FAILED|ERROR|Traceback`), not just console output.
