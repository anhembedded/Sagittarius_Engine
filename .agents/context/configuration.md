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

## Extensions with their own config

Some extensions accept parameters directly at construction instead of going through
`IConfig` — e.g. `AuditExtension(port=8765)`. Tools built on top of the engine (like
`tools/audit_dashboard`) manage their own configuration independently of the engine's
`IConfig` entirely.
