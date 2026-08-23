# TASK-019: `DatabaseExtension` gives no sanctioned way to reach the raw `Engine`

**Superseded 2026-08-23 by [`EPIC-003B`](../epics/EPIC-003_database_extension_multi_db/README.md).**
The suggested fix below (register the `Engine` as a container singleton) is exactly what
`EPIC-003B` did, plus multi-database/sharding support this task never anticipated needing.
Kept here as historical record — see the epic for the actual implementation.

**Priority:** P2
**Category:** Extensions / Persistence
**Found:** 2026-08-23, while building the `EPIC-002A` sample app
(`Tasks/epics/EPIC-002_engine_sample_app_and_doc_rewrite/`)

## Problem

`sagittarius_engine/extensions/persistence/database_module.py`'s `DatabaseExtension.register()`
creates a real SQLAlchemy `Engine`, wraps it in a `scoped_session`, and registers only the
wrapped `ISession` into the container:

```python
engine = create_engine(db_url)
session_factory = sessionmaker(bind=engine)
Session = scoped_session(session_factory)
session_adapter = SQLAlchemySessionAdapter(Session)
context.container.singleton(ISession, session_adapter)
```

The `engine` local variable is never put anywhere a consumer can reach it — not in the
container, not as an attribute on `ISession`/`SQLAlchemySessionAdapter`. Confirmed by
`grep -rn "singleton(Engine" sagittarius_engine/extensions/persistence/` (zero hits) and by
reading `ISession`/`SQLAlchemySessionAdapter` in full — neither exposes an `engine` property.

**Concrete consequence:** any consuming app that defines its own ORM models has no sanctioned
way to run `Base.metadata.create_all(engine)` (or any other engine-level operation — reflection,
raw DDL, connection pooling config inspection). `EPIC-002A`'s `StudentManagementExtension`
worked around this by creating a **second**, throwaway `Engine` from the same `database.url`
config value purely to call `create_all()`, then discarding it — see
`examples/student_management/infrastructure/persistence/extension.py` and
`examples/student_management/docs/persistence_and_transactions.md` for the workaround in
context. That workaround is acceptable for a sample app but means every real consumer of
`DatabaseExtension` either duplicates it or reaches around the extension entirely (e.g. builds
its own engine and never uses `DatabaseExtension` at all) — the extension isn't providing the
value it should for anything beyond simple query/session use.

## Suggested fix (not decided — flag to user before implementing)

Register the `Engine` itself into the container alongside `ISession`, e.g.
`context.container.singleton(Engine, engine)` (using SQLAlchemy's own `Engine` type as the
key — no new engine-side interface needed, since bringing in raw `sqlalchemy.Engine` as an
abstraction key doesn't leak framework detail into `interfaces/`, `database_module.py`
already imports SQLAlchemy directly). Consumers that need schema creation, reflection, or raw
DDL can then `container.resolve(Engine)`.

## Verification (once actioned)

- A consumer can resolve the real `Engine` from the container after `DatabaseExtension`
  registers.
- `EPIC-002A`'s workaround engine in `StudentManagementExtension` can be deleted in favor of
  the resolved one — that's the acceptance signal this task is actually fixed, not just
  patched around again.
