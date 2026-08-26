# Modules & Extensions

Rewritten 2026-08-23 — the previous version documented `IModule` as *the* module model. It
isn't: the engine's own code calls it *"a legacy `IModule`"*
(`kernel/extension_manager.py:22`), and every shipped extension implements `IExtension`
instead. See
[`AUDIT_REPORT.md`](../../Tasks/epics/EPIC-002_engine_sample_app_and_doc_rewrite/AUDIT_REPORT.md)
§1.1.

## `IExtension` — the real model

Every extension the engine ships (`LoggerExtension`, `DatabaseExtension`, `HealthExtension`,
`DiagnosticsExtension`, `ThreadManagerExtension`, and this repo's own sample app's
`StudentManagementExtension`/`PySideMvcExtension`) implements `IExtension`, generic over its
own context Protocol (`IExtension[ILoggerContext]`, etc. — see `rules/architecture.md`'s
"Prefer a narrow context Protocol" section).

**Two layers of lifecycle method, not one flat list** — see `rules/architecture.md`'s
"Extension lifecycle: override vs. call" for the full override-vs-call trap. Short version:

| Layer | Methods | Who calls them |
| :--- | :--- | :--- |
| Author (abstract, you implement) | `register`, `boot`, `shutdown` | Never called directly by the engine |
| Orchestrator (concrete, delegates by default) | `initialize`→`register`, `start`→`boot`, `stop`→`shutdown`, `dispose`→no-op | `ExtensionManager` calls these |
| Async hooks (concrete, no-op by default) | `boot_async`, `shutdown_async` | Scheduled on `AsyncRuntime` |

### Registration order — declarative, not just `app.use()` sequence

`ExtensionManager._build_and_sort()` performs a real topological sort keyed on
`descriptor.dependencies` — a list of **strings**, matched against another extension's
`descriptor.name` (defaults to the class name). Declare it:

```python
class StudentManagementExtension(IExtension[IStudentManagementContext]):
    dependencies = ["DatabaseExtension"]   # matches by name, real class need not be imported
    ...
```

Verified directly (`examples/student_management/infrastructure/persistence/extension.py`,
`docs/module_registration.md`): with this declared, `app.boot()` succeeds even if `app.use()`
was called in the wrong order — the sort corrects it before any `register()` runs. Without a
declared dependency, `app.use()` call order is the *only* thing establishing it, and getting
it wrong fails loudly at boot with `DependencyResolutionError` — not silently, but not
protected either. Prefer declaring dependencies over relying on call order once there's more
than one extension with a real ordering requirement.

## `IModule` — legacy, adapted, not the pattern to reach for

Still present and functional (`extension_manager.py`'s `ModuleExtensionAdapter` wraps an
`IModule` to satisfy `IExtension`'s interface internally), for backward compatibility with
code written before `IExtension` existed. Declares `register(app)`, `boot(app)`,
`shutdown(app)` — no context Protocol, no `dependencies`/`priority` metadata support beyond
what the adapter reads via `getattr`. **Do not use this for new code** — see
`docs/module_registration.md` for why the deleted old sample's choice of `IModule` made it a
worse reference, not a different-but-valid one.

---

## `DiagnosticsExtension`

Attaches the wiring inspection to the readiness milestone: `app.use(DiagnosticsExtension())`,
optionally with `fail_fast=True` to abort a boot on a wiring error. It reaches the lifecycle
through `context.lifecycle.when_ready()`, never the other way round — the kernel knows nothing
about diagnostics. See [`diagnostics.md`](diagnostics.md).
