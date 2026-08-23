import logging
from typing import Any

from sagittarius_engine.runtime.hosted.events import (
    HostedServiceStarted,
    HostedServiceStopped,
)
from sagittarius_engine.runtime.hosted.hosted_service import IHostedService


class HostedServiceManager:
    """
    @brief Manages registration, startup, stop, and rollback of Hosted Services.
    """

    def __init__(self, context: Any) -> None:
        self.context = context
        self.services: list[IHostedService] = []
        self.started_services: list[IHostedService] = []
        self._logger = logging.getLogger("App")

    def register(self, service: IHostedService) -> None:
        """
        @brief Registers a hosted service.
        """
        if not isinstance(service, IHostedService):
            raise TypeError("Service must implement IHostedService")
        self.services.append(service)

    def _emit(self, event_name: str, event_data: Any) -> None:
        try:
            self.context.event_bus.emit(event_name, event_data)
        except Exception as e:
            self.context.logger.error(f"Failed to emit event: {e}")

    def start(self) -> None:
        """
        @brief Starts all registered hosted services.
        @details On failure of any service startup, performs safe rollback.
        """
        for service in self.services:
            name = service.__class__.__name__
            self._logger.info(f"Starting Hosted Service '{name}'...")
            try:
                service.start(self.context)
                self.started_services.append(service)
                self._emit("runtime.hosted.started", HostedServiceStarted(name))
            except Exception as e:
                self._logger.error(
                    f"Failed to start Hosted Service '{name}': {e}. Rolling back..."
                )
                self._rollback(e)
                raise e

    def _rollback(self, original_error: Exception) -> None:
        """
        @brief Stops previously started services in reverse order.
        """
        for service in reversed(self.started_services):
            name = service.__class__.__name__
            self._logger.info(f"Stopping Hosted Service '{name}' due to rollback...")
            try:
                service.stop(self.context)
                self._emit("runtime.hosted.stopped", HostedServiceStopped(name))
            except Exception as stop_error:
                self._logger.error(
                    f"Error stopping Hosted Service '{name}' during rollback: {stop_error}"
                )
        self.started_services.clear()

    def stop(self) -> None:
        """
        @brief Stops all started hosted services in reverse order.
        """
        errors = []
        for service in reversed(self.started_services):
            name = service.__class__.__name__
            self._logger.info(f"Stopping Hosted Service '{name}'...")
            try:
                service.stop(self.context)
                self._emit("runtime.hosted.stopped", HostedServiceStopped(name))
            except Exception as e:
                self._logger.error(f"Error stopping Hosted Service '{name}': {e}")
                errors.append(e)

        self.started_services.clear()
        if errors:
            raise RuntimeError(f"Multiple errors stopping hosted services: {errors}")
