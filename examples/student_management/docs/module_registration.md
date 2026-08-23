# Module registration — why order isn't declarative, and why it matters here

Written 2026-08-23, at the point registration order was confirmed to actually matter (not
theorized) — removing it from `main.py` and re-running failed exactly as predicted.

## The dependency graph

```mermaid
flowchart LR
    subgraph "app.use(...) order — must be this order"
        A["LoggerExtension"] --> B["DatabaseExtension"]
        B --> C["StudentManagementExtension"]
    end

    B -. "registers ISession into container" .-> D[(Container)]
    C -. "resolves ISession from container" .-> D
    C -. "registers IStudentRepository into container" .-> D
    A -. "registers ILogger into container" .-> D
```

`StudentManagementExtension.register()` does `context.container.resolve(ISession)` — that
call fails immediately (`DependencyResolutionError`) unless `DatabaseExtension.register()`
already ran and bound `ISession`. `IExtension` itself declares no `dependencies` mechanism
that's enforced automatically at `app.use()` time (there's a `dependencies`/`priority`
attribute pattern visible in `ExtensionDescriptor`, but nothing in this app's three extensions
declares or needs it — the ordering here is a straight line, not a graph, so `app.use()` call
order is sufficient and simpler than reaching for that mechanism).

## What actually happens if the order is wrong

Verified 2026-08-23 by actually swapping the order (`app.use(StudentManagementExtension())`
before `app.use(DatabaseExtension())`) and running `app.boot()` — not assumed from reading the
code:

```
sagittarius_engine.exceptions.DependencyResolutionError:
Cannot instantiate abstract class <class 'sagittarius_engine.extensions.persistence.i_session.ISession'>
```

Thrown from inside `StudentManagementExtension.register()`, at `app.boot()` time — before any
command is ever dispatched. Worth noting the message names the *abstract* class being
resolved, not "no binding found" — the container's fallback path tries to instantiate
`ISession` itself when nothing bound it, and fails because it's an `ABC`. Still a loud,
immediate failure at boot, not a silent `None` or a late failure on first use — just not
phrased the way a first guess at the message would expect.

## The legacy `IModule` path was rejected for exactly this app

The deleted old sample used `IModule` (`kernel/extension_manager.py:22` calls it "a legacy
`IModule`" in the engine's own code) instead of `IExtension`. `IExtension` is what every other
shipped extension in this engine implements (`LoggerExtension`, `DatabaseExtension`,
`HealthExtension`, `AuditExtension`, `ThreadManagerExtension`) — using anything else here would
have made this app a worse reference, not a different-but-valid one.
