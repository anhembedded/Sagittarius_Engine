from abc import ABC, abstractmethod
from datetime import datetime, timedelta


class ITrigger(ABC):
    """
    @brief Interface for scheduler triggers to calculate the next run time.
    """

    @abstractmethod
    def get_next_run(self, from_time: datetime) -> datetime:
        """
        @brief Calculates the next execution datetime.
        """
        pass

    def describe(self) -> str:
        """
        @brief A short, human-readable description of this trigger's own
        schedule -- `EPIC-008E`'s Tasks & threads "Limits" jobs table needs
        one real per-job `trigger` column.

        @details Concrete, not abstract, for the same reason as
        `ITaskManager.snapshot()`/`pool_stats()`: a third-party `ITrigger`
        predating this method must not fail to instantiate over it. The
        class name is the honest default; the two triggers this engine ships
        both override it with their own real schedule.
        """
        return self.__class__.__name__


class IntervalTrigger(ITrigger):
    """
    @brief Trigger that fires at fixed intervals.
    """

    def __init__(self, delta: timedelta) -> None:
        self.delta = delta

    def get_next_run(self, from_time: datetime) -> datetime:
        return from_time + self.delta

    def describe(self) -> str:
        return f"every {self.delta}"


class CronTrigger(ITrigger):
    """
    @brief Basic cron-like trigger. Simulates basic minute-level cron matching.
    """

    def __init__(self, cron_expr: str) -> None:
        self.cron_expr = cron_expr

    def get_next_run(self, from_time: datetime) -> datetime:
        # Align to the next minute boundary for basic simulation
        return from_time.replace(second=0, microsecond=0) + timedelta(minutes=1)

    def describe(self) -> str:
        return f"cron {self.cron_expr}"
