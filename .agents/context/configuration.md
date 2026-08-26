# Configuration

Rewritten 2026-08-23 — the previous version recommended `pydantic.BaseSettings` as *the*
pattern. That's not what the engine actually ships: `IConfig`'s real, working implementation
(`infrastructure/config/config_manager.py`'s `ConfigManager`) is a plain multi-source
JSON/env-var reader, verified end to end while building `examples/student_management/`.

## The real pattern — `ConfigManager`

```python
from sagittarius_engine.infrastructure.config.config_manager import ConfigManager

config = ConfigManager()
config.load_json("config.json")        # first source
config.load_env(prefix="MYAPP_")       # overrides JSON on collision
config.set("computed.key", value)      # in-memory override, e.g. a computed absolute path

value = config.get("some.key", default="fallback")
```

Sources merge in the order added — later sources override earlier ones on key collision
(`ConfigManager`'s own docstring, verified against `_load()`'s `dict.update()` loop). One JSON
source may be marked `writable=True` (`load_json(path, writable=True)`) so `config.save()`
persists later `set()` calls back to that file, merged onto its existing contents.

## A real trap: relative paths in `config.json`

A relative path written into a static JSON config file resolves against the **process's
current working directory** at the moment it's used — not against where `config.json` itself
lives. Verified in `examples/student_management/main.py`: `database.url` is deliberately
**not** left in `config.json` — it's computed in code
(`Path(__file__).resolve().parent / "data" / ...`) and injected via `config.set(...)`, so it's
immune to the caller's working directory. See the sample's own `docs/config_loading.md` for
the full account, including the one deliberate exception (a test-only `db_url` override
parameter for isolation).

## Registering `IConfig` so it's resolvable

`App(container, event_bus)` does **not** automatically bind either argument into the
container — only `app.event_bus`/`context.event_bus` reach `event_bus` directly.
`container.resolve(IConfig)` raises `DependencyResolutionError` unless the composition root
does this explicitly, before `app.boot()`:

```python
container.singleton(IConfig, config)
```

See the sample's `docs/bootstrap.md` for the same point applied to `IEventBus`.

## `DatabaseExtension`: one database or many (`database.url` vs `database.shards`)

`DatabaseExtension` (`extensions/persistence/database_module.py`) reads exactly one of two
config keys, mutually exclusive:

- **`database.url`** (a string) — the original, single-database shape. Registers `ISession`
  *and* the raw SQLAlchemy `Engine` as container singletons — `container.resolve(Engine)`
  works, `container.resolve(ISession)` works.
- **`database.shards`** (a `dict[str, str]` of `{name: url}`) — added in `EPIC-003` for
  consumers that need more than one database (the motivating case: a trading bot sharding
  SQLite per traded symbol). `ISession`/`Engine` are **not** registered as singletons in this
  case — which shard would `container.resolve(ISession)` even mean? — so shard consumers must
  resolve `IDatabaseManager` and call `get_session(name)` / `get_engine(name)` explicitly.

Either way, `IDatabaseManager` is always registered — it's the one sanctioned way to reach a
raw `Engine` for schema creation/DDL/reflection, and it supports adding/removing a database
*after* boot (`manager.add_database(name, url)` / `manager.remove_database(name)`), verified
by resolving it from a real, already-booted `App` and mutating it at runtime — see
`tests/extensions/persistence/test_database_extension_runtime.py`.

## One SQLite file per shard — `SqliteShardManager`

`database.shards` above expects you to know every database up front. When you don't — a shard
per tenant, per partition, per traded instrument, learned at runtime — construct
`SqliteShardManager` directly (`extensions/persistence/sqlite_shard_manager.py`, EPIC-004):

```python
from sagittarius_engine.extensions.persistence.sqlite_shard_manager import (
    IN_MEMORY, SqliteShardConfig, SqliteShardManager,
)

manager = SqliteShardManager(SqliteShardConfig(directory="data/", metadata=Base.metadata))
with manager.get_raw_session("BTCUSDT") as session:   # file created on first use
    ...
```

Import it from its own module, not from the `persistence` package: that package's `__init__`
is reached while booting the kernel, so re-exporting anything importing SQLAlchemy at module
scope would make SQLAlchemy mandatory just to start the engine (`SqlAlchemyDatabaseManager` is
kept out of the re-exports for the same reason).

It is an `IDatabaseManager`, so the usual session/engine/name/disposal methods work, plus
shard listing, removal, purging and vacuuming for the file lifecycle. Pass
`directory=IN_MEMORY` for tests — each shard gets its own shared-cache URI, so connections to
one shard see the same database while different shards stay isolated (plain `:memory:` would
give every connection its own empty one).

What it sets up for you, because each is easy to miss: WAL + `synchronous=NORMAL` applied on
**every** connection (SQLite scopes PRAGMAs per connection; applying them once at engine
creation silently does nothing for pooled connections), `check_same_thread=False` plus a lock
timeout so pooled connections survive threads, shard-name validation and path-traversal
containment, and `-wal`/`-shm` sidecar cleanup on removal. Override any of it via
`SqliteShardConfig`; `pragmas=()` disables the PRAGMAs entirely.

## Extensions with their own config

Some extensions accept parameters directly at construction instead of going through
`IConfig` — e.g. `DiagnosticsExtension(fail_fast=True)`, or `TraceServer(recorder, port=9999)`.
Tools and apps built on top of the engine manage their own configuration independently of
the engine's `IConfig` entirely.
