from typing import TYPE_CHECKING

from sagittarius_engine.domain.event_registry import EventRegistry

if TYPE_CHECKING:
    from sagittarius_engine.kernel.i_kernel_context import IKernelContext
from sagittarius_engine.interfaces import ILogger

#: No dedicated event class exists for this one — the payload is the `App`
#: instance itself, not a purpose-built event shape. Named as a constant
#: (rather than inlined at the `emit()` call site below) for the same reason
#: every other lifecycle event in `kernel/events.py`/`runtime/*/events.py`
#: reads its name off a class attribute: one place to change on a rename.
APP_BOOTED_EVENT_NAME = "app.booted"

EventRegistry.register_named(
    APP_BOOTED_EVENT_NAME, None, module="sagittarius_engine.kernel.bootstrap"
)


class Bootstrap:
    """Responsible for bootstrapping the engine."""

    def __init__(self, context: "IKernelContext") -> None:
        self.context = context

    def _get_logger(self) -> ILogger:
        return self.context.logger

    def boot(self, auto_discover: str | None = None) -> None:
        """
        @brief Boots the application.
        """
        logger = self._get_logger()
        logger.info("App is booting...")

        self.context.lifecycle.set_booting()

        # Start Async Runtime early so extensions/hosted services can use it
        self.context.async_runtime.start()

        try:
            if auto_discover:
                self.context.module_loader.discover_and_load(auto_discover)

            self.context.extension_manager.initialize_and_start()

            # Start Hosted Services
            self.context.hosted_services.start()

            # Start Scheduler
            self.context.scheduler.start()

        except (
            RuntimeError,
            ValueError,
            TypeError,
            AttributeError,
            ImportError,
            OSError,
        ) as e:
            logger.error(
                f"[Bootstrap] Error during boot sequence: {e}. Shutting down runtime..."
            )
            # Clean up what was started
            try:
                self.context.scheduler.stop()
            except (RuntimeError, ValueError) as se:
                logger.warning(
                    f"[Bootstrap] Error stopping scheduler during boot cleanup: {se}"
                )
            try:
                self.context.hosted_services.stop()
            except (RuntimeError, ValueError) as he:
                logger.warning(
                    f"[Bootstrap] Error stopping hosted services during boot cleanup: {he}"
                )
            try:
                self.context.async_runtime.stop()
            except (RuntimeError, ValueError) as ae:
                logger.warning(
                    f"[Bootstrap] Error stopping async runtime during boot cleanup: {ae}"
                )
            raise e

        self.context.lifecycle.set_booted()

        logger.info(
            f"App booted successfully with {len(self.context.modules)} modules."
        )

        self.context.event_bus.emit(APP_BOOTED_EVENT_NAME, self.context.app)

        # Readiness follows unconditionally, and deliberately so.
        #
        # An earlier draft gated this on "no extension was left stranded",
        # reasoning that `boot()` returning is not the same as everything
        # having come up. Measured, that gate was dead code: during boot,
        # `initialize_and_start()` raises for both ways an extension can fail
        # to initialise — `ExtensionDependencyError` for a dependency that was
        # never registered, `ExtensionCircularDependencyError` for a cycle — so
        # control never reaches here with anything stranded. Keeping the check
        # would have implied a boot outcome this engine cannot produce.
        #
        # Stranding is real, but only *after* boot: `register()` defers an
        # extension with unmet dependencies and never raises, so a plugin added
        # to a running engine can sit uninitialised while the state still reads
        # `ready`. A one-shot gate here could not have caught that either. It is
        # `BUG-008`, and `EPIC-006B`'s check D1 already reports it at any point
        # in the engine's life, which is what that case needs.
        self.context.lifecycle.set_ready()
