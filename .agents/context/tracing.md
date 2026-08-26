# Tracing — the trace recorder, `ctx.trace`, and `sagittarius-trace`

`EPIC-005`. Records **what happened and when**, on a monotonic clock, into a bounded ring
buffer — then hands it to tools that already render timelines rather than building another one.

---

> **Not the same tool as `sagittarius-doctor`.** That one
> ([`diagnostics.md`](diagnostics.md)) answers *"is this wired correctly?"* — a structural
> question, answered once at boot. This one answers *"what ran, in what order, and for how
> long?"* Both are worth having; reaching for the wrong one wastes a debugging session.

## 1. Turning it on

```python
from sagittarius_engine.extensions.audit.recorder import TraceRecorder

app = App(container, event_bus)
recorder = app.context.enable_tracing(TraceRecorder())
app.boot()
```

**Before `boot()`, not after.** Extension spans are the answer to "why does startup take four
seconds", and they only exist if the recorder does before the extensions start.

Off by default. When it is off, `context.recorder` is `None` and every instrumentation site in
the engine is a `is not None` branch — see §5.

## 2. Instrumenting your own application

```python
ctx.trace.mark("order-filled", price=101.5)            # instant
with ctx.trace.span("strategy-eval", symbol="BTC"):    # span
    ...
```

`ctx.trace` (`kernel/tracing.py`, class `TraceApi`) is **always present**, whether tracing is on
or off, so application code never writes its own `if` around a marker. Application records go in
the `USER` lane; applications do not add lanes.

The framework knows about **zero** application events, deliberately — `D8` in `EPIC-005` §2 was
the engine hard-coding `student.added` and three other demo-app event names inside its own
observability service.

## 3. Attaching from outside the process

```bash
sagittarius-trace attach ws://127.0.0.1:9999 --save session.sagtrace
```

Prints each record as a line of text as it arrives, and on detach (Ctrl+C, or the server
closing) writes everything it saw to a `.sagtrace`. There is deliberately **no timeline
widget** — `EPIC-005` §5 is the standing decision that Perfetto renders a timeline better than
we would, and live streaming is the one thing Perfetto cannot do.

The engine side is `TraceServer` (`extensions/audit/infra/trace_server.py`):

```python
from sagittarius_engine.extensions.audit.infra.trace_server import TraceServer

server = TraceServer(recorder, host="127.0.0.1", port=9999)
server.start()          # returns immediately; `server.ready_event` says when it is listening
```

| | |
| :--- | :--- |
| `host` / `port` | `port=0` binds an ephemeral port, resolved into `.port` once listening |
| `token` | when set, a client must pass `?token=...` or the connection is closed with code `4401` before anything is sent |

**Binding off-loopback without a token raises `TraceServerConfigError` at construction**, not at
connect and not as a logged warning. An unauthenticated trace server reachable off the machine
hands out everything the application records to anyone who connects.

### Attach-late works, and it is the point

Start the app, run the workload, *then* attach — the retained buffer replays what already
happened before streaming live. This is the property `py-spy` and `viztracer` cannot offer:
attach to those after the fact and you see "now", not "then".

Mechanically, `add_tap()` is registered **before** `snapshot()` is read for the backlog. A row
captured in the gap is delivered twice, never dropped. The reverse order can drop one, and for a
diagnostic stream a duplicate is a shrug while a silent gap is the defect this engine exists to
stop shipping.

### A version mismatch fails at connect

`Envelope.from_dict()` calls `check_protocol()` before it reads anything else about a message,
and the first message on any connection is `hello`. A client built against a different
`PROTOCOL_VERSION` therefore raises `ProtocolMismatch` and exits `2` with a message naming both
versions — it never sits there rendering nothing, which is exactly how `D1` looked from the
operator's chair.

## 4. Getting the trace into a real viewer

| Consumer | Module | Cost |
| :--- | :--- | :--- |
| **`.sagtrace`** — save and reopen offline | `extensions/audit/sagtrace.py` | plain JSON, readable with `jq` |
| **Perfetto** (`ui.perfetto.dev`) | `extensions/audit/exporters/perfetto.py` | stdlib only |
| **OpenTelemetry** — Jaeger, Tempo, Datadog | `extensions/audit/exporters/otel.py` | behind the `[otel]` extra |

The `[otel]` extra is **genuinely optional**: uninstall it and the recorder, `.sagtrace` and the
Perfetto exporter all keep working, and calling into the OTel exporter raises `OTelNotInstalled`
naming the fix. The engine's stdlib-only core rule is not negotiable for a diagnostic feature.

## 5. Overhead, and why the call sites look the way they do

| | ns | |
| :--- | ---: | :--- |
| no instrumentation at all (floor) | 21.5 | |
| disabled — `is not None` guard | 24.5 | **what the engine does** |
| disabled — call on a no-op object | 48.8 | rejected |
| enabled — guard + `perf_counter_ns()` + `deque.append` | 157 | against a 2000 ns budget |

**Guard at the call site; let the recorder be `None` when off.** A branch is a load and a
compare; a call on a null object is a whole frame. `EPIC-005` §4.2 originally specified the
opposite and was corrected by measurement before any code was written against it — and
`EPIC-006F` independently measured the same result for its bus observer hook. Treat "a no-op
object is free" as false here by default.

**Nothing is formatted at capture.** No `strftime`, no f-strings, no `str()` of a payload. A
tuple of primitives goes into the ring buffer; `TraceRecord.from_row()` builds the typed object
later, off the hot path, on the consumer's thread.

**Records are counted when evicted.** A full buffer drops oldest-first and increments
`recorder.dropped`, reported to every connecting client in `hello.dropped_before_connect`. A
consumer that does not show it is presenting a trace with holes in it as complete.

## 6. Where the pieces are

| Path | |
| :--- | :--- |
| `interfaces/i_trace_recorder.py` | `ITraceRecorder`, `Lane` — the vocabulary `kernel/` needs |
| `extensions/audit/recorder.py` | `TraceRecorder` — the ring buffer, and `add_tap()` for live subscribers |
| `extensions/audit/contracts.py` | `TraceRecord`, `Hello`, `Envelope`, `PROTOCOL_VERSION` — one schema, imported by both sides |
| `extensions/audit/infra/trace_server.py` | `TraceServer` — the live WebSocket transport |
| `extensions/audit/cli.py` | `sagittarius-trace` |
| `extensions/audit/sagtrace.py` | `save_sagtrace()` / `load_sagtrace()` |
| `extensions/audit/exporters/perfetto.py` | Chrome Trace Event Format |
| `extensions/audit/exporters/otel.py` | OpenTelemetry spans |
| `kernel/tracing.py` | `TraceApi` — `ctx.trace` |
| `kernel/context.py` | `enable_tracing()` / `disable_tracing()` |

`Lane` is defined **once**, in `interfaces/i_trace_recorder.py`, and re-exported by
`contracts.py`. A second definition would be `D3`/`D4` a third time — that module's whole
argument is that two hand-maintained copies of a schema drift until the consumer is reading
fields the producer stopped sending.

## 7. What is still the old implementation

`extensions/audit/audit_extension.py`, `extensions/audit/audit_service.py`,
`extensions/audit/ports.py`, `extensions/audit/infra/websocket_broadcaster.py` and
`tools/audit_dashboard/` are the **superseded** snapshot
dashboard, scheduled for deletion by `EPIC-005` §3 and kept only until that teardown is run.
Nothing above depends on them. `TASK-002` shipped that dashboard as complete while both of its
clients were 100% non-functional; do not build on it.
