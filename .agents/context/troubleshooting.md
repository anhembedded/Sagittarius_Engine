# Troubleshooting Guide

Solutions to common issues.

## 1. Async Context Errors (`RuntimeError: Event loop is closed`)
- **Cause**: Trying to spawn a task after the `AsyncRuntime` has been stopped.
- **Fix**: Ensure background tasks check the `CancellationToken` (e.g. `token.is_cancelled`) and exit gracefully before the app fully shuts down.

## 2. Mypy Type Errors (`Liskov substitution principle violation`)
- **Cause**: A child class overrides a method with a different signature than the interface.
- **Fix**: For an `IExtension`, ensure `register(self, context: TContext)` matches your
  declared context Protocol exactly (see `rules/architecture.md`'s narrow-context-Protocol
  section) — a common cause is widening or narrowing `TContext` in the override. For the
  legacy `IModule` path, ensure `register(self, app: App)` matches `IModule.register(self,
  app: App)` exactly.

## 5. `start()`/`stop()` override silently skips your `boot()`/`shutdown()`
- **Cause**: `IExtension`'s orchestrator methods (`initialize`/`start`/`stop`/`dispose`)
  delegate to the author methods (`register`/`boot`/`shutdown`) by default. Overriding
  `start()` without calling `super().start(context)` means `ExtensionManager` never reaches
  your `boot()` — no error, the extension just doesn't do what it's supposed to.
- **Fix**: Override the author layer (`register`/`boot`/`shutdown`) unless you specifically
  need to wrap orchestration — see `modules.md` and `rules/architecture.md`.

## 3. `sagittarius-trace attach` shows nothing
- **Cause**: tracing is off, so there is nothing to stream. It is off by default —
  `context.recorder` is `None` until something enables it.
- **Fix**: `app.context.enable_tracing(TraceRecorder())` **before** `app.boot()`, and start a
  `TraceServer` against that same recorder. See `tracing.md` §1 and §3.
- **Note**: a version mismatch does *not* look like this — it exits non-zero at connect with a
  message naming both versions. Silence means no records, not a broken connection.

## 4. Circular Imports
- **Cause**: Domain models importing infrastructure details.
- **Fix**: Use `from typing import TYPE_CHECKING` and `if TYPE_CHECKING:` to resolve typing circular dependencies. Enforce Dependency Inversion.
