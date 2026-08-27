# EPIC-007C — The collector extension, and `SNAPSHOT` on the wire

**Epic:** [EPIC-007 — Runtime State Console](../README.md)
**Status:** 🟠 Not started
**Category:** Observability / Extensions
**Priority:** P2
**Depends on:** EPIC-007A, EPIC-007B

---

## 1. The milestone where it becomes a tool

This is the first subtask whose command attaches to a **live process**. Everything before it
is proof that pieces fit; this is the one that produces the thing being built.

It is also independently valuable and should be treated as shippable on its own: a text
rendering of a running application's wiring, over SSH, in a container, on a build agent, is
a usable diagnostic even if `EPIC-007E` never happens.

## 2. Scope

### 2.1 `StateConsoleExtension`

New package `sagittarius_engine/extensions/state_console/` — engine side, **stdlib only**,
never imports PySide6 or anything from `tools/`.

It attaches at the readiness milestone the same way `DiagnosticsExtension` does, through
`when_ready()`. The kernel knows nothing about it; the dependency points from the extension
to the lifecycle, never back. `EPIC-006C` established this and it is not re-argued here.

```python
app.use(StateConsoleExtension(port=8781, token=None, interval_hz=1.0))
```

### 2.2 Collection is pull or interval, never event-driven

`ADR-001` §2.4, and the reason it is not negotiable: `EPIC-005` §2's **D9** was
`AuditService` re-collecting the whole world on every emitted event, with no coalescing, no
rate limit and no delta — which made a task-heavy workload pay for its own observation.

A snapshot is collected when a client asks for one, or on the fixed interval a client opted
into. It is never triggered by an emit, a dispatch, or a task transition.

### 2.3 Zero cost while detached

The collector runs only while at least one client is connected. Detached, the cost is a
comparison on a connection count: **no timer thread, no periodic walk, no allocation**.

`EPIC-005` §4.2 measured its way out of a specification that was backwards (a no-op object
turned out to cost 48.8 ns against 24.5 ns for an `is not None` guard, having been specified
on the assumption it was free). The same discipline applies: this milestone's budget is
measured and the table goes in the outcome section, not asserted here.

**Budget:** ≤ 5 ms per full snapshot on `examples/student_management` at ≤ 1 Hz; nothing
measurable detached.

### 2.4 Transport: nothing new

`TraceServer` already provides the WebSocket, `?token=` auth rejected with close code
`4401` before any data is sent, refusal to bind off-loopback without a token, and
ephemeral-port binding with a readiness event. `MessageType.SNAPSHOT` has been declared in
`contracts.py:44` since `EPIC-005A` and constructed by nothing — this fills that seat.

`TraceServer` gains one thing: a snapshot provider it can call, and the handling of a
client's snapshot request. It keeps owning nothing — it reads a provider the way it already
reads a recorder.

### 2.5 A text rendering, as part of the end-to-end test

`ADR-002` §2.3. A `--format text` rendering of a parsed snapshot, whose output is a string,
so the end-to-end test can assert on it. It is small, it keeps the schema honest — a panel
hides a missing field behind blank space, a text dump cannot — and it makes the console
usable with no display server for free.

Shipped as a `snapshot` subcommand on `sagittarius-trace`, beside `attach`.

## 3. How to run it

Two terminals. **This is the command this epic exists to make work.**

```powershell
# terminal 1 — the observed app, with the console extension attached
.\examples\student_management\run.ps1 -Console
```

```bash
# terminal 2 — read it
.venv/bin/sagittarius-trace snapshot ws://127.0.0.1:8781

# and keep reading it
.venv/bin/sagittarius-trace snapshot ws://127.0.0.1:8781 --watch 1s
```

The `-Console` switch on `run.ps1` is `EPIC-007D`'s deliverable; until it exists, pass the
extension by hand:

```bash
PYTHONPATH=. .venv/bin/python -c "
from examples.student_management.main import build_app
from sagittarius_engine.extensions.state_console import StateConsoleExtension
app = build_app(extra_extensions=[StateConsoleExtension(port=8781)])
input('attached on 8781 - press enter to stop')
app.stop()
"
```

The automated proof:

```bash
.venv/bin/python -m pytest tests/extensions/state_console/test_end_to_end.py -v
```

## 4. Done when

1. **A real `TraceServer` is started, a client connects, and a parsed snapshot is asserted
   on** — in a test, in CI, on every push. This is the test whose absence let `EPIC-005`
   D1–D6 ship in two releases; it is criterion one for that reason.
2. `sagittarius-trace snapshot` prints a live application's state in a terminal.
3. `--watch` re-reads on the interval and does not re-collect between them.
4. A v1 client is refused at connect with both versions named, not left blank.
5. The token and off-loopback rules are asserted against the snapshot path too, not only the
   trace path — an auth check that covers one of two message types is not an auth check.
6. **Measured:** detached cost, and one full snapshot, both in a table in this file's Outcome
   section, in the shape of `EPIC-005` §4.2's.
7. Nothing in `extensions/state_console/` imports outside the stdlib and the engine's own
   interfaces — architecture test extended to say so.
