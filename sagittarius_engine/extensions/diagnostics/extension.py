"""`DiagnosticsExtension` — runs the wiring inspection when the engine is ready.

The dependency deliberately points this way. The kernel knows nothing about
diagnostics; the extension attaches itself to the lifecycle milestone through
`when_ready()`. A kernel that imported an extension to run a check would invert
the engine's own layering, and this repository has removed that shape of
coupling twice already (`TASK-008`, `TASK-013`).
"""

from collections.abc import Iterable
from typing import Any

from sagittarius_engine.interfaces import IExtension

from .handlers import as_handler_tuple, discover_handlers
from .inspector import WiringInspector
from .report import WiringReport
from .runtime import RuntimeMonitor


class DiagnosticsError(RuntimeError):
    """@brief Raised by `fail_fast=True` when the wiring report contains errors."""


class DiagnosticsExtension(IExtension[Any]):
    """
    @brief Inspects the application's wiring at the readiness milestone.

    @details Readiness is the one instant where the answer is both complete and
    still ahead of any real work. Inspecting earlier reports subscriptions that
    have not been made yet; inspecting later means the application has already
    been serving while mis-wired.

    @par Usage
    @code
    app.use(DiagnosticsExtension(fail_fast=True))
    app.boot()   # report is logged; a wiring error aborts here
    @endcode

    @param fail_fast Raise `DiagnosticsError` when the report contains errors.
        Default `False`: an engine that refuses to start over a diagnostic is a
        worse default than one that says loudly what is wrong. Warnings never
        block — see `WiringReport.ok`.
    @param expected_unheard Event names this application deliberately does not
        listen to (check A1). Declared by the application; the framework never
        decides an event is legitimately unheard on its behalf.
    @param handlers Dispatchable handler classes to pre-flight (checks B1–B3).
        Exact, and preferred where the list is short.
    @param watch_runtime Also watch the running application for the `EPIC-006F`
        checks — an event emitted with nobody listening (R1), and a handler
        that raised (R2). Off by default: the static checks are a single pass
        at readiness and cost nothing afterwards, while this one observes every
        dispatch for the life of the process. Measured at ~98 ns per emit with
        it on, and nothing measurable with it off.
    @param handler_packages Dotted package prefixes to search for handlers
        instead of listing them — e.g. `("myapp.application",)`. Imports
        nothing; see `discover_handlers()`. A prefix is required because
        searching everything would sweep in unrelated classes that happen to
        have an `execute` method.
    """

    def __init__(
        self,
        *,
        fail_fast: bool = False,
        expected_unheard: Iterable[str] = (),
        handlers: Iterable[type] = (),
        handler_packages: Iterable[str] = (),
        watch_runtime: bool = False,
    ) -> None:
        self.fail_fast = fail_fast
        self.expected_unheard = tuple(expected_unheard)
        self.handlers = as_handler_tuple(handlers)
        self.handler_packages = tuple(handler_packages)
        self.dependencies: list[str] = []
        #: The report from the most recent run, or `None` before readiness.
        #: Kept so a test or an operator can read the findings directly rather
        #: than parsing them back out of a log line.
        self.last_report: WiringReport | None = None
        #: `EPIC-006F`'s observer, or `None` when `watch_runtime` is off. Kept
        #: rather than created on demand so `runtime_report()` can be read at
        #: any point, including after shutdown — which is when it is most
        #: useful, because that is when everything that was going to happen has.
        self.runtime_monitor: RuntimeMonitor | None = (
            RuntimeMonitor(expected_unheard=self.expected_unheard)
            if watch_runtime
            else None
        )

    def register(self, context: Any) -> None:
        pass

    def boot(self, context: Any) -> None:
        """
        @brief Defers the inspection to the readiness milestone.

        @details `when_ready()` rather than a subscription to `app.ready`:
        extensions boot in dependency order, so this one may well be booting
        *after* readiness in some arrangements, and an event subscription made
        after the event has fired waits forever. That is the exact defect
        recorded in `extensions/health/health_check_requested.py:9`.
        """
        if self.runtime_monitor is not None:
            # Started in `boot()`, not at readiness: an event emitted *during*
            # boot with nobody listening is exactly as much of a defect as one
            # emitted afterwards, and waiting for readiness would miss the
            # entire startup sequence — where subscriptions are still being
            # made and the mistake is most likely.
            self.runtime_monitor.start()
        context.lifecycle.when_ready(lambda: self._inspect(context))

    def shutdown(self, context: Any) -> None:
        """@brief Stops observing, and logs what the run turned up.

        @details The findings are logged here rather than only exposed on the
        monitor: a runtime anomaly that nobody reads is the same as one that
        was never detected, and shutdown is the one moment the whole run is
        known. `stop()` keeps what was seen, so `runtime_report()` still works
        after this."""
        if self.runtime_monitor is None:
            return

        self.runtime_monitor.stop()
        report = self.runtime_monitor.report()
        logger = getattr(context, "logger", None)
        if logger is None or report.ok and not report.warnings:
            return
        if report.errors:
            logger.error(f"Runtime anomalies during this run:\n{report.format()}")
        else:
            logger.warning(f"Runtime anomalies during this run:\n{report.format()}")

    def runtime_report(self) -> WiringReport | None:
        """@brief What `watch_runtime` has seen so far, or `None` when off."""
        if self.runtime_monitor is None:
            return None
        return self.runtime_monitor.report()

    def _resolve_handlers(self) -> tuple[type, ...]:
        """@brief Explicit handlers, plus anything found under the configured
        packages. Discovery runs at inspection time rather than construction:
        the application may not have imported its handler modules yet when the
        extension is built."""
        discovered = (
            discover_handlers(*self.handler_packages) if self.handler_packages else ()
        )
        return tuple(dict.fromkeys((*self.handlers, *discovered)))

    def _inspect(self, context: Any) -> None:
        report = WiringInspector().inspect(
            bus=context.event_bus,
            container=context.container,
            extension_manager=getattr(context, "extension_manager", None),
            hosted_services=getattr(context, "hosted_services", None),
            scheduler=getattr(context, "scheduler", None),
            expected_unheard=self.expected_unheard,
            handlers=self._resolve_handlers(),
        )
        self.last_report = report

        logger = getattr(context, "logger", None)
        if logger is not None:
            if report.errors:
                logger.error(report.format())
            elif report.warnings:
                logger.warning(report.format())
            else:
                logger.info(report.format())

        if self.fail_fast and not report.ok:
            raise DiagnosticsError(
                f"wiring inspection found {len(report.errors)} error(s):\n"
                f"{report.format()}"
            )
