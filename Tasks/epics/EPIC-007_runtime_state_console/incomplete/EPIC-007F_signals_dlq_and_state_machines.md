# EPIC-007F — Signals: the dead-letter queue and state machines

**Epic:** [EPIC-007 — Runtime State Console](../README.md)
**Status:** 🟠 Not started
**Category:** Observability / Diagnostics
**Priority:** P2
**Depends on:** EPIC-007C, EPIC-007D, EPIC-007E

---

## 1. Why these two, and why last

Every other milestone renders state that *something* could already reach — a report, a CLI,
a test. These two render state that **the engine holds and nothing whatsoever surfaces**, and
they are the highest value-per-line in the epic for that reason.

They come last because each needs a live app with the condition seeded (`EPIC-007D`) and a
screen to put it on (`EPIC-007E`). Neither adds instrumentation: both read APIs that exist.

## 2. The dead-letter queue

`ResilientEventBus` retries a failing handler `max_retries` times and then parks the event:

```python
def get_dlq(self) -> list[tuple[str, Any, Callable, Exception]]:
def reprocess(self) -> None:
```

**`grep` across the repository finds both called from tests and nowhere else.** So an event
that exhausted every retry is sitting in memory right now in any app using this bus: nothing
logs it at that point, nothing reads it, and it is gone when the process exits. There is
already a public method to replay it and no way to know you should.

### 2.1 What the panel shows

Per parked event: name, the handler that gave up, the exception type and message, the
payload, retries spent, and when. Grouped by event name, newest first.

### 2.2 Reprocess is rendered, disabled, and not wired

The control appears — a queue you can see and not act on is half a feature, and hiding the
control hides the fact that a remedy exists. It is **disabled**, with the reason stated on
screen: write actions are off.

`reprocess()` re-emits into a live application from a socket. That is a write path with a
real blast radius, and `EPIC-007` §6 puts every write action behind **ADR-003**. Wiring it
here because the method happens to be one call away is exactly the shortcut
`design-discipline.md` exists to refuse.

## 3. State machines

`BaseStateMachine.add_global_callback(cb)` is a **public, existing** extension point taking
`(old_state, new_state)`. One callback per machine yields the current state, the transition
history, and the count per state — with no change to the FSM implementation at all.

### 3.1 The finding that justifies the panel

**Corrected `REF-005`:** this section originally claimed `transition_to()` "returns `False`
on an illegal transition and raises nothing." That was never true of `BaseStateMachine` —
`transition_to()`/`dispatch()` both `logger.error(...)` and raise
`InvalidStateTransitionError` (`state_machine.py`, `declarative_state_machine.py`). The panel
this section justifies is still worth building, on a narrower and accurate ground: a raised
exception is visible only to a caller that catches it and does something with it, and nothing
in the engine does that today. A rejected transition inside a handler the event bus already
isolates (`handler_reporting.py`) is caught, logged once, and otherwise lost — the same shape
as `EPIC-006`'s A2 typo, not because the FSM stays silent, but because everything downstream
of it currently is.

The transition log therefore renders rejected attempts **in `danger`, inline with the
accepted ones**, and the count of rejections is a first-class number on the panel. If this
milestone ships only one thing, it is this row.

### 3.2 Registration

A machine is not discoverable — there is no registry of `BaseStateMachine` instances. So the
application opts in, one line per machine, at the point it constructs one:

```python
console.watch_state_machine("EnrolmentFlow", flow)
```

Explicit rather than a `__init_subclass__` registry, and for a measured reason:
`EPIC-006D` found that a subclass registry would have discovered **0 of the demo app's 7
handlers**, because the marker was duck-typed. Guessing at discovery has already cost this
repository a rewrite; an application naming its own machines cannot be wrong.

## 4. Also on this screen

**UI-thread health**, for consumers using `pyside_mvc`: `UIWatchdog` already detects main
loop freezes (`_handle_freeze(elapsed)`) and `thread_affinity` / `safe_ui_action` already
guard cross-thread UI mutation. Both currently only log. Surfacing the counts and the worst
elapsed is the cheapest red flag in the epic for a desktop app.

## 5. How to run it

```powershell
# the seeded app plus the console; open the Signals screen
.\scripts\run-console.ps1 -Demo
```

`EPIC-007D`'s `-DemoFaults` seeds both conditions: a handler on `student.deleted` that
raises until its retries are spent, and an `EnrolmentFlow` driven through one illegal move.

Text path, no display server:

```bash
.venv/bin/sagittarius-trace snapshot ws://127.0.0.1:8781 --watch 1s
# the `signals` section carries both
```

Tests:

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/tools/state_console/test_signals_screen.py -v
.venv/bin/python -m pytest tests/extensions/state_console/test_dlq_section.py -v
```

## 6. Done when

1. An event that exhausted its retries appears on screen with its handler, exception and
   payload — **the first time anything in this repository other than a test has read
   `get_dlq()`**.
2. The reprocess control is visible, disabled, and states why.
3. A rejected transition appears in the transition log, marked as rejected, and is counted.
4. A test drives a machine through an illegal transition and asserts the console reports it —
   the behaviour is `transition_to()` raising `InvalidStateTransitionError` (`REF-005`), so
   the panel's global callback fires only on a *successful* transition and the rejected one
   has to be observed by catching the exception at the call site, not by reading a return
   value; the test asserts on the console's output, not on the FSM.
5. Watching a machine costs nothing measurable when the console is detached: the callback is
   registered only while a client is attached, or it is a plain append the collector reads.
6. UI-thread freeze and off-thread-mutation counts appear when the observed app uses
   `pyside_mvc`, and the section is **absent rather than zeroed** when it does not — a zero
   there means "no violations", and showing it for a headless app would be a lie.
