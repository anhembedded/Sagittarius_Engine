# Wiring Diagnostics — `sagittarius-doctor` and `DiagnosticsExtension`

`EPIC-006`. Compares what an application **declared** against what it actually **wired**, and
reports the difference — at boot, deterministically, rather than on a user's first request.

---

> **Adopting it in your own application?** Start with
> [`diagnostics_usage.md`](diagnostics_usage.md) — writing the factory, the first
> run, CI, and every way it refuses to run. This file is the reference: what each
> check means and why.

## 1. What it is for

A DI container and an event bus are a deliberate trade: flexibility bought by giving up static
checking. mypy checks types and is blind to wiring — `"student.updatd"` is a perfectly valid
`str`, so nothing complains, and the handler simply never runs. This is the checking that trade
gave away, handed back.

The three questions it answers, none of which anything outside the framework can:

- Is every subscription bound to an event that exists?
- Can every registration and every dispatchable handler actually be constructed?
- Did everything registered actually come up?

---

## 2. Running it

### From the shell

```bash
sagittarius-doctor myapp.main:build_app \
    --handler-package myapp.application \
    --expect-unheard app.booted \
    --strict
```

| | |
| :--- | :--- |
| `factory` | `package.module:callable` returning a booted `App`. The working directory is put on `sys.path`, so a factory in the project you are standing in resolves. |
| `--handler-package` | Search this package for dispatchable handlers (checks B1–B3). Repeatable. **Without it, handlers are not checked** — nothing registers them, so there is nothing to enumerate. |
| `--expect-unheard` | An event this application deliberately does not listen to; silences A1 for it. Repeatable. |
| `--json` | Machine-readable. Boot output is redirected to stderr so the document is never corrupted by an application that prints while starting. |
| `--strict` | Exit non-zero on warnings as well as errors. |

Exit codes: `0` clean, `1` findings, `2` the doctor could not run. The last is separate on
purpose — "your wiring is wrong" and "the tool never started" need different responses from
whoever reads the build.

`2` covers every way no report gets produced, not just a mistyped argument: a module that
raises while being *imported* (importing runs its top-level code), and a factory that dies
before returning an `App`, both land here. Corrected 2026-08-25 — this said "a mistyped
argument", and the code matched that reading: both of those cases escaped as a bare traceback
under exit `1`, which claims an inspection happened and found errors. In the failing case the
traceback is printed in full, because it names the line that actually broke.

**It boots the application.** Wiring does not exist until something wires it, so there is no way
to inspect it without running the application's own composition. Point it at a factory that uses
a throwaway database, the way `examples/student_management/doctor_target.py` does.

### Inside the engine

```python
app.use(DiagnosticsExtension(fail_fast=True, handler_packages=["myapp.application"]))
app.boot()          # inspection runs at readiness; an error aborts the boot
```

`fail_fast` is off by default: an engine that refuses to start over a diagnostic is a worse
default than one that says loudly what is wrong. Warnings never block.

The inspection runs at the **readiness milestone** (`EPIC-006C`) — the one instant where the
answer is both complete and still ahead of any real work. Earlier reports subscriptions that do
not exist yet; later means the application has been serving while mis-wired.

---

## 3. The checks

| Check | Severity | Finds |
| :--- | :--- | :--- |
| **A2** | **error** | A handler subscribed to a name no event is registered under — with the intended spelling named |
| A2 | warning | Subscribed but undeclared, and unlike anything declared: cannot be typo-checked at all |
| A1 | info | Declared, nobody listening |
| A3 | info | More than one handler on a name |
| A5 | info | Subscribed **by string**, i.e. exposed to the A2 class of defect |
| **B1** | **error** | Handler needs an unbound **abstract** dependency — dispatching raises |
| B2 | warning | Handler needs an unbound **plain** dependency — see §4 |
| B3 | info | What a handler depends on |
| **C1** | **error** | Registration needs an unbound abstract dependency |
| C2 | warning | Registration needs an unbound plain dependency — §4 again |
| **C3** | **error** | Circular constructor dependency, named in full |
| **D1** | **error** | Extension registered but never initialised |
| D2 | warning | Hosted service registered but never started |
| D3 | warning | Scheduled job with no next run — it will never fire |

**A1 is advisory on purpose.** `EventRegistry` is process-wide and holds every event the engine
can emit, most of which any given application has no reason to handle. Warning on those every
boot would train the reader to skip the report, which costs more than the check finds. Silence
the ones you mean with `expected_unheard`.

**A2 separates a typo from an undeclared event** by edit distance. `order.cancelld` matches
`order.cancelled` and is an error; `legacy.tick` matches nothing and is a warning suggesting
registration. Without that split, an application that has not declared its events reads as a
pile of defects and the check gets switched off.

**A5 reports exposure, not a fault.** A class-based subscription cannot be misspelled — Python
raises `NameError` before the bus is reached — so A2's whole value sits on the string API. A5
lists where you are using it, with a fix that removes the class of defect entirely.

---

## 4. The silent case worth knowing about

An unbound **abstract** dependency raises on resolve, and C1/B1 report it as an error.

An unbound **plain class** does not raise. The container constructs the annotation itself and
injects that, so the application receives an empty stand-in where its real implementation was
intended, and simply behaves wrongly — no exception, no log line. That is C2/B2, and it is why
"resolve it and see whether it raises" was not a sufficient check.

---

## 5. What it will not do

**Nothing is resolved, constructed, emitted or started to produce a finding.** Every check is a
set difference or a static signature walk. A diagnostic that builds objects in order to describe
them would run half the application as a side effect of a question, and could not honestly run
at boot — which is the only place it is worth running. A test counts constructions and asserts
zero.

`discover_handlers()` walks `sys.modules` and **imports nothing**, for the same reason. The
honest cost: a handler in a module the application never imported is invisible — and is also a
handler nothing can dispatch.

---

## 6. Where the pieces are

| Path | |
| :--- | :--- |
| `extensions/diagnostics/inspector.py` | The checks |
| `extensions/diagnostics/report.py` | `Finding`, `WiringReport` |
| `extensions/diagnostics/handlers.py` | Structural handler discovery |
| `extensions/diagnostics/extension.py` | `DiagnosticsExtension` — attaches to readiness |
| `extensions/diagnostics/cli.py` | `sagittarius-doctor` |
| `interfaces/i_event_bus.py` | `subscriptions()` — the enumeration the checks needed |
| `interfaces/i_container.py` | `registrations()`, `Registration` |
| `kernel/lifecycle.py` | `EngineState`, `app.ready`, `when_ready()` |

CI runs the command against `examples/student_management` with `--strict`, through
`examples/student_management/doctor_target.py`. `tests/extensions/diagnostics/` covers the same
ground, so a break is a red test before it is a red build.
