# EPIC-004A — `SqliteShardManager` + `IDatabaseManager`/`ISession` Gaps

**Epic:** [EPIC-004](../README.md)
**Status:** ✅ Completed (2026-08-23)
**Category:** Persistence / Extensions
**Priority:** P2
**Depends on:** EPIC-003A/B

---

## 🎯 Objective

Move the generic half of `Sagittarius_Elite_Warrior`'s `DatabaseManager` into the engine, and
close the `IDatabaseManager` gaps that made it impossible to express in the first place.

## What was built

**New — `sagittarius_engine/extensions/persistence/sqlite_shard_manager.py`:**
`SqliteShardManager` + `SqliteShardConfig` + `IN_MEMORY`. One SQLite file per shard name,
under a configured directory, created lazily on first `get_session()`. Differs from
`SqlAlchemyDatabaseManager` in three ways that are the whole point:

- **Lazy** — shards are created on demand, because a caller usually cannot enumerate every
  shard at boot (a bot learns its symbols at runtime).
- **Fresh session per call** — so callers can hold independent transactions, where
  `SqlAlchemyDatabaseManager` hands back one shared adapter.
- **Owns files** — `remove_shard`/`purge_all` delete from disk, including the `-wal`/`-shm`
  sidecars that would otherwise resurrect deleted data.

Plus the parts that are easy to get subtly wrong, now in one place: WAL +
`synchronous=NORMAL` applied **per connection** via a `connect` event listener (SQLite scopes
PRAGMAs to the connection, and a pooled engine opens many — applying them once at creation is
the common bug), `check_same_thread=False` + a lock `timeout`, shard-name validation,
path-traversal containment kept as defence-in-depth even though names are pattern-checked,
optional `MetaData` for automatic schema creation, and `list_shards`/`vacuum`/`dispose_all`.

**Changed — `IDatabaseManager`:**

- `add_database(name, url, **engine_options)` — forwarded to `create_engine`. Without this
  `connect_args` was unreachable, so the interface could not express a threaded SQLite app at
  all. A signature change to an interface added the same day and never released.
- `dispose_all()` — added. Previously each database had to be removed one at a time, and
  forgetting left SQLite handles open (`ResourceWarning: unclosed database`).

**Changed — `ISession.connection()`:** the Core-connection escape hatch, with
`SQLAlchemySessionAdapter` implementing it. Without it, an `ISession` consumer had no way to
drive a bulk `INSERT … ON CONFLICT` without per-row ORM overhead — which is precisely what
Elite's repository does.

## Verification

`tests/extensions/persistence/test_sqlite_shard_manager.py` — 28 tests. The behavioural cases
deliberately mirror Elite's own `test_database_manager_shards.py`/`test_security.py`, since
proving the generalization lost nothing is what licensed EPIC-004C.

Two are worth calling out as genuine (not tautological) checks:
`test_pragmas_can_be_disabled` is the control that makes the WAL assertion meaningful — with
`pragmas=()` the journal mode is *not* WAL, so the passing case is measuring something.
`test_connect_args_actually_reach_the_driver` passes an argument `sqlite3.connect` rejects and
asserts it raises; a silently-dropped config would make that test fail. It initially did not
raise, which was a real finding about the test rather than the code — `create_engine` is lazy,
so the driver is only invoked on first `connect()`.

Gate: `ruff`/`ruff format`/`mypy` clean; mypy caught a real LSP violation on the way
(`get_session`/`get_engine` dropped the supertype's default argument).
