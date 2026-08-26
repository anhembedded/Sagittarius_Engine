# Using the trace recorder — a walkthrough

`tracing.md` is the reference: what each piece is, and why it is shaped that way. This is the
hands-on version — start here, then go there when you want the reasoning.

Everything below was **executed** to write it. Every number and every line of output is copied
from a real run on 2026-08-26, not composed. That is deliberate: `TASK-002` shipped a feature
marked complete whose two clients had never once run, and the cheapest guard against a repeat is
a guide whose author had to run what it tells you to.

---

## 0. The 30-second version

```bash
python examples/trace_demo.py            # record → save → Perfetto file
python examples/trace_demo.py --serve    # …and hold a live server open
```

`examples/trace_demo.py` is a working script, not a snippet. Read it if you prefer code to
prose — it is about 180 lines and covers every path in this document.

---

## 1. Turn it on — before `boot()`

```python
from sagittarius_engine.extensions.audit.recorder import TraceRecorder

app = App(StdLibContainer(), MemoryEventBus())
app.context.enable_tracing(TraceRecorder())  # ← before boot()
app.boot()
```

Tracing is **off by default**: `context.recorder` is `None` until you call this.

The ordering is not a style preference. Extension `register`/`boot` spans only exist if the
recorder exists before the extensions start, and those spans are the answer to *"why does
startup take four seconds"*. Enable it after `boot()` and you have silently thrown that away.

> **A bare `App` with no extensions records nothing at boot** — measured: `0 records`. That is
> correct, not a bug: there is nothing to instrument. Records start when something happens.

## 2. Two things get recorded, and the difference is the point

Run the demo and this is the summary it prints:

```
  captured         : 24 records
  closed spans     : 10
  dropped (evicted): 0
  by lane          : {'user': 12, 'dispatch': 12}
  slowest span     : startup-warmup @ 10.13 ms
```

**The `dispatch` lane — the engine instrumenting itself.** You wrote none of it. One `app.dispatch()`
produces four records sharing one correlation id:

```
[   11.915 ms] dispatch   GreetQuery cid=1     ← dispatch total opens
[   11.921 ms] dispatch   GreetQuery cid=1     ← handler opens
[   14.025 ms] dispatch   GreetQuery cid=1     ← handler closes,  dur 2132847 ns
[   14.033 ms] dispatch   GreetQuery cid=1     ← dispatch closes, dur 2156468 ns
```

The handler's interval nests inside the dispatch total's, and the shared `cid` is what lets a
consumer rebuild the tree. This is the half a generic profiler cannot give you: `py-spy` sees
`_dispatch_inner()`, not *"query `GreetQuery`, through middleware, into its handler"*.

**The USER lane — what you marked.** `ctx.trace` is always present, on or off, so your code never
guards its own markers:

```python
ctx.trace.mark("order-filled", price=101.5)  # instant
with ctx.trace.span("strategy-eval", symbol="BTC"):  # span
    ...
```

The framework knows about **zero** application events by design — see `tracing.md` §2.

## 3. Watch a running process from outside

Terminal 1 — your app, with a server attached to its recorder:

```python
from sagittarius_engine.extensions.audit.infra.trace_server import TraceServer

server = TraceServer(app.context.recorder, host="127.0.0.1", port=9999)
server.start()
server.ready_event.wait(timeout=5.0)  # port=0 picks a free one; read server.port after
```

Terminal 2:

```bash
sagittarius-trace attach ws://127.0.0.1:9999
sagittarius-trace attach ws://127.0.0.1:9999 --save session.sagtrace
```

Real output:

```
attached to ws://127.0.0.1:9999 — protocol v1, capacity=100000, dropped_before_connect=0
[    0.012442] user     startup-warmup dur=10241788ns args={'cache': 'cold'}
[    0.012595] dispatch GreetQuery cat=query cid=1
[    0.014752] dispatch GreetQuery cat=query cid=1 dur=2156468ns
[    0.014778] user     order-filled args={'price': 101.5}
```

### Attach-late is the feature worth knowing about

Those lines arrived **after** connecting, describing work that finished **before** it. The
recorder retains ~100k records whether or not anyone is watching, so you attach *when it goes
wrong* and still see what went wrong. `py-spy` and `viztracer` attach to *now*; this attaches
to *then*. It is the one property this tool has that they cannot.

`dropped_before_connect` in the `hello` line is how many records were evicted before you
arrived — if it is non-zero, your trace has holes and the tool says so rather than presenting a
partial picture as complete.

### `--save` survives being killed

`sagittarius-trace` installs a `SIGTERM` handler, so a container stop, a systemd unit or a
supervisor still writes the file. Verified under `timeout -s TERM`:

```
detached
saved 39 record(s) to session.sagtrace
```

> **If you test this yourself, do not pipe to head.** head exits early, the CLI takes
> `SIGPIPE`, and no file is written — which looks exactly like the save being broken. That cost
> me a wrong diagnosis while writing this section; redirect to a file instead.

### `sagittarius-trace` not found?

The console script ships with the installed package. Running from a repo checkout that was
never `pip install`ed, use the module path instead — same code, same arguments:

```bash
python -m sagittarius_engine.extensions.audit.cli attach ws://127.0.0.1:9999
```

## 4. Open it in a real viewer

```python
from sagittarius_engine.extensions.audit.sagtrace import (
    load_sagtrace,
    save_sagtrace_from_recorder,
)
from sagittarius_engine.extensions.audit.exporters.perfetto import write_perfetto_trace

save_sagtrace_from_recorder("demo.sagtrace", app.context.recorder)
hello, records = load_sagtrace("demo.sagtrace")  # round-trips, checks the version
write_perfetto_trace("demo.perfetto.json", records)
```

Then drag `demo.perfetto.json` onto <https://ui.perfetto.dev>. Nothing is uploaded — Perfetto
parses it in the browser.

`.sagtrace` is plain JSON on purpose: readable with `jq` when the tooling that wrote it is not
at hand.

For OpenTelemetry — Jaeger, Tempo, Grafana, Datadog — see `tracing.md` §4. It needs the `[otel]`
extra; the recorder, `.sagtrace` and Perfetto are stdlib-only and keep working without it.

## 5. Security: the server refuses to be careless

```python
TraceServer(recorder, host="0.0.0.0")  # raises TraceServerConfigError
TraceServer(recorder, host="0.0.0.0", token="…")  # fine
TraceServer(recorder, host="127.0.0.1")  # fine, loopback
```

Binding off-loopback without a token is refused **at construction**, not warned about in a log
nobody reads. A trace stream is everything your application records; an unauthenticated one
reachable off the machine hands that to anyone who connects. With a token set, clients pass
`?token=…` and a bad one is closed with code `4401` before any data is sent.

## 6. Cost

| | |
| :--- | ---: |
| one record, tracing on | ~157 ns |
| the budget it was measured against | 2000 ns |
| a call site with tracing off | ~3 ns over an empty call |
| for scale, one `MemoryEventBus` emit | ~490 ns |

An enabled trace point costs about a third of one event-bus emit. That is what makes leaving it
on in production reasonable — which is what makes attach-late (§3) possible at all.

## 7. When something looks wrong

| Symptom | Cause |
| :--- | :--- |
| `attach` prints nothing after the `attached to …` line | Tracing is off — `context.recorder` is `None`. §1. A version mismatch does **not** look like this: it exits non-zero at connect with both versions named. |
| No boot/extension spans | `enable_tracing()` was called after `boot()`. §1. |
| `dropped_before_connect` is non-zero | The ring buffer evicted records before you attached. Raise `TraceRecorder(capacity=…)`. |
| `--save` wrote nothing | You piped the CLI to head (or another early-exiting reader). §3. |
| `sagittarius-trace: command not found` | Repo checkout, not an install. Use `python -m …audit.cli`. §3. |

## 8. Where the pieces are

| | |
| :--- | :--- |
| `examples/trace_demo.py` | the runnable tour this guide describes |
| `extensions/audit/recorder.py` | `TraceRecorder` — the ring buffer |
| `extensions/audit/cli.py` | `sagittarius-trace` |
| `extensions/audit/infra/trace_server.py` | `TraceServer` — the live transport |
| `extensions/audit/sagtrace.py` | save / load `.sagtrace` |
| `extensions/audit/exporters/` | `perfetto.py`, `otel.py` |
| `kernel/tracing.py` | `ctx.trace`, the application-facing API |
