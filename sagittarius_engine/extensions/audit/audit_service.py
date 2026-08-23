import logging
import platform
from collections import deque
from datetime import UTC, datetime
from typing import Any, Protocol

from sagittarius_engine.extensions.health.health_check_query import (
    HealthCheckDTO,
    HealthCheckQuery,
)
from sagittarius_engine.interfaces.i_container import IContainer

from .infra.websocket_broadcaster import WebsocketBroadcaster


class IAuditContext(Protocol):
    @property
    def container(self) -> IContainer: ...
    @property
    def tasks(self) -> Any: ...


try:
    import psutil

    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False


class AuditService:
    """
    @brief Collects telemetry and metrics from the EngineContext for the Audit Dashboard.
    """

    def __init__(self, context: IAuditContext, port: int = 9999) -> None:
        self.context: IAuditContext = context
        self.port: int = port
        self.start_time: datetime = datetime.now(UTC)
        self._logger: logging.Logger = logging.getLogger("AuditService")
        self.recent_events: deque = deque(maxlen=100)

        # Initialize the broadcaster
        self.broadcaster = WebsocketBroadcaster(port=self.port)
        self.broadcaster.on_new_client_callback = self._get_full_state

        self._subscribe_events()

    def _get_full_state(self) -> dict[str, Any]:
        return {
            "uptime": self.get_uptime_seconds(),
            "environment": self.get_environment_info(),
            "health": self.get_system_health(),
            "tasks": self.get_active_tasks(),
            "extensions": self.get_loaded_extensions(),
            "services": self.get_running_hosted_services(),
            "config_bus": self.get_config_and_event_bus_info(),
            "pipeline": self.get_middleware_pipeline(),
            "scheduler": self.get_scheduler_jobs(),
            "recent_events": list(self.recent_events)[-10:],
        }

    def _subscribe_events(self) -> None:
        try:
            eb = getattr(self.context, "event_bus", None)
            if not eb or not hasattr(eb, "on"):
                return

            def on_state_changed(event: Any) -> None:
                # Add to recent events
                event_name = event.__class__.__name__
                if isinstance(event, str):
                    event_name = event
                timestamp = datetime.now().strftime("%H:%M:%S")
                self.recent_events.append(f"[{timestamp}] {event_name}")

                # Push state update
                state = self._get_full_state()
                self.broadcaster.broadcast("state_update", state)

            from sagittarius_engine.runtime.tasks.events import (
                TaskCompleted,
                TaskFailed,
                TaskStarted,
            )

            # Subscribe to specific important events using their class (EventBus handles mapping)
            eb.on(TaskStarted, on_state_changed)
            eb.on(TaskCompleted, on_state_changed)
            eb.on(TaskFailed, on_state_changed)

            # Keep string fallbacks for events that might not have classes available in all contexts
            eb.on("ExtensionLoaded", on_state_changed)
            eb.on("SystemStateChangedEvent", on_state_changed)

            # Application specific events (for Student Management Demo)
            eb.on("student.added", on_state_changed)
            eb.on("student.updated", on_state_changed)
            eb.on("student.deleted", on_state_changed)
            eb.on("report.completed", on_state_changed)

        except Exception as e:
            self._logger.error(f"Failed to subscribe to events: {e}")

    def start_server(self) -> None:
        """Starts the background telemetry socket server."""
        self.broadcaster.start()

    def stop_server(self) -> None:
        """Stops the background socket server."""
        self.broadcaster.stop()

    def get_uptime_seconds(self) -> float:
        """
        @brief Returns engine uptime in seconds.
        """
        return (datetime.now(UTC) - self.start_time).total_seconds()

    def get_system_health(self) -> dict[str, Any]:
        """
        @brief Dispatches HealthCheckQuery to get system health.
        """
        # Since IEngineContext doesn't expose dispatcher directly, we cast/duck-type
        try:
            app = getattr(self.context, "app", None)
            if app and hasattr(app, "dispatch"):
                return app.dispatch(HealthCheckQuery, HealthCheckDTO())

            # Fallback if dispatcher is accessible directly
            dispatcher = getattr(self.context, "dispatcher", None)
            if dispatcher:
                return dispatcher.dispatch(HealthCheckQuery, HealthCheckDTO())

        except Exception as e:
            # SECURITY: Do not expose raw exception strings to prevent information disclosure.
            self._logger.error(f"Failed to get system health: {e}")
            return {
                "status": "error",
                "message": "An internal error occurred",
                "components": {},
            }

        return {"status": "unknown"}

    def get_active_tasks(self) -> list[dict[str, Any]]:
        """
        @brief Returns a list of active background tasks.
        """
        tasks_data = []
        try:
            # ITaskManager stores tasks in a .tasks dictionary
            tasks_dict = getattr(self.context.tasks, "tasks", {})
            for task_id, task in tasks_dict.items():
                runtime = "N/A"
                if hasattr(task, "start_time") and task.start_time:
                    end = task.end_time or datetime.now(UTC)
                    runtime = f"{(end - task.start_time).total_seconds():.1f}s"

                tasks_data.append(
                    {
                        "id": task_id[:8],
                        "name": getattr(task, "name", "Unknown"),
                        "status": task.status.value
                        if hasattr(task.status, "value")
                        else str(task.status),
                        "progress": getattr(task, "progress", 0.0),
                        "runtime": runtime,
                    }
                )
        except Exception as e:
            self._logger.error(f"Audit service error: {e}")
        return tasks_data

    def get_loaded_extensions(self) -> list[dict[str, Any]]:
        """
        @brief Returns a list of loaded extensions.
        """
        extensions_data = []
        try:
            ext_manager = getattr(self.context, "extension_manager", None)
            if ext_manager:
                for ext in ext_manager.registered_extensions:
                    desc = getattr(ext, "descriptor", None)
                    if desc:
                        extensions_data.append(
                            {
                                "name": desc.name,
                                "version": desc.version,
                                "enabled": desc.enabled,
                            }
                        )
                    else:
                        extensions_data.append(
                            {
                                "name": ext.__class__.__name__,
                                "version": "unknown",
                                "enabled": True,
                            }
                        )
        except Exception as e:
            self._logger.error(f"Audit service error: {e}")
        return extensions_data

    def get_running_hosted_services(self) -> list[str]:
        """
        @brief Returns a list of running hosted services.
        """
        services_data = []
        try:
            hs_manager = getattr(self.context, "hosted_services", None)
            if hs_manager:
                for srv in hs_manager.started_services:
                    services_data.append(srv.__class__.__name__)
        except Exception as e:
            self._logger.error(f"Audit service error: {e}")
        return services_data

    def get_environment_info(self) -> dict[str, str]:
        """
        @brief Returns basic OS, Python environment info, and System Metrics.
        """
        env = {
            "os": platform.system(),
            "os_release": platform.release(),
            "python_version": platform.python_version(),
            "cpu_percent": "N/A",
            "ram_mb": "N/A",
        }

        if PSUTIL_AVAILABLE:
            try:
                process = psutil.Process()
                env["cpu_percent"] = f"{process.cpu_percent(interval=None):.1f}%"
                env["ram_mb"] = f"{process.memory_info().rss / 1024 / 1024:.1f} MB"
            except Exception as e:
                self._logger.error(f"Audit service error: {e}")

        return env

    def get_config_and_event_bus_info(self) -> dict[str, Any]:
        """
        @brief Returns high-level config keys and event bus subscriptions.
        """
        info: dict[str, Any] = {"event_bus_handlers": {}, "config_keys": []}
        try:
            eb = getattr(self.context, "event_bus", None)
            if eb and hasattr(eb, "_handlers"):
                for event_name, handlers in eb._handlers.items():
                    info["event_bus_handlers"][event_name] = len(handlers)

            from sagittarius_engine.interfaces import IConfig

            config = self.context.container.resolve(IConfig)
            if config and hasattr(config, "_config"):
                info["config_keys"] = list(config._config.keys())
        except Exception as e:
            self._logger.error(f"Audit service error: {e}")
        return info

    def get_middleware_pipeline(self) -> list[str]:
        """Returns the list of loaded middlewares."""
        try:
            pipeline = getattr(getattr(self.context, "app", None), "pipeline", None)
            if pipeline and hasattr(pipeline, "middlewares"):
                return [m.__class__.__name__ for m in pipeline.middlewares]
        except Exception as e:
            self._logger.error(f"Audit service error: {e}")
        return []

    def get_scheduler_jobs(self) -> list[dict[str, str]]:
        """Returns scheduled jobs and next run time."""
        jobs_data = []
        try:
            scheduler = getattr(self.context, "scheduler", None)
            if scheduler and hasattr(scheduler, "jobs"):
                for job in scheduler.jobs:
                    job_name = getattr(job.job_func, "__name__", "anonymous_job")
                    next_run = (
                        job.next_run.strftime("%H:%M:%S")
                        if hasattr(job, "next_run") and job.next_run
                        else "Unknown"
                    )
                    jobs_data.append(
                        {
                            "name": job_name,
                            "interval": f"{job.interval}s",
                            "next_run": next_run,
                        }
                    )
        except Exception as e:
            self._logger.error(f"Audit service error: {e}")
        return jobs_data

    def get_full_config(self) -> dict[str, Any]:
        """Returns the full configuration dictionary."""
        config = getattr(self.context, "config", None)
        if not config:
            return {}
        if hasattr(config, "_cache"):
            return getattr(config, "_cache", {})
        if hasattr(config, "store"):
            return getattr(config, "store", {})
        if hasattr(config, "_store"):
            return getattr(config, "_store", {})
        return {"error": "Unable to extract config dictionary from implementation"}

    def get_all_tasks_details(self) -> list[dict[str, Any]]:
        """Returns detailed information of all background tasks including errors."""
        tasks = []
        try:
            tm = getattr(self.context, "tasks", None)
            if tm and hasattr(tm, "tasks"):
                tasks_dict = getattr(tm, "tasks", {})
                if isinstance(tasks_dict, dict):
                    task_items = tasks_dict.values()
                else:
                    task_items = tasks_dict

                for t in task_items:
                    error_msg = None
                    if hasattr(t, "error") and t.error:
                        error_msg = str(t.error)
                    elif hasattr(t, "exception") and t.exception:
                        error_msg = str(t.exception)

                    runtime = "N/A"
                    if hasattr(t, "start_time") and t.start_time:
                        end = getattr(t, "end_time", None) or datetime.now(UTC)
                        runtime = f"{(end - t.start_time).total_seconds():.1f}s"

                    tasks.append(
                        {
                            "id": getattr(t, "id", getattr(t, "task_id", "Unknown")),
                            "name": getattr(t, "name", "Unknown"),
                            "status": t.status.value
                            if hasattr(t, "status") and hasattr(t.status, "value")
                            else str(getattr(t, "status", "Unknown")),
                            "progress": getattr(t, "progress", 0.0),
                            "runtime": runtime,
                            "error": error_msg,
                        }
                    )
        except Exception as e:
            self._logger.error(f"Audit service error: {e}")
        return tasks
