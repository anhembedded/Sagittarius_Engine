"""
@brief `EventDelivery` — one handler call in transit across the thread hop.

@details A value object, kept apart from `QtEventBridge` (the QObject that
sends it) because a piece of data and the machinery that transports it are
different abstractions.

A dataclass rather than a bare tuple so the slot that receives it cannot
silently drift out of order with the code that packs it — `code-rule.md`
requires dataclasses over raw tuples/dicts for exactly this reason, and a
mis-ordered 3-tuple crossing a Qt signal is the kind of mistake that fails
far from where it was made.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class EventDelivery:
    """@brief The handler to call, what to call it with, and the event label
    to name in a failure report if it raises."""

    handler: Callable[..., Any]
    payload: Any
    event_label: str
