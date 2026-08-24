"""
@brief `FallbackLogger` — an `ILogger` for code that was given no logger and
must still not go silent.

@details
Distinct from the two loggers that already exist, and deliberately so:

- `NullLogger` (`utils/null_logger.py`) discards everything. It is the right
  Null Object for *optional diagnostics* — a component whose logging is
  genuinely nice-to-have. It is the wrong default for an **error** path: an
  exception routed into `NullLogger` is an exception nobody will ever learn
  about, which is precisely the defect `BUG-006` reports for the event buses.
- `StdLogger` (`std_logger.py`) is the application's configured logger. It
  cannot be used as an implicit fallback because constructing it *mutates
  global state*: it clears and replaces the handlers on the shared `"App"`
  logger and resets its level. A library quietly reconfiguring the host
  application's logging as a side effect of not being handed a logger would
  be a far worse bug than the one this class exists to fix.

`FallbackLogger` configures nothing. It forwards to `logging.getLogger(name)`
and lets whatever the application has already set up decide what happens. An
application that configured logging sees these records in its own handlers;
an application that configured nothing still sees WARNING and above, because
Python's own `logging.lastResort` handler writes those to stderr. Either way
an exception leaves a trace, which is the entire point.
"""

from __future__ import annotations

import logging
from typing import Any

from sagittarius_engine.infrastructure.logging.logger_config import TRACE
from sagittarius_engine.interfaces import ILogger


class FallbackLogger(ILogger):
    """
    @brief Forwards to the standard `logging` module without configuring it.

    @param name The logger name to forward to. Pass the calling module's
    `__name__` so records are attributable to where they came from, and so an
    application can silence or route one noisy component without touching the
    others.
    """

    def __init__(self, name: str) -> None:
        self._logger = logging.getLogger(name)

    def _log(self, level: int, message: str, extra: dict[str, Any] | None) -> None:
        #: `extra` is passed through as a single nested key rather than
        #: splatted into the record's namespace: `logging` raises KeyError if
        #: an `extra` key collides with a built-in `LogRecord` attribute
        #: (`message`, `module`, `name`, ...), and this class cannot vet keys
        #: it receives from arbitrary callers.
        self._logger.log(level, message, extra={"context": extra} if extra else None)

    def info(self, message: str, extra: dict[str, Any] | None = None) -> None:
        self._log(logging.INFO, message, extra)

    def warning(self, message: str, extra: dict[str, Any] | None = None) -> None:
        self._log(logging.WARNING, message, extra)

    def error(self, message: str, extra: dict[str, Any] | None = None) -> None:
        self._log(logging.ERROR, message, extra)

    def debug(self, message: str, extra: dict[str, Any] | None = None) -> None:
        self._log(logging.DEBUG, message, extra)

    def critical(self, message: str, extra: dict[str, Any] | None = None) -> None:
        self._log(logging.CRITICAL, message, extra)

    def trace(self, message: str, extra: dict[str, Any] | None = None) -> None:
        self._log(TRACE, message, extra)
