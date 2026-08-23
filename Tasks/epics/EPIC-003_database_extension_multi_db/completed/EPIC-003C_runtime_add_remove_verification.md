# EPIC-003C — Verify Runtime `add_database`/`remove_database` After Boot

**Epic:** [EPIC-003 — `DatabaseExtension` Multi-Database Support](../README.md)
**Status:** ✅ Completed (2026-08-23)
**Category:** Persistence / Extensions
**Priority:** P2
**Depends on:** [EPIC-003B](EPIC-003B_wire_database_extension.md)

---

## 🎯 Summary & Objective

The motivating case for this epic (a trading bot sharding SQLite per traded symbol) creates
and destroys databases **at runtime**, not just at boot — a symbol gets added to or dropped
from a watchlist mid-run. `IDatabaseManager.add_database`/`remove_database` were built in
EPIC-003A and exercised directly there, but never proven to work through the actual path a
real consumer would use: resolve the manager from a container **after** `app.boot()` has
already run `DatabaseExtension.register()`, then mutate it.

## What was built

`tests/extensions/persistence/test_database_extension_runtime.py` — 3 integration tests, each
building a real `App`/`StdLibContainer`/`MemoryEventBus`, registering `DatabaseExtension`,
calling `app.boot()`, and only then resolving `IDatabaseManager`:

- Add a database after boot — immediately usable (`get_session` returns a working session).
- Remove a database after boot — disposed, and subsequent lookups raise
  `DatabaseNotFoundError`.
- A full add/remove cycle against the `database.shards` path (mirrors the actual per-symbol
  shard lifecycle: start with one shard from config, add two more at runtime, remove one,
  confirm the remaining two still resolve correctly).

## Explicitly out of scope (per the epic's own design)

No auto-reload/file-watching/event-bus wiring to decide **when** to add/remove a database —
that belongs to the later, separate Elite Warrior migration task, which knows its own trigger
conditions (symbol added to/removed from watchlist). This subtask only proves the mechanism
itself works standalone in the engine.

## Verification

- `pytest tests/extensions/persistence/test_database_extension_runtime.py -v` — 3/3 passed.
- Full suite: `pytest tests/ --ignore=tests/runtime/benchmark_runtime.py -q` — 740 passed,
  7 skipped (up from 737 before this subtask).
