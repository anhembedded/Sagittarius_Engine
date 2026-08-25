# EPIC-006: Wiring & Readiness Diagnostics

- **Status**: 🟡 **In Progress — 1/6 subtasks done** (`EPIC-006A` ✅ 2026-08-25)
- **Created**: 2026-08-25
- **Priority**: P1
- **Category**: Diagnostics / Runtime Correctness
- **Relationship to `EPIC-005`**: complementary, and **ahead of it in priority** — see §1.2

---

## 1. Objective

Answer, at boot and while running:

1. **Is the system wired correctly?** — every event has a listener, every listener is bound to
   an event that exists, every handler can actually be resolved.
2. **Has it stabilised?** — is there a defined moment at which the engine is "up", and has it
   been reached?
3. **Are all events loaded?** — does what the registry declares match what the bus actually
   subscribed?
4. **What handler is bound to what?** — a queryable wiring graph, not a guess.
5. **Is anything abnormal right now?** — surfaced early, not after a user reports it.

### 1.1 The gap, in this repository's own words

`sagittarius_engine/domain/event_registry.py` states it plainly:

> **What this registry is not** — It does not track *subscribers*. Which handlers are registered
> against a live `IEventBus` instance is runtime state tied to one running application, not
> something a class-level, import-time registry can know. **A consuming app's own test suite is
> where "every event has at least one subscriber, or is documented as intentionally unheard"
> belongs**, checked against its actual bus instance (`bus.get_handlers(event_name)`).

The gap was identified correctly and then delegated outward, to every consuming app, forever.
This epic brings it back in — because both halves already exist in the engine and nothing joins
them:

| Half | Where | State |
| :--- | :--- | :--- |
| Every event that **can** be emitted | `EventRegistry.all()` | ✅ public, already generates `EVENT_CATALOG.md` |
| Every handler **actually** subscribed | `IEventBus.get_handlers()` | ✅ public, on the interface |
| **The comparison between them** | — | ❌ **does not exist anywhere** |

The flagship case this unlocks: today `bus.on("student.updatd", handler)` — one missing letter —
**fails silently forever**. The handler never fires, no test catches it, no profiler catches it,
and neither Perfetto nor OpenTelemetry can see it. A registry-vs-bus diff catches it at boot in
milliseconds.

### 1.2 Why this comes before `EPIC-005`

They answer different questions and the cost differs by an order of magnitude.

| | **EPIC-006** — wiring | **EPIC-005** — trace recorder |
| :--- | :--- | :--- |
| Question | "why is it **wrong**?" | "why is it **slow**?" |
| Cost | a few hundred lines | thousands + protocol + ring buffer + exporters |
| Runtime overhead | ~zero — introspection at one moment | needs a µs budget |
| Available off the shelf? | **No.** Nothing outside the framework knows your DI wiring | Largely — `py-spy`, `viztracer`, Perfetto, OTel |
| Reuses what exists | `EventRegistry`, `get_handlers()`, `DependencyValidatorExtension`, `HealthExtension` | almost entirely new |

`EPIC-005`'s central argument — that the engine's unique contribution is knowing the *meaning*
of its own internals — applies here more strongly than it does there. A generic tool can sample
stacks; none can tell you a command's dependency is unbindable.

### 1.3 There is already a precedent in this codebase

`extensions/dependency_validator.py` does exactly this shape of thing — a boot-time pre-flight
that fails fast with an actionable message:

```
CRITICAL FAULT: Missing required dependencies: ...
Please fix by running:
    pip install ...
```

…but only for **pip packages**. EPIC-006 is the same mechanism, same lifecycle position, same
fail-fast philosophy, applied to the engine's **own internal wiring**. This is not a new idea
being introduced; it is an existing, deliberate pattern being extended to the thing that
actually breaks.

---

## 2. Feasibility survey

Verified against the tree at `2b72557`. This decides which checks are buildable and which need
groundwork first.

| Capability needed | Available? | Notes |
| :--- | :--- | :--- |
| Declared event catalogue | ✅ | `EventRegistry.all()` → `EventEntry(event_name, event_class, module)` |
| Live subscriptions, one name | ✅ | `IEventBus.get_handlers(name)` — answers only about a name the caller already holds |
| **Enumerate subscriptions** | ✅ **added by `EPIC-006A`** | `IEventBus.subscriptions()`. Was the blocker for check A2: a typo'd name cannot be found by asking about the correct one |
| Extension declared dependencies | ✅ | `self.dependencies` (e.g. `AuditExtension.dependencies = ["HealthExtension"]`) |
| Started hosted services | ✅ | `hosted_services.started_services` |
| Registered scheduler jobs | ✅ | `scheduler.jobs` |
| **Enumerate DI bindings** | ✅ **added by `EPIC-006A`** | `IContainer.registrations() -> Mapping[type, Registration]`. Was private-only across four stores |
| **Command → handler map** | ❌ **does not exist** | See §2.2 — changes the shape of the dispatch check |
| **Readiness / "stable" state** | ❌ **does not exist** | `grep -riE "ready\|readiness\|stable\|settled"` over `kernel/` and `extensions/health/` returns nothing |

### 2.1 Constraint: no reaching into privates

`EPIC-005` §2 recorded, as a defect, that `AuditService` reads `eb._handlers` and
`config._config` directly — an observability tool that freezes a private is a liability. **This
epic must not repeat that.** Where introspection is needed and no public surface exists, the
work is to *add a narrow, read-only public API*, not to reach in:

- `IContainer.registrations() -> Mapping[type, Registration]` — abstract type, concrete type,
  lifetime (`singleton` / `transient` / `scoped`), and whether it is already instantiated.
- `IEventBus.subscriptions() -> Mapping[str, tuple[Callable, ...]]` — the whole map, alongside
  the existing per-name `get_handlers()`.

Both are small and independently useful. They are the first subtask for that reason.

**✅ Done — `EPIC-006A`, 2026-08-25.** Both landed as **concrete methods with an empty default**
rather than abstract: `code-rule.md` §L forbids the `NotImplementedError` alternative, and making
them abstract would break any implementation outside this repository at instantiation. Two
architecture guards ensure the default never applies to a class shipped here.

The rejected alternative is worth recording, because the codebase proves it would not merely have
been untidy but **wrong**: `ThreadPoolEventBus` has no `_handlers` at all (it delegates to an
inner bus), so a diagnostic reading privates reports a fully-wired application as having zero
subscriptions; and `ResilientEventBus` registers `resilient_wrapper` closures rather than the
caller's handlers, so reading through would name the decorator instead of the subscriber.

### 2.2 The dispatcher has no handler registry — and that changes the check

`Dispatcher.dispatch(handler_class, input_dto)` takes the handler **class itself** and resolves
it straight from the container:

```python
handler = self.context.container.resolve(handler_class)
```

There is no registration step, so there is no "command → N handlers" table to audit, and
"zero handlers" / "ambiguous handlers" are not failure modes this engine can have. Good — that
is a simpler design than CQRS frameworks that maintain a map.

But it relocates the risk rather than removing it: **a handler whose constructor dependency is
not bound fails only when a user triggers that command.** The container raises at
`resolve()` time, in production, on a real request — the exact "late failure" this epic exists
to pull forward.

So the dispatch check becomes a **resolvability pre-flight**: discover every `IDispatchable`
subclass and prove each one can be constructed. That is more valuable than a registry audit
would have been, and it is only possible because the container can be asked to resolve without
executing anything.

### 2.3 The container does not fail on an unbound dependency — it silently builds the interface

Found 2026-08-25 while prototyping check C against the `EPIC-006A` API. Resolving a class whose
constructor annotation is unbound behaves in two completely different ways:

| Unbound dependency | Result |
| :--- | :--- |
| An **ABC** | `DependencyResolutionError: Cannot instantiate abstract ...` — check C catches it |
| A **plain class** | **Resolves successfully**, and injects an instance of the annotation itself |

The second is the dangerous one, and it is silent: the caller receives a bare `IMailer()` where
its real implementation was intended. No exception, no log line, and the application simply
behaves wrongly.

**Consequence for check B1/C1:** "resolve it and see whether it raises" is not sufficient — it
passes on exactly the case worth finding. The check must also ask whether each dependency was
*explicitly bound*, or whether the container fell back to constructing the annotation. That
question is answerable now: compare the injected type against `registrations()`; an annotation
that resolves to itself and appears nowhere in the registry was an implicit fallback, not a
decision anyone made.

Whether that fallback should keep happening at all is a separate question, and a bigger one —
raise it as its own task rather than changing resolution semantics inside this epic.

---

## 3. The checks

### A — Event wiring

| ID | Check | Catches |
| :--- | :--- | :--- |
| A1 | Declared **−** subscribed → events nobody listens to | A feature wired only halfway |
| A2 | Subscribed **−** declared → **a handler bound to an event name that does not exist** | **Typos.** The flagship case (§1.1) |
| A3 | Handler count per event, reported | "I thought that fired twice" |
| A4 | Handlers whose bound callable is a dead/garbage-collected reference | Subscriptions outliving their owner |

A1 needs an escape hatch: some events are legitimately unheard (`TaskProgressUpdated` in an app
that shows no progress). An allowlist, declared by the app — *not* by the framework — keeps the
check honest rather than noisy.

A2 has no escape hatch. A handler bound to an unregistered name is always a bug.

### B — Dispatch wiring

| ID | Check | Catches |
| :--- | :--- | :--- |
| B1 | Every discoverable `IDispatchable` subclass resolves from the container | A command that explodes only when first used |
| B2 | Report each handler's resolved dependency chain | "what does this actually depend on?" |

### C — DI wiring

| ID | Check | Catches |
| :--- | :--- | :--- |
| C1 | Every binding's concrete type is constructible | A binding registered but never satisfiable |
| C2 | Constructor annotations that resolve to nothing bindable | Typo'd or refactored-away interface |
| C3 | Circular dependencies reported as a named cycle | `_resolve()` already carries a `resolving: set[type]` guard — surface it as a diagnostic, not just an exception |

### D — Lifecycle wiring

| ID | Check | Catches |
| :--- | :--- | :--- |
| D1 | Every extension's declared `dependencies` are present, and boot order satisfies them | A silent ordering assumption |
| D2 | Hosted services registered vs. actually started | A service that was declared and never ran |
| D3 | Scheduler jobs registered, with next-run resolved | A job that will never fire |

### E — Readiness

Currently the engine has no concept of being "up". The `health` extension carries a note from
being bitten by exactly this — `health_check_requested.py:9`: *"already missed it, and its
subscription is dead code that never fires"* — the classic symptom of subscribing after the
event has already fired.

Deliverable: an explicit lifecycle state machine and an `app.ready` milestone, reached when
boot has completed **and** every extension has booted **and** every hosted service has started
**and** the scheduler is running. That milestone is what makes "has it stabilised?" answerable,
and it is also the correct place to run checks A–D.

### F — Runtime anomalies *(phase 2)*

Once E exists, "abnormal" becomes definable relative to a settled baseline:

- An event emitted that has zero handlers → warn once, with the emit site.
- A handler that raised — the bus no longer swallows these (fixed in `bde88e9`), so they can be
  counted and surfaced rather than merely logged.
- A task running past an expected duration; a hosted service that died after starting.

---

## 4. Output

Four consumers of one diagnostic result, in increasing order of intrusiveness:

1. **`report()`** — a structured `WiringReport` object. Everything else is a rendering of it.
2. **Fail-fast at boot** — opt-in, mirroring `DependencyValidatorExtension`. Default is to
   report, not to exit; see §7.1.
3. **`sagittarius-doctor`** — a CLI that boots the app, prints the report, exits non-zero on
   findings. Runnable in CI, which is where it earns most of its value.
4. **A generated wiring document**, in the shape `EVENT_CATALOG.md` already established:
   committed, diffable, and guarded by a test so an unintended change to the wiring shows up in
   review.

---

## 5. Subtasks

| ID | Scope | Done when |
| :--- | :--- | :---: |
| **EPIC-006A** | Public read-only introspection: `IContainer.registrations()`, `IEventBus.subscriptions()` (§2.1) | ✅ **Done 2026-08-25** — [`completed/EPIC-006A_introspection_read_api.md`](completed/EPIC-006A_introspection_read_api.md). Both concrete-with-empty-default (not abstract: `code-rule.md` §L), implemented across all five buses and `StdLibContainer`, with architecture guards proving no shipped class inherits the default |
| **EPIC-006B** | Checks A + C + D, `WiringReport`, `report()` | A deliberately mis-wired fixture app produces the exact expected findings — including the A2 typo case |
| **EPIC-006C** | Readiness state machine + `app.ready` (§E), checks run at that milestone | `app.ready` fires exactly once, after all four preconditions; a late subscriber can query state instead of missing the event |
| **EPIC-006D** | Check B — `IDispatchable` discovery and resolvability pre-flight | A handler with an unbindable constructor dependency is reported at boot, not on first dispatch |
| **EPIC-006E** | `sagittarius-doctor` CLI + generated wiring document + docs | Runs in CI against `examples/student_management`; `.agents/context/` updated |
| **EPIC-006F** | Runtime anomaly detection (§F) | *Deferred — specify after C lands and "settled" is well-defined* |

Order: **A → B → C → D → E.** A is groundwork and small; B delivers the flagship value on its
own and is independently shippable.

---

## 6. Acceptance criteria

1. **The typo is caught.** A test subscribes a handler to a deliberately misspelled event name
   and asserts the diagnostic reports it, naming both the bad name and the nearest registered
   one.
2. **No private attribute access.** No diagnostic code touches `_handlers`, `_bindings`,
   `_config` or any other private. Enforced by the existing architecture test job if it can be
   expressed there.
3. **An unheard event is reported, and can be allowlisted by the app** — never by the framework.
4. **An unbindable handler dependency is reported at boot**, not at first dispatch.
5. **`app.ready` fires exactly once**, after boot + all extensions + all hosted services +
   scheduler. A subscriber registering after it has fired can still learn the state.
6. **Zero cost when disabled**, and bounded when enabled: the full check runs in well under a
   second on `examples/student_management`, and runs at boot only — never per event.
7. **`sagittarius-doctor` runs in CI** against the sample app and fails the build on findings.
8. **The generated wiring document is guarded by a test**, in the same manner as
   `EVENT_CATALOG.md`.
9. **Works on the declared floor** — Python 3.12, per `requires-python` as of `58946b3`.

---

## 7. Open decisions

1. **Fail-fast by default, or report-only?** `DependencyValidatorExtension` calls `sys.exit(1)`.
   That is right for a missing package; it may be too aggressive for an unheard event.
   *Recommendation: A2, B1 and C are fatal by default (they are always bugs); A1 and D are
   warnings.*
2. **Where does it live?** A new `extensions/diagnostics/`, or folded into `HealthExtension`?
   *Recommendation: its own extension.* Health answers "is it working now"; this answers "was it
   assembled correctly" — different lifecycle, different consumers.
3. **How are `IDispatchable` subclasses discovered** for B1 — a registry populated by
   `__init_subclass__` (the pattern `BaseEvent`/`EventRegistry` already uses successfully), or
   package walking? *Recommendation: `__init_subclass__`, for consistency with the existing
   mechanism and to avoid importing an app's whole tree.*
4. **Allowlist format** for intentionally-unheard events — config key, decorator, or a file?
5. **Does `sagittarius-doctor` justify a second console script**, given `sagittarius-audit` is
   already declared and currently broken (`EPIC-005` §2, D6)? Both entry points must be covered
   by the wheel guard (§8).

---

## 8. Relationship to the wheel guard

`scripts/verify_wheel_importable.py` (added `49c941b`) builds the wheel, installs it into a
throwaway venv, `compileall`s it and imports every module. That is stronger than what
`EPIC-005` §7 asked for, and it closes the class of defect that shipped `v2.1.0` and `v2.2.0`
broken.

**One gap remains, and it is precisely the one `TASK-002` fell through:** the guard sweeps the
`sagittarius_engine` package only, and it *imports modules* rather than **resolving and invoking
the declared console scripts**. Installing the built wheel into a clean venv and running
`sagittarius-audit` fails three ways over: `PySide6` is imported at module level but declared
nowhere (the wheel is zero-dependency); the inner imports are bare and need a specific cwd; and
the entry point `tools.audit_dashboard:main` binds a *module* rather than a function. None of
the three is reachable by an import sweep over a package the script does not live in.

**✅ Closed by `TASK-039` (2026-08-25), ahead of both epics as recommended.** The guard now has
a third step that reads `console_scripts` from the installed distribution's metadata, resolves
each `module:attr` the way the generated launcher does, and asserts the result is callable —
resolving but never invoking, since running a console script would start the application. It
caught `sagittarius-audit` on the first run; that entry point was removed rather than repaired,
since `EPIC-005` §3 schedules its target for deletion.

**Milestone E's `sagittarius-doctor` is therefore already gated** before it can reach a
consumer, which is exactly why this was worth doing first.
