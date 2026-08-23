# EPIC-003 — `DatabaseExtension` Multi-Database Support

**Status:** ✅ Completed 2026-08-23 (4/4 subtasks done)
**Category:** Persistence / Extensions
**Priority:** P2
**Supersedes:** [`TASK-019`](TASK-019_database_extension_expose_engine.md)

---

## 🎯 Objective

`DatabaseExtension` (`sagittarius_engine/extensions/persistence/database_module.py`) only ever
supported **one** database per app: a single `database.url` config value, one `Engine`, one
`ISession` singleton in the container. The raw `Engine` itself was never exposed to consumers
at all (`TASK-019`).

This surfaced because `Sagittarius_Elite_Warrior` (a separate, live trading-bot app, not in
this repo) has its own fully independent SQLAlchemy persistence layer that shards SQLite
**per trading symbol** — one `Engine` per symbol, created/destroyed dynamically at runtime —
and never adopted `DatabaseExtension` at all, because it structurally couldn't: there was no
way to register more than one database. This epic builds the engine-side capability a future
migration onto `DatabaseExtension` would need, verified standalone inside this repo first.

**Explicitly out of scope for this epic:** actually migrating `Sagittarius_Elite_Warrior` onto
`DatabaseExtension`/`IDatabaseManager`. That's a separate, later, cross-repo task once this
epic's mechanism is proven clean in isolation — which it now is.

## 🧭 Design decision: a manager singleton, not a container change

The container (`StdLibContainer`) only supports one singleton per **type** — registering the
same type twice silently overwrites (last write wins), and no extension in the repo does
keyed/multi-instance registration. Changing `IContainer`'s core interface to support
named/keyed resolution would touch every extension in the repo for one feature's benefit.

Instead: `IDatabaseManager` is **one** new abstraction, registered as **one** container
singleton, that internally owns a `dict[str, ...]` of named engines/sessions. The
single-database case is just the multi-database case with one entry keyed `"default"` — this
is what lets the legacy `database.url` config path and the new `database.shards` path share
one implementation instead of two, and it's why backward compatibility didn't require any
special-casing beyond "register the compat singletons only when there's exactly one database."

**Rejected alternatives:**
- Keyed `container.resolve(ISession, name=...)` — changes `IContainer` for every extension.
- Synthetic per-shard types (`type("ISession_orders", (ISession,), {})}`) registered normally
  — fights the container's `resolve(type)` contract, breaks `isinstance`/mypy, can't support
  dynamic add/remove without generating new types at runtime.

## 🗂️ Subtasks

| ID | Title | Status |
| :--- | :--- | :---: |
| **[EPIC-003A](completed/EPIC-003A_database_manager_interface_and_impl.md)** | `IDatabaseManager` interface + `SqlAlchemyDatabaseManager` implementation | ✅ Completed |
| **[EPIC-003B](completed/EPIC-003B_wire_database_extension.md)** | Wire `DatabaseExtension` to the manager; supersede `TASK-019` | ✅ Completed |
| **[EPIC-003C](completed/EPIC-003C_runtime_add_remove_verification.md)** | Verify runtime `add_database`/`remove_database` after boot | ✅ Completed |
| **[EPIC-003D](completed/EPIC-003D_tests_docs_cleanup.md)** | Test suite expansion, docs, cleanup, bookkeeping | ✅ Completed |

## 📐 Scope

- **In scope:** `IDatabaseManager`/`SqlAlchemyDatabaseManager`; `DatabaseExtension` rewrite
  supporting both `database.url` (unchanged behavior) and `database.shards` (new); raw
  `Engine` exposure (closes `TASK-019`); runtime add/remove verification; test coverage;
  `.agents/context/configuration.md` update; deleting `student_management`'s `TASK-019`
  workaround in favor of the real fix.
- **Out of scope:** migrating `Sagittarius_Elite_Warrior` onto this mechanism; any config-driven
  auto-reload/hot-shard-discovery orchestration (the later migration's problem, since it knows
  its own trigger conditions — symbol added to/removed from a watchlist, etc.).

## ✅ Verification (whole epic)

- `pwsh -NoProfile -File scripts/ci-local.ps1 -Full` — green (ruff, mypy strict, pytest ≥80%
  coverage, architecture boundary tests), verified by reading the actual log file, not just
  console output.
- Full pytest suite: 740+ passed (up from 737 pre-epic), 7 skipped, 0 failed.
- `mypy sagittarius_engine tests examples tools --ignore-missing-imports --follow-imports=skip`
  — clean.
- Sample app (`examples/student_management`) — 37/37 tests passed after both the
  `DatabaseExtension` rewrite and the `TASK-019` workaround deletion, proving the legacy
  `database.url` path works end-to-end through a real running app.

## Related

- [`TASK-019`](TASK-019_database_extension_expose_engine.md) — superseded, kept as historical
  record of the original finding.
- `.agents/context/configuration.md` — `database.url` vs `database.shards` documented there.
- `examples/student_management/docs/persistence_and_transactions.md` — sample app's own
  account of the schema-creation gap and its fix.
