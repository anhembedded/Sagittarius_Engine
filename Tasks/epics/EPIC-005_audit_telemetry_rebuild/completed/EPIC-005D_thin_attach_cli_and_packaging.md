# EPIC-005D — Thin attach CLI, packaging, docs

**Epic:** [EPIC-005 — Audit Telemetry Teardown & Trace Recorder](../README.md)
**Status:** ✅ **Done 2026-08-26** — see §Outcome. Requirement 1 verified literally: a wheel
built from this branch, installed into a clean Python 3.12 venv, attached to a separately
running engine and wrote a `.sagtrace`. Transcript in §Outcome.
**Category:** Tooling / Packaging
**Priority:** P3
**Depends on:** EPIC-005C

---

## 🎯 Objective

One thin command that attaches to a running engine, streams the live event log and task stats,
and saves a `.sagtrace`.

## What this subtask is *not*

**No timeline widget.** `EPIC-005` §5 is the standing decision: no mainstream framework ships its
own trace viewer, `py-spy` and `viztracer` already cover most of what one would do, and Perfetto
renders the timeline better than we would. This milestone is roughly a tenth of what it was
before that scope cut.

Pressure to add "just a small timeline" will return. Reopening §5 needs a reason that `py-spy`,
`viztracer` and Perfetto together cannot cover — and **live streaming is the only known one**,
which is what this CLI provides in text.

## Requirements

1. From a built wheel in a clean venv, the command attaches to a running engine, streams the
   live event log, and writes a `.sagtrace`.
2. Version mismatch fails **loudly at connect**, never as a blank panel. This is the direct fix
   for D1, where a transport mismatch degraded into a permanent "connection error".
3. **Attach-late works**: start the app, run a workload, *then* attach — the retained buffer
   shows the workload that already finished.
4. Auth: rejected without a token when one is configured; binding off-loopback without a token is
   refused at startup.
5. `.agents/context/` updated; `TASK-002` marked superseded.

## Already guaranteed

The console script this adds is covered by `scripts/verify_wheel_importable.py` step 3 from the
moment it is declared (`TASK-039`). The failure that produced `TASK-002` — shipping a command
that had never run — cannot recur silently.

---

# Outcome

## What shipped

| | Requirement | Where |
| :--- | :--- | :--- |
| 1 | attach, stream live, write `.sagtrace` | `extensions/audit/cli.py` — `sagittarius-trace attach <uri> [--save PATH]` |
| 1 | the live transport it attaches *to* | `extensions/audit/infra/trace_server.py` — `TraceServer` |
| 1 | the recorder's live subscription | `extensions/audit/recorder.py` — `add_tap()`/`remove_tap()` |
| 2 | version mismatch fails at connect | `Envelope.from_dict()` → `check_protocol()`, before any field is read |
| 3 | attach-late | tap registered **before** `snapshot()` — see below |
| 4 | auth + off-loopback refusal | `TraceServer.__init__` raises `TraceServerConfigError`; `4401` close code |
| 5 | docs | new `.agents/context/tracing.md`; `TASK-002` marked ⛔ Superseded in place |

Console script: `sagittarius-trace = "sagittarius_engine.extensions.audit.cli:main"`.
`websockets` is declared in `requirements.txt` as a **real** dependency, not an extra —
`EPIC-005A`'s requirements 5/6 name the transport as a bare requirement, unlike OTel, which §5.1
explicitly gates behind `[otel]`. It had been present only *transitively*, via `python-binance`
(`pip show websockets` → `Required-by: python_binance`), which is not a dependency this engine
gets to rely on.

## The transport was missing, and building it did not require the teardown

Requirement 1 cannot be met without a live transport, and none existed: `EPIC-005A`'s
requirements 5/6 describe exactly this, and that half of `EPIC-005A` was deferred pending the
teardown decision (§3 — deleting `tools/audit_dashboard/`, four engine modules and 13 passing
tests), which is still outstanding.

Those two turned out to be separable. `TraceServer` is **new code alongside** the old
`websocket_broadcaster.py`, which was not touched, moved or deleted — so `EPIC-005A`'s
requirements 5/6 are satisfied in substance while the deletion decision stays open. Its shape is
deliberately the old broadcaster's, because `EPIC-005A` said that module's proven-testable
behaviour "must come back as tests against the new transport": threaded server on its own event
loop, `ready_event` set once actually bound, `port=0` resolved into `.port`, `?token=`
query-string auth, close code `4401`. `tests/extensions/audit/test_trace_server.py` is modelled
directly on `tests/extensions/test_websocket_broadcaster_auth.py` — same fixtures, same close
code.

## Attach-late: duplicate rather than drop, on purpose

`add_tap()` is registered **before** `snapshot()` is read for the backlog. A row captured in the
gap between the two is delivered twice — once in the backlog batch, once live. The other order
can drop one instead. For a diagnostic stream a duplicate is a shrug; a silent gap is the defect
this engine exists to stop shipping, so the ordering is the one that can only over-deliver.

## A real bug: `is` and `==` on the two halves of one subscribe API

`add_tap()` checked `if callback not in self._taps` — equality. The first `remove_tap()` used
`t is not callback` — identity. A bound method creates a **new wrapper object on every attribute
access**: `obj.method is obj.method` is `False` while `obj.method == obj.method` is `True`. So
the ordinary way to subscribe and unsubscribe —

```python
recorder.add_tap(self._on_row)
...
recorder.remove_tap(self._on_row)
```

— registered successfully and then silently failed to unregister, leaving a dead tap notified on
every capture forever. Found by writing a test that used `seen.append` twice and watching
`remove_tap` do nothing. Fixed to `!=`, matching `add_tap`'s `in`.

**The same latent inconsistency exists in `infrastructure/event_bus/bus_observers.py`**
(`EPIC-006F`, already merged): `add_bus_observer` uses `not in`, `remove_bus_observer` uses
`is not`. It was checked rather than assumed and is **currently harmless** — its only caller is
`RuntimeMonitor.start()`/`stop()` (`extensions/diagnostics/runtime.py`), which registers `self`,
a plain object with default identity-based equality, where the two comparisons agree. Left
unfixed as out of scope here, and recorded rather than silently noticed: it is a trap for the
next caller who subscribes a bound method.

## A second one, found only by running the acceptance case literally

The first end-to-end run used `timeout 4 sagittarius-trace attach ... --save session.sagtrace`
and produced **no file at all**, silently. `timeout` sends `SIGTERM`, whose Python default
terminates the process without unwinding, so the `--save` write never ran. `attach()` handled
`KeyboardInterrupt` (Ctrl+C) and nothing else — and `SIGTERM` is what a container stop, a systemd
unit and a supervisor all send, which is most of the ways this command actually gets ended.

"You asked for output and got nothing, with no error" is the exact failure class this epic
exists to close. `main()` now installs a `SIGTERM` handler that raises `KeyboardInterrupt`;
`attach()` deliberately does **not**, because a signal handler is process-global state a library
caller has not asked for. Verified by re-running the same command under `timeout -s TERM`:
`saved 244 record(s)`.

Worth noting how this was found: it is not reachable from any unit test, because a unit test
never sends the process a signal. It came from running the requirement the way the requirement
is written — the same discipline `TASK-002`'s §Note asks for, and the same one that would have
caught `D1` a month earlier.

## Requirement 1, verified literally

Wheel built from this branch, installed into a fresh `python3.12 -m venv` with only
`websockets` alongside it, engine running as a **separate process**, attached ~1.5s after the
workload started:

```
$ ./cleanvenv/bin/sagittarius-trace attach ws://127.0.0.1:34973 --save session.sagtrace
attached to ws://127.0.0.1:34973 — protocol v1, capacity=100000, dropped_before_connect=0
[    0.002718] user     already-happened args={'i': 0}
[    0.002732] user     already-happened args={'i': 1}
[    0.002734] user     already-happened args={'i': 2}
[    0.002794] user     strategy-eval args={'symbol': 'BTC'}
[    0.052970] user     strategy-eval dur=50176348ns args={'symbol': 'BTC'}
[    0.053021] user     order-filled args={'price': 101.5}
...
detached
saved 274 record(s) to session.sagtrace
```

The first four records are timestamped at ~2.7 ms — **1.5 seconds before the client connected**.
That is requirement 3 in one line: the retained buffer showed a workload that had already
finished. `load_sagtrace()` reads the file back to 274 records, `capacity=100000`, `dropped=0`.

## Verification

33 new tests: 8 on the recorder's tap mechanism, 15 on `TraceServer` (config refusal, auth
accept/reject, `hello`-first with the protocol version, attach-late backlog, live streaming,
two-client fan-out, tap removal on disconnect, lifecycle), 10 on the CLI (live text log,
attach-late, `--save` round-trip and no-`--save`, protocol mismatch, a peer that does not speak
`hello` first, a dead address, argparse, `SIGTERM`).

Full suite **1403 passed, 8 skipped**; `ruff check` and `ruff format --check` clean across
`sagittarius_engine/` and `tests/`, `mypy` clean across all 363 source files;
`scripts/verify_wheel_importable.py` passes with the new entry point:

```
[3/3] resolving declared console scripts
  ok   sagittarius-doctor = sagittarius_engine.extensions.diagnostics.cli:main
  ok   sagittarius-trace = sagittarius_engine.extensions.audit.cli:main
```

## Honestly not bulletproof

Each connection's outgoing queue is **unbounded**. A client that stops reading while the
application keeps recording grows that queue until it disconnects or the process runs out of
memory. Deliberate: backpressure across a fan-out is real engineering that a milestone which is
"roughly a tenth of what it was" does not need, and the retained buffer makes disconnect-and-
reattach a safe fix. Recorded here and in the module docstring rather than left for someone to
discover.
