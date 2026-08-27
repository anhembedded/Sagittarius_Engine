"""`_StateMachineWatcher` — `EPIC-007F` §3.2.

An application opts a `BaseStateMachine` in with one line,
`StateConsoleExtension.watch_state_machine(name, machine)`. This is what
that call installs.

@par Two mechanisms, because success and rejection are observed differently
`add_global_callback()` fires only on a *successful* transition
(`state_machine.py::transition_to()`/`declarative_state_machine.py::dispatch()`
both call it after the state has already changed) — a rejected attempt
raises `InvalidStateTransitionError` before that point and the callback
never runs (`REF-005`). So a rejection has to be caught at the call site
instead, and since the watcher must not require every caller of
`transition_to()`/`dispatch()` to add its own try/except, it wraps the bound
methods on the *instance* it was asked to watch, catches the exception
there, records it, and re-raises unchanged — the app's own behaviour
(the exception still propagates) is untouched.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from typing import Any

from sagittarius_engine.extensions.audit.contracts import (
    StateMachineState,
    StateMachineTransition,
)
from sagittarius_engine.extensions.fsm.exceptions import InvalidStateTransitionError

#: Bounded, like `TaskManager`'s own retained-task cap (`EPIC-007B` §2.3) —
#: a log a diagnostic console can show, not an unbounded history a
#: long-running app would grow forever.
_MAX_TRANSITIONS = 200

#: Both methods a watched machine might expose: `transition_to` on every
#: `BaseStateMachine`, `dispatch` only on a `DeclarativeStateMachine`.
_WATCHED_METHOD_NAMES = ("transition_to", "dispatch")


class _StateMachineWatcher:
    def __init__(self, name: str, machine: Any) -> None:
        self.name = name
        self._machine = machine
        self._lock = threading.Lock()
        self._transitions: deque[StateMachineTransition] = deque(
            maxlen=_MAX_TRANSITIONS
        )
        self._rejected_count = 0

        machine.add_global_callback(self._on_transition)
        self._wrap_rejecting_methods()

    # -------------------------------------------------------------- install

    def _wrap_rejecting_methods(self) -> None:
        for method_name in _WATCHED_METHOD_NAMES:
            original = getattr(self._machine, method_name, None)
            if original is None:
                continue
            setattr(self._machine, method_name, self._wrap_rejecting(original))

    def _wrap_rejecting(self, original: Any) -> Any:
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return original(*args, **kwargs)
            except InvalidStateTransitionError as exc:
                self._record_rejection(exc)
                raise

        return wrapper

    # -------------------------------------------------------------- record

    def _on_transition(self, old_state: Any, new_state: Any) -> None:
        with self._lock:
            self._transitions.append(
                StateMachineTransition(
                    from_state=old_state.name,
                    to_state=new_state.name,
                    at_ns=time.perf_counter_ns(),
                )
            )

    def _record_rejection(self, exc: InvalidStateTransitionError) -> None:
        with self._lock:
            self._rejected_count += 1
            self._transitions.append(
                StateMachineTransition(
                    from_state=exc.from_state,
                    to_state=exc.to_state,
                    event=exc.event or "",
                    rejected=True,
                    at_ns=time.perf_counter_ns(),
                )
            )

    # ------------------------------------------------------------- collect

    def collect(self) -> StateMachineState:
        with self._lock:
            transitions = tuple(self._transitions)
            rejected_count = self._rejected_count
        return StateMachineState(
            name=self.name,
            current_state=self._machine.current_state.name,
            transitions=transitions,
            rejected_count=rejected_count,
        )
