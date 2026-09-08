import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock

from sagittarius_engine.interfaces import IEngineContext
from sagittarius_engine.runtime.scheduler.scheduler import ScheduledJob, Scheduler
from sagittarius_engine.runtime.scheduler.triggers import IntervalTrigger


class TestScheduler(unittest.TestCase):
    def test_scheduler_initialization(self):
        # Arrange
        mock_context = MagicMock(spec=IEngineContext)

        # Act
        scheduler = Scheduler(context=mock_context)

        # Assert
        self.assertEqual(scheduler.context, mock_context)
        self.assertFalse(scheduler._running)
        self.assertEqual(len(scheduler.jobs), 0)

    def test_add_job(self):
        # Arrange
        mock_context = MagicMock(spec=IEngineContext)
        scheduler = Scheduler(context=mock_context)
        dummy_trigger = IntervalTrigger(timedelta(seconds=1))
        job = ScheduledJob(lambda: None, dummy_trigger)

        # Act
        scheduler.add_job(job)

        # Assert
        self.assertEqual(len(scheduler.jobs), 1)
        self.assertEqual(scheduler.jobs[0], job)

    def test_every_builder(self):
        # Arrange
        mock_context = MagicMock(spec=IEngineContext)
        scheduler = Scheduler(context=mock_context)

        def dummy_fn():
            return None

        # Act
        job = scheduler.every(seconds=5).do(dummy_fn)

        # Assert
        self.assertEqual(len(scheduler.jobs), 1)
        self.assertEqual(scheduler.jobs[0], job)
        self.assertEqual(job.fn, dummy_fn)
        self.assertIsInstance(job.trigger, IntervalTrigger)
        self.assertEqual(job.trigger.delta, timedelta(seconds=5))

    def test_after_builder(self):
        # Arrange
        mock_context = MagicMock(spec=IEngineContext)
        scheduler = Scheduler(context=mock_context)

        def dummy_fn():
            return None

        # Act
        job = scheduler.after(minutes=2).do(dummy_fn)

        # Assert
        self.assertEqual(len(scheduler.jobs), 1)
        self.assertEqual(scheduler.jobs[0], job)
        self.assertEqual(job.fn, dummy_fn)
        self.assertEqual(job.max_runs, 1)

    def test_cron_builder(self):
        # Arrange
        mock_context = MagicMock(spec=IEngineContext)
        scheduler = Scheduler(context=mock_context)

        def dummy_fn():
            return None

        # Act
        job = scheduler.cron("* * * * *").do(dummy_fn)

        # Assert
        self.assertEqual(len(scheduler.jobs), 1)
        self.assertEqual(scheduler.jobs[0], job)
        self.assertEqual(job.fn, dummy_fn)

    def test_scheduler_start_stop(self):
        # Arrange
        mock_context = MagicMock(spec=IEngineContext)
        mock_context.event_bus = MagicMock()
        scheduler = Scheduler(context=mock_context)

        # Act
        scheduler.start()
        is_running = scheduler._running
        thread = scheduler._thread

        # We stop it so it doesn't run forever in background
        scheduler.stop()
        is_running_after = scheduler._running

        # Assert
        self.assertTrue(is_running)
        self.assertIsNotNone(thread)
        self.assertFalse(is_running_after)

        # Verify event emission
        self.assertEqual(mock_context.event_bus.emit.call_count, 2)

    def test_run_executes_ready_jobs(self):
        # Arrange
        mock_context = MagicMock(spec=IEngineContext)
        mock_context.tasks = MagicMock()
        scheduler = Scheduler(context=mock_context)

        dummy_fn = MagicMock(__name__="dummy_fn")
        trigger = IntervalTrigger(timedelta(milliseconds=1))
        job = ScheduledJob(dummy_fn, trigger, max_runs=1)
        # Make the job immediately ready
        job.next_run = datetime.now() - timedelta(seconds=1)

        scheduler.add_job(job)

        # Start and stop quickly
        scheduler.start()
        # let thread run a little
        import time

        time.sleep(0.05)
        scheduler.stop()

        # Assert
        mock_context.tasks.spawn.assert_called_once()

    def test_run_drops_a_dead_job_without_crashing_the_thread(self):
        """`Scheduler._run()` used to crash comparing `None <= datetime`
        the moment any job's `next_run` was `None` -- found via `EPIC-007D`
        deliberately producing that state (the same condition
        `WiringInspector`'s D3 check looks for). The whole background thread
        died silently on the unhandled exception, with nothing in the
        scheduler's own state showing it. This proves it no longer does."""
        mock_context = MagicMock(spec=IEngineContext)
        mock_context.tasks = MagicMock()
        scheduler = Scheduler(context=mock_context)

        dead_fn = MagicMock(__name__="dead_fn")
        dead_job = ScheduledJob(dead_fn, IntervalTrigger(timedelta(hours=1)))
        dead_job.next_run = None
        scheduler.add_job(dead_job)

        scheduler.start()
        import time

        time.sleep(0.05)

        # If _run() had raised, the thread would already be dead here --
        # before stop() was ever called to end it deliberately.
        self.assertTrue(scheduler._thread.is_alive())

        scheduler.stop()

        mock_context.tasks.spawn.assert_not_called()
        self.assertNotIn(dead_job, scheduler.jobs)

    def test_start_stop_idempotent(self):
        # Arrange
        mock_context = MagicMock(spec=IEngineContext)
        scheduler = Scheduler(context=mock_context)

        # Act
        scheduler.start()
        thread = scheduler._thread
        scheduler.start()  # Should return immediately

        self.assertEqual(scheduler._thread, thread)

        scheduler.stop()
        scheduler.stop()  # Should return immediately
        self.assertFalse(scheduler._running)
