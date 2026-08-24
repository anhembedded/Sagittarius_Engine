import logging
import threading
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

from sagittarius_engine.interfaces import IEngineContext
from sagittarius_engine.runtime.scheduler.events import (
    SchedulerStarted,
    SchedulerStopped,
)
from sagittarius_engine.runtime.scheduler.triggers import (
    CronTrigger,
    IntervalTrigger,
    ITrigger,
)


class ScheduledJob:
    """
    @brief Model representing a job scheduled in the scheduler.
    """

    def __init__(
        self, fn: Callable, trigger: ITrigger, max_runs: int | None = None
    ) -> None:
        self.fn = fn
        self.trigger = trigger
        self.max_runs = max_runs
        self.runs = 0
        self.next_run = trigger.get_next_run(datetime.now())


class JobBuilder:
    """
    @brief Fluent builder for configuring and registering scheduled jobs.
    """

    def __init__(
        self,
        scheduler: "Scheduler",
        trigger: ITrigger,
        max_runs: int | None = None,
    ) -> None:
        self.scheduler = scheduler
        self.trigger = trigger
        self.max_runs = max_runs

    def do(self, fn: Callable) -> ScheduledJob:
        """
        @brief Registers the callback function to run when the trigger fires.
        """
        job = ScheduledJob(fn, self.trigger, self.max_runs)
        self.scheduler.add_job(job)
        return job


class Scheduler:
    """
    @brief Lightweight, thread-safe, non-blocking Task Scheduler using Condition variables.
    """

    def __init__(self, context: IEngineContext) -> None:
        self.context = context
        self.jobs: list[ScheduledJob] = []
        self._lock = threading.Lock()
        self._cond = threading.Condition(self._lock)
        self._running = False
        self._thread: threading.Thread | None = None
        self._logger = logging.getLogger("App")

    def _emit(self, event_name: str, event_data: Any) -> None:
        try:
            self.context.event_bus.emit(event_name, event_data)
        except Exception as e:
            self.context.logger.error(f"Failed to emit event: {e}")

    def start(self) -> None:
        """
        @brief Starts the background scheduler thread.
        """
        with self._lock:
            if self._running:
                return
            self._running = True

        self._thread = threading.Thread(
            target=self._run, name="SagittariusScheduler", daemon=True
        )
        self._thread.start()
        self._logger.info("Scheduler started.")
        self._emit(SchedulerStarted.event_name, SchedulerStarted())

    def stop(self) -> None:
        """
        @brief Stops the scheduler thread gracefully.
        """
        with self._lock:
            if not self._running:
                return
            self._running = False
            self._cond.notify_all()

        if self._thread is not None:
            self._thread.join(timeout=5.0)
            self._thread = None
        self._logger.info("Scheduler stopped.")
        self._emit(SchedulerStopped.event_name, SchedulerStopped())

    def add_job(self, job: ScheduledJob) -> None:
        """
        @brief Adds a job and notifies the scheduler thread to wake up.
        """
        with self._lock:
            self.jobs.append(job)
            self._cond.notify_all()

    def every(
        self, seconds: float = 0, minutes: float = 0, hours: float = 0
    ) -> JobBuilder:
        """
        @brief Fluent API to schedule a job recurringly at fixed intervals.
        """
        delta = timedelta(seconds=seconds, minutes=minutes, hours=hours)
        return JobBuilder(self, IntervalTrigger(delta))

    def after(
        self, seconds: float = 0, minutes: float = 0, hours: float = 0
    ) -> JobBuilder:
        """
        @brief Fluent API to schedule a single delayed one-off job.
        """
        delta = timedelta(seconds=seconds, minutes=minutes, hours=hours)
        return JobBuilder(self, IntervalTrigger(delta), max_runs=1)

    def cron(self, cron_expr: str) -> JobBuilder:
        """
        @brief Fluent API to schedule a job using a basic cron expression.
        """
        return JobBuilder(self, CronTrigger(cron_expr))

    def _run(self) -> None:
        while True:
            with self._lock:
                if not self._running:
                    break

                now = datetime.now()
                jobs_to_run = []
                active_jobs = []
                next_wakeup = now + timedelta(seconds=1.0)

                for job in self.jobs:
                    if job.next_run <= now:
                        jobs_to_run.append(job)
                    else:
                        active_jobs.append(job)
                        if job.next_run < next_wakeup:
                            next_wakeup = job.next_run
                self.jobs = active_jobs

                # Execute ready jobs
                for job in jobs_to_run:
                    try:
                        self.context.tasks.spawn(
                            job.fn, name=f"ScheduledJob_{job.fn.__name__}"
                        )
                    except Exception as e:
                        self._logger.error(f"Failed to spawn scheduled job: {e}")

                    job.runs += 1
                    if job.max_runs is None or job.runs < job.max_runs:
                        job.next_run = job.trigger.get_next_run(now)
                        self.jobs.append(job)
                        if job.next_run < next_wakeup:
                            next_wakeup = job.next_run

                # Sleep time calculation
                sleep_time = (next_wakeup - datetime.now()).total_seconds()
                if sleep_time <= 0:
                    sleep_time = 0.01

                # Block on condition (releasing the lock)
                self._cond.wait(sleep_time)
