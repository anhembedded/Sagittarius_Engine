# Glossary

* **App / Kernel**: The central entrypoint and orchestrator of the Sagittarius Engine.
* **`IExtension`**: The real, current plugin interface — every shipped extension
  (`LoggerExtension`, `DatabaseExtension`, `HealthExtension`, `DiagnosticsExtension`,
  `ThreadManagerExtension`, `pyside_mvc`) and this repo's own sample app
  (`StudentManagementExtension`, `PySideMvcExtension`) implement it. See `modules.md`.
* **`IModule`**: Legacy — the engine's own code calls it *"a legacy `IModule`"*
  (`kernel/extension_manager.py:22`). Adapted internally to satisfy `IExtension`. Not the
  interface to reach for in new code; see `modules.md`.
* **Extension** (informal term): either an `IExtension` or an adapted `IModule` — the engine
  doesn't distinguish "system-level" vs. "application-level" plugins structurally; both use
  the same registration mechanism (`app.use(...)`).
* **EventBus**: The messaging infrastructure used to decouple system events (e.g., `TaskStarted`) and domain events (e.g., `StudentEnrolled` — see `examples/student_management/domain/events.py`; corrected 2026-08-23, the previous version named a nonexistent `StudentAddedEvent`).
* **TaskManager**: The background task runner for asynchronous or threaded jobs.
* **HostedService / BackgroundService**: A long-running daemon process that starts with the `App` and shuts down gracefully with it (e.g. queue listeners, CLI menus).
* **DI Container**: The Dependency Injection container mapping Abstractions (Interfaces) to Concretions.
