"""
@brief The TRACE line a bus writes when it dispatches an event.

@details Separate from `handler_reporting` because tracing a normal dispatch
and reporting a failure are different abstractions: one is routine flow
diagnostics that is off in every ordinary run, the other is an error report
that must always survive. They also have opposite requirements — this one
must stay cheap enough to sit on a per-tick code path, that one must never be
suppressed.
"""

from __future__ import annotations

from sagittarius_engine.interfaces import ILogger


def log_event_emitted(logger: ILogger, event_name: str, handler_count: int) -> None:
    """
    @brief Records that an event was dispatched, at TRACE.

    @details TRACE, not INFO, because a bus emits once per event and some
    events are per-tick — `ILogger.trace` is documented for exactly this
    ("too high-frequency even for a normal `--dev` run"). One INFO line per
    emitted event is the log flood that froze the consuming app's UI thread
    in its `BUG-042`.

    The payload is deliberately **not** included. Two reasons, both concrete:
    formatting it costs a `repr()` of an arbitrary object on every single
    emit even when the level is disabled (`ILogger` takes an already-formatted
    string, so there is no lazy-formatting escape hatch), and a payload dumped
    into a log line is how domain data ends up somewhere it was never meant to
    be. The event name and handler count are what flow-tracing actually needs;
    a handler that wants its own payload logged is free to log it.
    """
    logger.trace(f"Dispatching '{event_name}' to {handler_count} handler(s)")
