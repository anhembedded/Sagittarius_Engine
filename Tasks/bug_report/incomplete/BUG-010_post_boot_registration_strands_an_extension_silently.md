# BUG-010 — Registering an extension after boot strands it silently, and the engine still reports `ready`

**Reported date:** 2026-08-25
**Severity:** Medium (a feature that never starts, with no exception and no log — and a lifecycle state that says everything is fine)
**Status:** 🔴 Open
**Found by:** `EPIC-006C`, while verifying whether the readiness gate it was about to add guarded a condition that can actually occur

---

## What is wrong

`ExtensionManager.register()` defers an extension whose declared dependencies are not yet
registered, and retries deferred extensions on each later `register()`. That is the right
behaviour for registration order — during boot it lets extensions be registered in any order.

**After boot, nothing ever retries again, and nothing reports the extension never started.**

The engine keeps reporting `ready`.

## Reproduction

Against `examples/student_management`, on `main`:

```python
app = build_app(db_url="sqlite:///:memory:")
print(app.context.lifecycle.state.value)      # ready

class Stranded(IExtension):
    def __init__(self):
        self.dependencies = ["NeverRegistered"]
    def register(self, ctx): ...
    def boot(self, ctx): ...
    def shutdown(self, ctx): ...

app.context.extension_manager.register(Stranded())   # no exception
```

Observed:

```
register after boot : did NOT raise
registered but never initialised : ['Stranded']
lifecycle state     : ready
```

The extension is in `registered_extensions`, absent from `initialized_extensions`, its
`register()`/`boot()` were never called — and the engine's own state says it is ready.

## Why it is not caught during boot

It cannot happen during boot, which is what makes the post-boot case easy to miss.
`initialize_and_start()` raises for **both** ways an extension can fail to initialise —
verified by reproducing each:

| Condition | During boot | After boot |
| :--- | :--- | :--- |
| Dependency never registered | `ExtensionDependencyError` raised | **silent** |
| Dependency cycle | `ExtensionCircularDependencyError` raised | **silent** |

So the boot path is strict and the post-boot path is silent, with no marker on
`register()` saying the two differ.

## Why it matters

Registering an extension into a running engine is the plugin-host use case this framework
exists to serve — `readme.md` names "plugin systems" among its targets. Silently accepting a
registration that will never take effect is the worst available outcome: the caller has no
exception to catch, no log line to read, and a lifecycle state actively telling them the
engine is healthy.

## Options

1. **Raise from `register()` when the engine is already booted and dependencies are unmet.**
   Matches the boot path exactly, and the caller finds out at the call site. Risk: an
   application that registers extensions out of order after boot, relying on a later
   registration to complete the set, would start failing.
2. **Return a result, or log a warning, naming the missing dependency.** Non-breaking, but a
   log line is exactly the kind of signal this repository has repeatedly found nobody reads.
3. **Leave `register()` alone and rely on diagnostics.** `EPIC-006B`'s check D1 already reports
   stranded extensions, at any point in the engine's life rather than only at boot. This is the
   status quo plus a tool that must be run deliberately.

*No recommendation is made here.* Option 1 changes public behaviour and deserves the
maintainer's call rather than a passing decision inside another epic's subtask.

## Related

- `EPIC-006C` — found it; its bootstrap readiness gate was removed once this measurement showed
  the boot path cannot strand anything, so the gate was guarding an impossible state
- `EPIC-006B` check D1 — reports the condition today
- `sagittarius_engine/kernel/extension_manager.py` — `register()`, `_try_initialize_available()`,
  `initialize_and_start()`
