"""A runnable, self-contained tour of the trace recorder (`EPIC-005`).

Run it and it does the whole loop for you:

    python examples/trace_demo.py              # record, save, report
    python examples/trace_demo.py --serve      # …and hold a live server open

@par What it shows
1. Turning tracing on **before boot**, which is what makes extension boot
   spans exist at all.
2. An application marking its own work (`ctx.trace.mark` / `ctx.trace.span`) —
   the engine knows about zero application events.
3. Saving a `.sagtrace`, and converting it to a Perfetto trace you can open in
   a browser at `ui.perfetto.dev`.
4. With `--serve`, a `TraceServer` you can attach to from another terminal:

       sagittarius-trace attach ws://127.0.0.1:9999

@par Why this file exists
`TASK-002` shipped a feature marked complete whose two clients had never run.
The guard against a repeat is a script that actually executes the documented
path, so "the docs are right" is something you check by running rather than by
reading. Every number this prints is measured at run time, not written down.
"""

from __future__ import annotations

import argparse
import sys
import time
from collections import Counter
from pathlib import Path

from sagittarius_engine.extensions.audit.exporters.perfetto import (
    write_perfetto_trace,
)
from sagittarius_engine.extensions.audit.recorder import TraceRecorder
from sagittarius_engine.extensions.audit.sagtrace import (
    load_sagtrace,
    save_sagtrace_from_recorder,
)
from sagittarius_engine.infrastructure.container.std_container import StdLibContainer
from sagittarius_engine.infrastructure.event_bus.memory_event_bus import MemoryEventBus
from sagittarius_engine.interfaces.i_dispatchable import IDispatchable
from sagittarius_engine.kernel.app import App

DEFAULT_PORT = 9999


def build_app() -> tuple[App, TraceRecorder]:
    """@brief Boots an app with tracing on, returning both.

    @details `enable_tracing()` goes **before** `boot()` on purpose: extension
    register/boot spans are only recorded if the recorder already exists when
    the extensions start, and those spans are the answer to "why does startup
    take four seconds".

    The concrete recorder is returned rather than read back off
    `context.recorder` later, because that attribute is typed
    `ITraceRecorder | None` — the narrow interface `kernel/` is allowed to know
    about, which has `instant`/`span_begin`/`span_end`/`next_cid` and
    deliberately **not** `snapshot()` or `dropped`. Reading a recording back
    out is tooling, not something an instrumentation site ever needs. So hold
    the concrete object if you want to read it; do not widen the interface.
    """
    recorder = TraceRecorder()
    app = App(StdLibContainer(), MemoryEventBus())
    app.context.enable_tracing(recorder)
    app.boot()
    return app, recorder


class GreetQuery(IDispatchable):
    """A minimal handler, only so there is a real `dispatch()` to trace."""

    def execute(self, dto: object = None) -> str:
        time.sleep(0.002)
        return "hi"


def do_some_work(app: App) -> None:
    """@brief Stands in for whatever your application actually does.

    @details Two different things get recorded here, and the difference is the
    whole point of the epic:

    - **The engine instruments itself.** `app.dispatch()` below produces spans
      in the `dispatch` lane with no help from you — the dispatch total, the
      middleware frames, the handler — all sharing one correlation id. That is
      the half no generic profiler can produce: `py-spy` sees
      `_dispatch_inner()`, not "query `GreetQuery`, through middleware, into
      its handler".
    - **The application marks its own work.** `ctx.trace` is yours. The
      framework hard-coding `student.added` and three other demo-app event
      names was defect `D8`; the replacement is the opposite arrangement, so
      the engine knows about zero application events.
    """
    ctx = app.context

    with ctx.trace.span("startup-warmup", cache="cold"):
        time.sleep(0.01)

    for i in range(3):
        with ctx.trace.span("strategy-eval", symbol="BTC", pass_no=i):
            app.dispatch(GreetQuery, None)  # engine-instrumented, not by us
            ctx.trace.mark("order-filled", price=101.5 + i)

    ctx.trace.mark("warmup-complete")


def report(recorder: TraceRecorder) -> None:
    records = recorder.snapshot()
    spans = [r for r in records if r.dur]
    print(f"\n  captured         : {len(records)} records")
    print(f"  closed spans     : {len(spans)}")
    print(f"  dropped (evicted): {recorder.dropped}")

    # Lanes are the point: `user` is what you marked, everything else the
    # engine recorded about itself without being asked.
    lanes = Counter(r.lane.value for r in records)
    print(f"  by lane          : {dict(lanes)}")

    if spans:
        slowest = max(spans, key=lambda r: r.dur)
        print(f"  slowest span     : {slowest.name} @ {slowest.dur / 1e6:.2f} ms")

    print("\n  first few records:")
    for r in records[:8]:
        cid = f" cid={r.cid}" if r.cid else ""
        print(f"    [{r.t / 1e6:9.3f} ms] {r.lane.value:<10} {r.name}{cid}")


def save_and_convert(recorder: TraceRecorder, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    sagtrace = out_dir / "demo.sagtrace"
    perfetto = out_dir / "demo.perfetto.json"

    save_sagtrace_from_recorder(sagtrace, recorder)

    # Read it back rather than reusing the in-memory records: this is the
    # round trip a consumer actually performs, so a format that only works
    # while the writing process is alive would fail right here.
    hello, records = load_sagtrace(sagtrace)
    write_perfetto_trace(str(perfetto), records)

    print(f"\n  saved   {sagtrace}  ({sagtrace.stat().st_size} bytes)")
    print(f"  saved   {perfetto}  ({perfetto.stat().st_size} bytes)")
    print(f"  reopened: protocol v{hello.protocol_version}, {len(records)} records")
    print(f"\n  Open {perfetto.name} at https://ui.perfetto.dev (drag the file in).")


def serve(app: App, recorder: TraceRecorder, port: int) -> None:
    """@brief Holds a live trace server open until Ctrl+C."""
    from sagittarius_engine.extensions.audit.infra.trace_server import TraceServer

    server = TraceServer(recorder, host="127.0.0.1", port=port)
    server.start()
    if not server.ready_event.wait(timeout=5.0):
        print("server failed to bind", file=sys.stderr)
        return

    uri = f"ws://{server.host}:{server.port}"
    print(f"\n  live server: {uri}")
    print("  attach from another terminal:")
    print(f"      sagittarius-trace attach {uri}")
    print(f"      sagittarius-trace attach {uri} --save session.sagtrace")
    print("\n  recording more work every 2s. Ctrl+C to stop.\n")

    try:
        n = 0
        while True:
            time.sleep(2)
            n += 1
            with app.context.trace.span("heartbeat", n=n):
                time.sleep(0.001)
            app.context.trace.mark("tick", n=n)
            print(f"  … emitted heartbeat {n}")
    except KeyboardInterrupt:
        print("\n  stopping.")
    finally:
        server.stop()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="trace_demo",
        description="Record a trace, save it, and optionally serve it live.",
    )
    parser.add_argument(
        "--serve",
        action="store_true",
        help=f"hold a TraceServer open on port {DEFAULT_PORT} after recording",
    )
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument(
        "--out",
        default="trace_out",
        help="directory for the .sagtrace and Perfetto files",
    )
    args = parser.parse_args(argv)

    print("booting with tracing enabled…")
    app, recorder = build_app()
    do_some_work(app)

    report(recorder)
    save_and_convert(recorder, Path(args.out))

    if args.serve:
        serve(app, recorder, args.port)

    app.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
