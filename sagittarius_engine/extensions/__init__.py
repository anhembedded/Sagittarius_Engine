# Package namespace for Sagittarius extensions.

# CQRS
# Audit
from .audit import AuditExtension, AuditService
from .cqrs import ICommand, IQuery
from .health.health_check_query import HealthCheckDTO, HealthCheckQuery

# Health
from .health.health_module import HealthExtension, HealthUpdatedEvent

# Logger
from .logger.logger_module import LoggerExtension

# Persistence
from .persistence import (
    BaseRepository,
    DatabaseExtension,
    ISession,
    SqlAlchemyExtension,
    SQLAlchemySessionAdapter,
)

# Thread Manager
from .thread_manager.thread_manager_module import ThreadManagerModule

__all__ = [
    # CQRS
    "ICommand",
    "IQuery",
    # Audit
    "AuditExtension",
    "AuditService",
    # Persistence
    "BaseRepository",
    "ISession",
    "SQLAlchemySessionAdapter",
    "DatabaseExtension",
    "SqlAlchemyExtension",
    # Health
    "HealthExtension",
    "HealthCheckQuery",
    "HealthCheckDTO",
    "HealthUpdatedEvent",
    # Logger
    "LoggerExtension",
    # Thread Manager
    "ThreadManagerModule",
]
