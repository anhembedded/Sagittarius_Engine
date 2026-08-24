"""
@brief Human-readable names for the two things an event-bus log line has to
name: an event, and a handler.

@details Naming something for a sentence a person reads is a different
concern from deciding what a bus *routes* on, and from formatting the report
itself — so it is its own module rather than helper functions living inside
the reporter.

That separation is not pedantic here. `describe_event` deliberately is **not**
a re-implementation of a bus's key resolution: a fourth hand-rolled copy of
that rule is exactly what `BUG-007` is about consolidating. Keeping the label
function here, in a module named for labelling, makes it hard to mistake for
the routing rule.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


def describe_event(event_name_or_type: str | type | Any) -> str:
    """@brief A readable label for an event. For log messages only — never
    for routing or subscription bookkeeping."""
    if isinstance(event_name_or_type, str):
        return event_name_or_type
    name = getattr(event_name_or_type, "event_name", None)
    if isinstance(name, str) and name:
        return name
    if isinstance(event_name_or_type, type):
        return event_name_or_type.__qualname__
    return type(event_name_or_type).__qualname__


def describe_handler(handler: Callable[..., Any]) -> str:
    """@brief A handler name a reader can act on. `repr()` of a bound method
    or a lambda is mostly a memory address; `__qualname__` says which
    function it is and which class it came from."""
    qualname = getattr(handler, "__qualname__", None)
    if qualname is None:
        return repr(handler)
    module = getattr(handler, "__module__", None)
    return f"{module}.{qualname}" if module else qualname
