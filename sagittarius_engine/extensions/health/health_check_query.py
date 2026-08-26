import logging
from dataclasses import dataclass
from typing import Any

from sagittarius_engine.extensions.cqrs import IQuery

# Leaf import (TASK-034 req. 3), not `from ...extensions.persistence import
# ISession`: this module needs only the pure-interface `ISession` for DI
# resolution/typing, but importing the `persistence` package itself also
# runs `database_module.py` and `sqlalchemy_session_adapter.py` (each
# guards its own `sqlalchemy` import, so nothing crashes — it is simply
# unnecessary work `health` has no reason to pay for a database check that
# may not even be configured).
from sagittarius_engine.extensions.persistence.i_session import ISession
from sagittarius_engine.interfaces import IContainer, IEventBus

logger = logging.getLogger(__name__)


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
            # No static `ISession` bound. Not an error — an app may register
            # a DatabaseManager instead, which the sweep below looks for.
            # Logged so that a *failing* resolution is still distinguishable
            # from an absent one, which a bare `pass` made impossible.
            logger.debug(
                "No ISession resolved from the container; "
                "falling back to the dynamic database-manager sweep.",
                exc_info=True,
            )

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
                        # This candidate did not resolve; try the next one.
                        # A health check must not fail because one optional
                        # registration is broken, but it must leave a trace
                        # of which one — that is the whole point of a health
                        # check.
                        logger.debug(
                            "Database-ish registration %s failed to resolve "
                            "during the health check; trying the next.",
                            type_name,
                            exc_info=True,
                        )

        if not db_checked:
            status["components"]["database"] = "not configured"

        return status
