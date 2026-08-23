# EPIC-004 — Sharded-SQLite Manager & Elite Warrior Migration

**Status:** ✅ Completed 2026-08-23 (3/3 subtasks done)
**Category:** Persistence / Extensions
**Priority:** P2
**Follows:** [EPIC-003](../EPIC-003_database_extension_multi_db/README.md)

---

## 🎯 Objective

`EPIC-003` established that `DatabaseExtension` can own several named databases. This epic
answers the question that immediately followed: **`Sagittarius_Elite_Warrior` already had a
working sharded-SQLite layer of its own — why was none of it in the engine?**

Reading that app's `DatabaseManager` in full, essentially all of it turned out to be generic
infrastructure — "one SQLite file per shard name" — with only two app-specific things in it:
the fact that a shard happens to be a *trading symbol*, and the app's own `Base.metadata`.
Everything else (lazy creation, WAL tuning, thread-safe connect args, name validation,
path-traversal containment, file lifecycle, vacuum) is what any app doing per-tenant or
per-partition SQLite has to get right, and had been solved once, privately, in an app.

So: move the generic part into the engine, then migrate the app onto it.

## 🧭 Why this direction, and why now

The user's framing was decisive on two points:

- **"Whatever can be common should go into the engine."** The alternative — leaving
  `SqliteShardManager` out and having Elite keep its own copy — would mean the next consumer
  needing sharded SQLite rediscovers WAL-per-connection and `check_same_thread` the hard way.
- **"No need to worry about risk, there's no release yet."** `IDatabaseManager` was added
  earlier the same day and never published, so its signature could be corrected freely rather
  than grown a compatibility shim. `add_database()` gaining `**engine_options` is exactly that
  correction — without it, `connect_args` was unreachable and the interface was unusable for
  any threaded SQLite app, Elite included.

Set against that, the *app's* behaviour was treated as fixed: the user asked explicitly to
watch for regressions, so Elite's public `DatabaseManager` API is byte-identical after the
migration and all eleven of its call sites are untouched.

## 🗂️ Subtasks

| ID | Title | Status |
| :--- | :--- | :---: |
| **[EPIC-004A](completed/EPIC-004A_sqlite_shard_manager.md)** | `SqliteShardManager` in the engine + `IDatabaseManager`/`ISession` gaps closed | ✅ Completed |
| **[EPIC-004B](completed/EPIC-004B_release_2_3_0.md)** | Release `2.3.0`, build, install into Elite, verify upgrade alone is clean | ✅ Completed |
| **[EPIC-004C](completed/EPIC-004C_elite_migration.md)** | Migrate Elite's `DatabaseManager` onto `SqliteShardManager` | ✅ Completed |

## 📐 Scope

- **In scope:** `SqliteShardManager`/`SqliteShardConfig`; `**engine_options` on
  `add_database`; `dispose_all()` on `IDatabaseManager`; `connection()` on `ISession`;
  engine `2.3.0`; Elite's `DatabaseManager` reduced to a façade over the engine class.
- **Out of scope:** changing Elite's repository layer or any of its call sites; moving
  Elite's `models.Base` or its symbol semantics into the engine (those are genuinely
  app-specific); wiring `SqliteShardManager` into `DatabaseExtension`'s config (a sharded
  file layout is a deliberate choice an app makes, not something to infer from a URL).

## ✅ Verification — the regression argument

Elite is a live trading bot, so "no regression" was established by measurement, not assertion,
against a baseline captured **before** anything changed:

| Stage | Main suite | Sanity | Gate |
| :--- | ---: | ---: | :---: |
| Baseline (engine `2.2.0`, original Elite) | 1776 passed | 50 passed | PASS |
| Engine `2.3.0` installed, Elite untouched | 1776 passed | 50 passed | PASS |
| After migration | **1780 passed** | 50 passed | PASS |

The `+4` is fully accounted for: `test_security.py` went from 2 tests to 6 when its single
monkeypatched case was replaced by a 5-way parametrized one (see EPIC-004C). No test was lost
and none was weakened; both post-change runs were verified by grepping the gate's own log file
for `FAILED`/`ResourceWarning`/`Traceback`, per that script's own instruction.

Behaviour that Elite depended on but never had a test for was verified directly against the
migrated code: `PRAGMA journal_mode` → `wal`, `PRAGMA synchronous` → `1` (NORMAL), the app's
`klines` table created on a fresh shard. The engine now has tests for all three
(`tests/extensions/persistence/test_sqlite_shard_manager.py`), so they cannot regress silently
again.

## Related

- [`EPIC-003`](../EPIC-003_database_extension_multi_db/README.md) — added `IDatabaseManager`,
  which this epic corrects and extends.
- `.agents/context/configuration.md` — `database.url` / `database.shards` / `SqliteShardManager`.
