# EPIC-004C — Migrate Elite's `DatabaseManager` onto `SqliteShardManager`

**Epic:** [EPIC-004](../README.md)
**Status:** ✅ Completed (2026-08-23)
**Category:** Persistence — cross-repo (`Sagittarius_Elite_Warrior`)
**Depends on:** [EPIC-004B](EPIC-004B_release_2_3_0.md)

---

## 🎯 Objective

Delete Elite's copy of the generic sharding logic, keeping only what is genuinely the bot's:
that a shard is a *symbol*, and that the schema is `models.Base`. Public API unchanged, so
none of the eleven call sites move.

## What changed in `Sagittarius_Elite_Warrior`

`src/infrastructure/persistence/database_manager.py` went from ~190 lines of hand-rolled
sharding to a ~95-line façade holding a `SqliteShardManager`. Removed from the app entirely:
the symbol regex, the path-traversal check, the WAL/`synchronous` event listener, the
`connect_args`, the `sessionmaker` cache, the URL construction, the `-wal`/`-shm` file
cleanup, and the directory `makedirs`.

Deliberately **kept** in the app:

- `get_session()` still returns a raw SQLAlchemy `Session`, not `ISession` — the repository
  uses `Session.connection()` for bulk upserts and reads more naturally against the full
  surface. The engine exposes `get_raw_session()` precisely so a consumer can make this
  choice; wrapping and immediately unwrapping would have been churn for its own sake.
- The per-symbol `try/except` in `vacuum()` — one unreadable shard must not abort a
  maintenance sweep over the others. The engine's `vacuum()` is deliberately strict; this
  tolerance is the app's policy, not the engine's.
- The `logger` calls, on `App.Database`, which the app's log-panel UI filters on.

## Test changes — and why each was necessary, not convenient

Only two tests changed. Both were coupled to *internals* that moved, never to behaviour:

1. **`tests/unit/infrastructure/persistence/test_security.py`** monkeypatched
   `database_manager._VALID_SYMBOL_REGEX` to force the path-traversal branch. That symbol no
   longer exists in the app. Rewritten to assert the same guarantee through the public API —
   a 5-way parametrized case covering `../../../etc/passwd`, `../BTCUSDT`, `sub/dir`,
   `BTC USDT` and `""`, which is **broader** than the single case it replaced. The deeper
   defence it was really reaching for (containment holds even when the name pattern is
   permissive) is now an engine test, where the permissive pattern can actually be configured
   rather than monkeypatched. This is the entire `+4` in the suite total.

2. **`tests/integration/.../test_sqlalchemy_repository.py::test_multi_symbol_db_separation`**
   asserted `len(repo.db_manager._sessions) == 2` on a private dict that now lives inside the
   engine. Every behavioural assertion in that test already passed unchanged — the two shards
   were correctly separate. Replaced with `sorted(...list_shards()) == ["BTCUSDT", "ETHUSDT"]`,
   which states the same intent through the public API and is a better assertion than the one
   it replaced.

## Verification

Full gate `RESULT: PASS`, verified against the log file rather than console output:
**1780 passed** (baseline 1776, `+4` fully accounted for above), 50 sanity, no `FAILED`, no
`ResourceWarning`, no `Traceback`.

Behaviour the app depended on but never tested was checked directly against the migrated
code, since a passing suite would not have caught its loss: `PRAGMA journal_mode` → `wal`,
`PRAGMA synchronous` → `1` (NORMAL), and the `klines` table present on a freshly created
shard. All three are now covered by engine tests as well.
