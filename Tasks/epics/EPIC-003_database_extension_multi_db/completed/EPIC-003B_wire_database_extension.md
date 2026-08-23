# EPIC-003B — Wire `DatabaseExtension` to `IDatabaseManager`, Supersede `TASK-019`

**Epic:** [EPIC-003 — `DatabaseExtension` Multi-Database Support](../README.md)
**Status:** ✅ Completed (2026-08-23)
**Category:** Persistence / Extensions
**Priority:** P2
**Depends on:** [EPIC-003A](EPIC-003A_database_manager_interface_and_impl.md)

---

## 🎯 Summary & Objective

Rewrite `DatabaseExtension.register()` to build a `SqlAlchemyDatabaseManager` internally,
supporting two mutually-exclusive config shapes — the existing `database.url` (must keep
working byte-for-byte the same for every current consumer) and a new `database.shards`
(`dict[str, str]`) for multi-database consumers. Also close out
[`TASK-019`](../TASK-019_database_extension_expose_engine.md) — expose the raw `Engine` for the
first time — as a side effect of the same rewrite rather than as separate work.

## What changed

`sagittarius_engine/extensions/persistence/database_module.py`:

- **Legacy path unchanged in behavior:** `database.url` (a string) still builds one database
  named `"default"` and registers `ISession` **and** `Engine` singletons — every existing
  consumer (verified: `examples/student_management`, 37 sample-app tests) keeps working with
  zero changes to their own code.
- **New path:** `database.shards` (`dict[str, str]` of `name -> url`) registers each named
  database via the manager. **Deliberately does not register `ISession`/`Engine` singletons**
  in this branch — which shard would `container.resolve(ISession)` even mean? Multi-db
  consumers must resolve `IDatabaseManager` and call `get_session(name)`/`get_engine(name)`.
- **Always:** `IDatabaseManager` is registered as a container singleton regardless of which
  path was taken — the one sanctioned way to reach a raw `Engine` from now on.
- `sagittarius_engine/extensions/persistence/__init__.py` now exports `IDatabaseManager`,
  `DatabaseNotFoundError`, `DEFAULT_DB` (safe — `i_database_manager.py` has no `sqlalchemy`
  import, unlike the concrete `SqlAlchemyDatabaseManager`, which stays internal to
  `database_module.py`'s guarded `SQLALCHEMY_INSTALLED` import block).

`examples/student_management/infrastructure/persistence/extension.py` — deleted the
`TASK-019` workaround (a second, throwaway `Engine` rebuilt from the same config value, with a
`ValueError` guard against `:memory:` because two separate `:memory:` engines are two
unrelated databases). Replaced with `context.container.resolve(Engine)` — the same `Engine`
`DatabaseExtension` already built, so there's only ever one database, `:memory:` or file-based
alike. This was `TASK-019`'s own stated acceptance signal.

## Verification

- `pytest tests/extensions/test_database_module.py` — 1/1 (pre-existing "no sqlalchemy" test,
  confirmed still passing unchanged).
- `pytest tests/test_examples.py examples/student_management/tests/ -q` — 37/37 passed, proving
  the legacy `database.url` path works end-to-end through a real running app, not just mocks.
- `mypy sagittarius_engine tests examples tools --ignore-missing-imports --follow-imports=skip`
  — clean, 334 source files.
- Full suite: `pytest tests/ --ignore=tests/runtime/benchmark_runtime.py -q` — 740 passed,
  7 skipped.
