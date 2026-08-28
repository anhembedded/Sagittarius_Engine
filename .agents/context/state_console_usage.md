# Using the runtime state console in your own application

A task-oriented guide. For *what each section means*, see
[`state_console.md`](state_console.md) — this file is about getting a console attached to an
application that is not this repository's, and seeing something real on it.

Every command and every screenshot referenced below was run against a real, booted
application while writing this.

---

## 1. Attach the extension

```python
# myapp/main.py
from sagittarius_engine.extensions.state_console import StateConsoleExtension

def build_app(*, console_port: int | None = None, extra_extensions=None):
    extensions = list(extra_extensions or [])
    if console_port is not None:
        extensions.append(StateConsoleExtension(port=console_port))
    app = App(container, event_bus)
    for ext in extensions:
        app.use(ext)
    app.boot()
    return app
```

Made optional behind a parameter, not always-on — the same shape
`examples/student_management/console.py` uses. `port=0` binds an ephemeral port, resolved into
`console_extension._server.port` once `app.boot()` returns (boot only returns once readiness is
reached, and the server starts there).

## 2. Read it as text

```bash
sagittarius-trace snapshot ws://127.0.0.1:8781
```

```console
$ sagittarius-trace snapshot ws://127.0.0.1:8781
snapshot @ 323.875556s
lifecycle: state=ready extensions=4/4 hosted=0/0 scheduler_jobs=0 (without_next_run=0)
events: 17
container: 12 registration(s), open_scopes=0
thread pools:
bounded: ring=0/0 (dropped=0), tasks=0/50, subscriptions=0, gc_counts=[135, 11, 0]
config: 3 entries
detached
```

**A section that never appears is not broken — it is absent because nothing filled it.**
`thread pools:` prints with no rows when nothing is running through `ITaskManager`, and `tasks`
is omitted entirely when there are none retained. Read this output for what changes between two
runs, not for a fixed shape it must always have.

## 3. Open the actual dashboard

```bash
scripts/run-console.ps1 -Attach ws://127.0.0.1:8781
```

Five screens behind a sidebar — Overview, Events & wiring, Container, Tasks & threads, Signals.
The window opens on Overview; the connection banner reads *"Attached — reading"* once the first
snapshot arrives, and *"Not attached"* (with the last snapshot's age) the moment the socket
drops, never the other way round silently.

### `sagittarius-console` not found?

`tools/state_console/main.py` imports `PySide6` only inside `main()`, and the `[dashboard]`
extra (`PySide6>=6.5`) is optional — a wheel built without it still installs and every other
command still resolves. Install it:

```bash
pip install -e ".[dashboard]"
```

## 4. Wire the Signals panel into your own app

Nothing appears on the Signals screen until something is watched — an unwatched console shows
empty tables, correctly, rather than inventing data.

```python
from sagittarius_engine.infrastructure.event_bus.resilient_event_bus import ResilientEventBus

resilient_bus = ResilientEventBus(app.context.event_bus, max_retries=3)
console.watch_dlq(resilient_bus)

# use resilient_bus.on(...) / resilient_bus.emit(...) instead of the plain bus
# from here on, for whichever events should get retry + dead-letter protection
```

```python
flow = EnrolmentFlow()
console.watch_state_machine("EnrolmentFlow", flow)   # before driving it
flow.transition_to(EnrolmentState.SUBMITTED)
```

**Order matters for the state machine, not for the DLQ.** `watch_dlq()` reads `get_dlq()`
fresh on every collection, so it does not matter whether you call it before or after the bus
has already parked something. `watch_state_machine()` installs by wrapping the machine's own
bound methods — a transition driven before the call is invisible to the watcher, the same way
any listener registered too late misses what already happened.

## 5. See it seeded for real

```bash
python examples/student_management/console.py --port 8781 --demo-faults &
sagittarius-trace snapshot ws://127.0.0.1:8781
```

```console
dead letters: 1
  demo.student_deleted: KeyError: 'demo: enrolment record missing' (handler=DemoFaultsExtension._seed_dead_letter.<locals>._always_raises, retries=1)
state machines: 1
  EnrolmentFlow: state=ENROLLED rejected=1
    DRAFT -> SUBMITTED
    SUBMITTED -> APPROVED
    APPROVED -> ENROLLED
    ENROLLED -> SUBMITTED [REJECTED]
```

Full seed table (every fault the sample app plants, and where each shows up):
[`examples/student_management/docs/runtime_state_console_demo.md`](../../examples/student_management/docs/runtime_state_console_demo.md).

## 6. Put a token on it before it leaves loopback

```python
StateConsoleExtension(port=8781, token="dev-only")
```

```bash
sagittarius-trace snapshot "ws://127.0.0.1:8781?token=dev-only"
```

Binding `host="0.0.0.0"` (or any non-loopback address) **without** a token raises
`TraceServerConfigError` at construction — before the process finishes booting, not as a log
line during a connection nobody reads.

## 7. When it will not run

| Symptom | Cause |
| :--- | :--- |
| Client refuses at connect, naming two `v` numbers | `PROTOCOL_VERSION` mismatch between the engine version the client and the server were built against — upgrade whichever is older |
| Connection closes with code `4401` | Wrong or missing `?token=` against a `token=`-configured server |
| `TraceServerConfigError` at boot | Non-loopback `host` with no `token` set |
| The Signals screen shows empty tables against a real fault | Nothing called `watch_dlq()`/`watch_state_machine()` — the console never discovers either on its own (§4) |
| `sagittarius-console` exits on `ModuleNotFoundError: PySide6` | The `[dashboard]` extra was not installed (§3) — the text path (`sagittarius-trace snapshot`) still works without it |

## 8. What it will not tell you

- **Anything about the past.** A snapshot is one instant; "what happened five minutes ago" is
  `sagittarius-trace`'s question, not this one's ([`tracing.md`](tracing.md)).
- **R1** (an emit nobody heard) or `ExclusiveAction.held_slot()` — seeded by the demo app and
  logged by `RuntimeMonitor`, but no collector reads either onto the wire yet.
- **Whether a write action would succeed.** The console is read-only; reprocessing a dead
  letter is visible and disabled, never wired.
