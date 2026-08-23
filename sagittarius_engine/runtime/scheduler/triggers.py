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


class IntervalTrigger(ITrigger):
    """
    @brief Trigger that fires at fixed intervals.
    """

    def __init__(self, delta: timedelta) -> None:
        self.delta = delta

    def get_next_run(self, from_time: datetime) -> datetime:
        return from_time + self.delta


class CronTrigger(ITrigger):
    """
    @brief Basic cron-like trigger. Simulates basic minute-level cron matching.
    """

    def __init__(self, cron_expr: str) -> None:
        self.cron_expr = cron_expr

    def get_next_run(self, from_time: datetime) -> datetime:
        # Align to the next minute boundary for basic simulation
        return from_time.replace(second=0, microsecond=0) + timedelta(minutes=1)
