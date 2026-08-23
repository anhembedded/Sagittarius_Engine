from dataclasses import dataclass
from typing import Any

from sagittarius_engine.extensions.cqrs import IQuery
from sagittarius_engine.extensions.persistence import ISession
from sagittarius_engine.interfaces import IContainer, IEventBus


@dataclass
class HealthCheckDTO:
    """
    @brief DTO for HealthCheckQuery.
    """

    pass


class HealthCheckQuery(IQuery):
    """
    @brief Query to perform a health check on the application components.
    """

    def __init__(self, container: IContainer, event_bus: IEventBus):
        self.container = container
        self.event_bus = event_bus

    def execute(self, input_dto: HealthCheckDTO | None = None) -> dict[str, Any]:
        """
        @brief Executes the health check.
        @return A dictionary containing the health status of various components.
        """
        status: dict[str, Any] = {
            "status": "healthy",
            "components": {
                "container": "ok",
                "event_bus": "ok",
                "database": "unknown",
            },
        }
        try:
            self.container.resolve(IContainer)
        except Exception:
            status["components"]["container"] = "error: container resolution failed"
            status["status"] = "unhealthy"

        try:
            if not hasattr(self.event_bus, "emit"):
                raise ValueError("event_bus has no emit method")
        except Exception:
            status["components"]["event_bus"] = "error: event bus check failed"
            status["status"] = "unhealthy"

        # Check Database health (supports static ISession OR dynamic DatabaseManager / Sharding)
        db_checked = False
        try:
            session: ISession = self.container.resolve(ISession)
            try:
                from sqlalchemy import text

                session.execute(text("SELECT 1"))
                status["components"]["database"] = "ok"
                db_checked = True
            except ImportError:
                status["components"]["database"] = "sqlalchemy not installed"
                status["status"] = "unhealthy"
                db_checked = True
            except Exception:
                status["components"]["database"] = "database connection failed"
                status["status"] = "unhealthy"
                db_checked = True
        except Exception:
            pass

        if not db_checked:
            # Check for dynamic database managers or repositories in DI container
            known_keys = (
                list(getattr(self.container, "_bindings", {}).keys())
                + list(getattr(self.container, "_factories", {}).keys())
                + list(getattr(self.container, "_instances", {}).keys())
            )
            for reg_type in known_keys:
                type_name = getattr(reg_type, "__name__", str(reg_type))
                if any(
                    kw in type_name
                    for kw in (
                        "DatabaseManager",
                        "DatabaseConfig",
                        "MarketDataRepository",
                        "Database",
                    )
                ):
                    try:
                        resolved = self.container.resolve(reg_type)
                        if resolved is not None:
                            status["components"]["database"] = "ok"
                            db_checked = True
                            break
                    except Exception:
                        pass

        if not db_checked:
            status["components"]["database"] = "not configured"

        return status
