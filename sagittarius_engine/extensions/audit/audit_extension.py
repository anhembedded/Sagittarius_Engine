from sagittarius_engine.extensions.audit.audit_service import (
    AuditService,
    IAuditContext,
)
from sagittarius_engine.interfaces import IExtension


class AuditExtension(IExtension[IAuditContext]):
    """
    @brief Framework Observability & Diagnostics Extension.
    @details Installs telemetry tracking and optionally an interactive TUI dashboard.
    """

    def __init__(self, enable_dashboard: bool = False) -> None:
        self.enable_dashboard = enable_dashboard
        self.dependencies = ["HealthExtension"]

    def register(self, context: IAuditContext) -> None:
        """
        @brief Binds the AuditService into the DI container.
        """
        audit_service = AuditService(context)
        context.container.singleton(AuditService, audit_service)

    def boot(self, context: IAuditContext) -> None:
        """
        @brief Starts the Telemetry HTTP Server if dashboard is enabled.
        """
        if self.enable_dashboard:
            audit_service = context.container.resolve(AuditService)
            audit_service.start_server()

    def shutdown(self, context: IAuditContext) -> None:
        """
        @brief Stops the Telemetry HTTP Server.
        """
        if self.enable_dashboard:
            audit_service = context.container.resolve(AuditService)
            audit_service.stop_server()
