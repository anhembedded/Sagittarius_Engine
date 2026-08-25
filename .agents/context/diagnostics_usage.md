# Using `sagittarius-doctor` in your own application

A task-oriented guide. For *what each check means*, see
[`diagnostics.md`](diagnostics.md) — this file is about getting the tool
running against an application that is not this repository's.

Every command and every output below was executed against a real application
while writing this. Three of the guards described in §7 exist **because** they
were written: following these steps surfaced three ways the command returned a
green result for something it had not inspected.

---

## 1. Write a factory

The one thing you must provide. A zero-argument callable that returns a
**booted** `App`:

```python
# myapp/doctor_target.py
from myapp.main import build_app


def build():
    """Zero-argument entry point for `sagittarius-doctor`.

    Separate from `build_app()` because the doctor calls it with no arguments,
    and because the database should be a throwaway — the factory really runs.
    """
    return build_app(db_url="sqlite:///:memory:")
```

Three rules, each enforced with its own error message (§7):

| Rule | If you break it |
| :--- | :--- |
| Takes **no arguments** | `exit 2` — the `TypeError` is printed |
| Returns an **`App`** | `exit 2` — *"returned dict, which has no `.context`"* |
| The app is **booted** | `exit 2` — *"returned an App that has not been booted"* |

The third is the one worth pausing on. Wiring does not exist until boot: before
it there are no subscriptions, no initialised extensions, and an empty
container. An unbooted app therefore passes *every* check — which is why this
is refused rather than reported clean.

> **It really runs your factory.** There is no way to inspect wiring without
> running the composition that creates it. Point it at a throwaway database and
> assume any other side effect happens too.

---

## 2. First run

```console
$ sagittarius-doctor myapp.doctor_target:build
Wiring report: 0 error(s), 0 warning(s), 16 info.
  [A1] INFO: app.booted — declared, but no handler is subscribed
        → intentional? pass it in expected_unheard to stop reporting it
  [A1] INFO: extension.started — declared, but no handler is subscribed
  ... 13 more like it ...
  [A5] INFO: order.placed — subscribed by string, so a misspelling here would
       fail silently rather than at import
        → a BaseEvent subclass makes that class of typo impossible
```

**A wall of `A1` on the first run is expected, not a problem.** The event
registry is process-wide and holds every event the *engine* can emit — most of
which your application has no reason to handle. Exit code is `0`.

Read the first run for what is *missing* from it rather than what is in it: no
`ERROR`, no `WARNING`. Then move to step 3.

---

## 3. Silence what is deliberate

```console
$ sagittarius-doctor myapp.doctor_target:build \
    --expect-unheard app.booted \
    --expect-unheard app.ready
Wiring report: 0 error(s), 0 warning(s), 14 info.
```

Repeatable, one event per flag. Declaring these is the application's job —
the framework never decides on your behalf that an event is legitimately
unheard.

Use it for events you have *decided* not to handle, not to make the report
shorter. The engine's own lifecycle events are the usual honest case.

---

## 4. Turn on the handler checks

Handlers are in no registry — nothing enumerates them — so without a package to
search, checks **B1–B3 do not run at all**:

```console
$ sagittarius-doctor myapp.doctor_target:build --handler-package myapp
Wiring report: 0 error(s), 0 warning(s), 17 info.
  [B3] INFO: PlaceOrderHandler — dispatchable, 2 dependencies
        → repo: IOrderRepository, event_bus: IEventBus
```

One extra finding, and the B checks are now live. This is the flag most worth
adding: `B1` (an unbound abstract dependency — dispatching raises) and `B2`
(an unbound plain dependency — nothing raises, see `diagnostics.md` §4) are the
two findings that a passing test suite is least likely to have caught.

Discovery searches modules your application **has already imported** and imports
nothing itself. A handler in a module nothing imports is invisible here — and
is also a handler nothing can dispatch.

---

## 5. Put it in CI

```yaml
- name: Wiring inspection
  run: |
    pip install -e .
    sagittarius-doctor myapp.doctor_target:build \
      --handler-package myapp \
      --strict
```

`--strict` makes warnings fail the build as well as errors. Whether you want it
is a real decision:

| | Without `--strict` | With `--strict` |
| :--- | :--- | :--- |
| Errors | fail | fail |
| Warnings | reported, build passes | fail |
| Info | reported, build passes | reported, build passes |

Start without it, fix what it finds, then turn it on — otherwise adoption is
blocked on clearing every warning before the tool has proved useful once. This
repository runs `--strict` against its own reference application, because that
application is held up as how to build on the engine.

Install the package first (`pip install -e .`). CI should run the **installed
command**, the way a consumer does, not an import of the library.

---

## 6. Or run it inside the application

```python
from sagittarius_engine.extensions.diagnostics import DiagnosticsExtension

app.use(DiagnosticsExtension(
    fail_fast=True,
    expected_unheard=("app.booted", "app.ready"),
    handler_packages=("myapp",),
))
app.boot()   # report is logged at readiness; a wiring error aborts here
```

Same checks, same arguments, at the readiness milestone. `fail_fast` defaults
to `False`: an engine that refuses to start over a diagnostic is a worse
default than one that says loudly what is wrong. Warnings never block.

The report from the last run is on `extension.last_report`, so a test can read
the findings directly instead of parsing them back out of a log line.

---

## 6b. Catching what only happens while it runs

Steps 1–6 all inspect **structure** — one pass, at readiness. Two more checks watch
**behaviour**, for the life of the process:

```python
app.use(DiagnosticsExtension(
    watch_runtime=True,
    expected_unheard=("order.archived",),
    handler_packages=("myapp",),
))
```

| Check | | Finds |
| :--- | :--- | :--- |
| **R1** | warning | An event was emitted and **nothing was listening** — with the line it came from |
| **R2** | **error** | A handler **raised**, how many times, and every exception type |

Anomalies are logged at shutdown, and readable at any point:

```python
report = diagnostics_extension.runtime_report()
```

```text
Wiring report: 1 error(s), 1 warning(s), 0 info.
  [R2] ERROR: myapp.orders.on_shipped on 'order.shipped' — raised 2x while
       handling this event (ValueError)
        → first failure: ValueError: downstream service returned 500
  [R1] WARNING: order.cancelled — emitted 2x at runtime with no handler
       subscribed — nothing received it
        → first emitted from myapp/orders/service.py:19
```

**R1 is not A1.** A1 is static — *declared, nobody subscribes* — and is usually fine. R1 fires
only when something really **published into the void**. The engine's own lifecycle events are
excluded by default; `include_engine_events=True` on `RuntimeMonitor` shows them.

**R2 does not change anything about how your application behaves.** A handler that raises is
still isolated, and the other subscribers still get the event. R2 only makes the failure
*countable* instead of one log line among thousands.

**Off by default, because it is the only part that runs continuously.** An application that
leaves it off pays nothing measurable per emit; one that turns it on pays about 98 ns.

Not available through `sagittarius-doctor`: the command is a one-shot inspection that boots,
reports, and exits, and there is no runtime to watch.

---

## 7. When it will not run

Exit `2` always means the same thing: **no report exists, nothing was
inspected**. It is never a statement about your wiring. Each message names what
to change.

| Message | Cause |
| :--- | :--- |
| `expected an application factory as 'package.module:callable'` | No `:` in the argument |
| `cannot import 'myapp.main'` | Not on `sys.path` — run from your project root, or install the package |
| `'myapp.main' has no attribute 'build'` | Typo, or the factory is named something else |
| `importing 'myapp.main' raised TypeError: ...` | Your module's **top-level code** raised. Importing runs it |
| `... raised while building the application` | The factory itself raised — full traceback above the message |
| `returned dict, which has no .context` | The factory returned something that is not an `App` |
| `returned an App that has not been booted` | Missing `app.boot()` in the factory |
| `--handler-package matched no loaded module: 'myapp.hadnlers'` | Typo, or that package is never imported by your app |

The last three were added on 2026-08-25 after writing this guide and following
it. Each of them previously produced a **green or misleading result**: a
non-`App` escaped as a bare traceback under exit `1`, an unbooted app reported
`0 error(s)` and exited `0`, and a mistyped `--handler-package` ran no handler
checks and still exited `0`. A green build for a check that never ran is worse
than no check at all, because it is believed.

---

## 8. Machine-readable output

```console
$ sagittarius-doctor myapp.doctor_target:build --json | jq '.counts'
{ "error": 0, "warning": 0, "info": 17 }
```

The document is `{ok, counts, findings[]}`; each finding carries
`check`, `severity`, `subject`, `message`, `hint`.

Your application's boot output goes to **stderr** so it cannot land in the
middle of the document — pipe `stdout` alone and it always parses. On exit `2`
stdout is empty rather than a partial document.

---

## 9. What it will not tell you

- **Whether a handler is correct** — only that it can be reached and its
  dependencies can be supplied.
- **Anything about runtime behaviour** — nothing is resolved, constructed,
  emitted or started to produce a finding. Every check is a set difference or a
  static signature walk.
- **Handlers in modules your application never imports** — see §4.
- **Whether an unheard event matters.** `A1` is advisory; only you know.

For the check catalogue and the reasoning behind each severity, read
[`diagnostics.md`](diagnostics.md).
