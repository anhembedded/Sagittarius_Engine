"""
@brief `resolve_logger` — turns an optional `ILogger` into one that is always
safe to call, and never silent about errors.

@details Lives beside the loggers rather than in the event-bus package
because deciding *which logger a component gets when it was handed none* is a
logging concern, not a bus concern — the buses are simply its first callers.

The choice it encodes is the substance of `BUG-005`'s fix: the alternative,
`NullLogger`, discards everything, so a component that was given no logger
would keep losing exceptions exactly as before. See `FallbackLogger` for why
`StdLogger` cannot be used here either.
"""

from __future__ import annotations

from sagittarius_engine.infrastructure.logging.fallback_logger import FallbackLogger
from sagittarius_engine.interfaces import ILogger


def resolve_logger(logger: ILogger | None, *, fallback_name: str) -> ILogger:
    """
    @brief Returns the injected logger, or a `FallbackLogger` that still
    reports rather than a `NullLogger` that would discard the failures
    callers rely on seeing.
    @param fallback_name The logger name to fall back to, so records stay
    attributable to the component that produced them and an application can
    route or silence one noisy component without touching the others.
    """
    return logger if logger is not None else FallbackLogger(fallback_name)
