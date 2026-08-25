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

from .inspector import WiringInspector
from .report import WiringReport


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
    """

    def __init__(
        self,
        *,
        fail_fast: bool = False,
        expected_unheard: Iterable[str] = (),
    ) -> None:
        self.fail_fast = fail_fast
        self.expected_unheard = tuple(expected_unheard)
        self.dependencies: list[str] = []
        #: The report from the most recent run, or `None` before readiness.
        #: Kept so a test or an operator can read the findings directly rather
        #: than parsing them back out of a log line.
        self.last_report: WiringReport | None = None

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
        context.lifecycle.when_ready(lambda: self._inspect(context))

    def shutdown(self, context: Any) -> None:
        pass

    def _inspect(self, context: Any) -> None:
        report = WiringInspector().inspect(
            bus=context.event_bus,
            container=context.container,
            extension_manager=getattr(context, "extension_manager", None),
            hosted_services=getattr(context, "hosted_services", None),
            scheduler=getattr(context, "scheduler", None),
            expected_unheard=self.expected_unheard,
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
