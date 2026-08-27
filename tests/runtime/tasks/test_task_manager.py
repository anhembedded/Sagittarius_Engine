import time
from unittest.mock import Mock

from sagittarius_engine.runtime.tasks.background_task import TaskState
from sagittarius_engine.runtime.tasks.events import TaskProgressUpdated
from sagittarius_engine.runtime.tasks.task_manager import TaskManager


class MockContext:
    def __init__(self):
        self.event_bus = Mock()
        self.async_runtime = Mock()
        # EPIC-005B added `recorder` to the engine context, and the task
        # manager reads it to decide whether to open a task-run span. `None`
        # here is what "tracing off" means -- the same value a real context
        # carries by default.
        self.recorder = None


def test_task_manager_spawn_sync_task():
    context = MockContext()
    manager = TaskManager(context)

    def dummy_task(token=None):
        time.sleep(0.1)
        return "done"

    task = manager.spawn(dummy_task, name="SyncTest")
    assert task.status == TaskState.RUNNING
    assert task.name == "SyncTest"

    # Wait for completion
    task.future.result(timeout=2.0)

    # Needs a slight delay for the wrapper to update state
    time.sleep(0.1)
    assert task.status == TaskState.COMPLETED


def test_task_manager_progress_event_emission():
    context = MockContext()
    manager = TaskManager(context)

    def progress_task(token=None):
        pass  # We will just manually trigger update_progress

    task = manager.spawn(progress_task, name="ProgressTask")

    # Manually trigger progress
    task.update_progress(75.5, "Almost there")

    # Verify event_bus.emit was called with TaskProgressUpdated
    emit_calls = context.event_bus.emit.call_args_list
    progress_calls = [
        call for call in emit_calls if call.args[0] == "runtime.tasks.progress"
    ]

    assert len(progress_calls) >= 1
    event_obj = progress_calls[0].args[1]
    assert isinstance(event_obj, TaskProgressUpdated)
    assert event_obj.task_id == task.id
    assert event_obj.progress == 75.5
    assert event_obj.message == "Almost there"


def test_task_manager_cleanup():
    from sagittarius_engine.runtime.tasks.background_task import (
        BackgroundTask,
        TaskState,
    )

    context = MockContext()
    manager = TaskManager(context)

    # Add 200 completed tasks
    for i in range(200):
        t = BackgroundTask(f"completed_task_{i}")
        t.status = TaskState.COMPLETED
        manager.tasks[t.id] = t
        manager._finished_task_ids.append(t.id)

    # Add 5 active tasks
    for i in range(5):
        t = BackgroundTask(f"active_task_{i}")
        t.status = TaskState.RUNNING
        manager.tasks[t.id] = t

    manager._cleanup_old_tasks()

    assert len(manager._finished_task_ids) == 50
    assert len(manager.tasks) == 55


def test_task_manager_cleanup_respects_configured_max_retained_tasks():
    """@brief TASK-017 issue 5 regression: the finished-task retention limit
    must be configurable via IConfig instead of a hardcoded 50."""
    from sagittarius_engine.interfaces.i_config import IConfig
    from sagittarius_engine.runtime.tasks.background_task import (
        BackgroundTask,
        TaskState,
    )

    class FakeConfig(IConfig):
        def __init__(self, values):
            self._values = values

        def get(self, key, default=None, cast=None):
            return self._values.get(key, default)

        def get_all(self):
            return dict(self._values)

        def set(self, key, value):
            self._values[key] = value

    class ConfiguredContext(MockContext):
        def __init__(self, max_retained: int):
            super().__init__()
            self.container = Mock()
            self.container.resolve.return_value = FakeConfig(
                {"task_manager.max_retained_tasks": max_retained}
            )

    context = ConfiguredContext(max_retained=5)
    manager = TaskManager(context)

    for i in range(20):
        t = BackgroundTask(f"completed_task_{i}")
        t.status = TaskState.COMPLETED
        manager.tasks[t.id] = t
        manager._finished_task_ids.append(t.id)

    manager._cleanup_old_tasks()

    assert len(manager._finished_task_ids) == 5
    assert len(manager.tasks) == 5


def test_task_manager_get_active_tasks():
    from sagittarius_engine.runtime.tasks.background_task import (
        BackgroundTask,
        TaskState,
    )

    context = MockContext()
    manager = TaskManager(context)

    t1 = BackgroundTask("running_task")
    t1.status = TaskState.RUNNING
    manager.tasks[t1.id] = t1

    t2 = BackgroundTask("pending_task")
    t2.status = TaskState.PENDING
    manager.tasks[t2.id] = t2

    t3 = BackgroundTask("completed_task")
    t3.status = TaskState.COMPLETED
    manager.tasks[t3.id] = t3

    active = manager.get_active_tasks()
    assert len(active) == 2
    active_ids = {t.id for t in active}
    assert active_ids == {t1.id, t2.id}


def test_task_manager_shutdown_logs_warning_when_active_tasks(caplog):
    import logging

    from sagittarius_engine.runtime.tasks.background_task import (
        BackgroundTask,
        TaskState,
    )

    context = MockContext()
    manager = TaskManager(context)

    t1 = BackgroundTask("active_task_1")
    t1.status = TaskState.RUNNING
    manager.tasks[t1.id] = t1

    with caplog.at_level(logging.WARNING):
        manager.shutdown(timeout=0.1)

    assert "TaskManager shutting down with 1 active tasks still running" in caplog.text
    assert "active_task_1" in caplog.text


# --------------------------------------------------------- EPIC-007B: snapshot()


def test_snapshot_includes_finished_tasks_get_active_tasks_omits():
    """`get_active_tasks()` only ever reports RUNNING/PENDING — this is what makes
    "task registered / running / not running" answerable for retained history too."""
    from sagittarius_engine.runtime.tasks.background_task import (
        BackgroundTask,
        TaskState,
    )

    context = MockContext()
    manager = TaskManager(context)

    t1 = BackgroundTask("completed_task")
    t1.status = TaskState.COMPLETED
    manager.tasks[t1.id] = t1

    t2 = BackgroundTask("failed_task")
    t2.status = TaskState.FAILED
    t2.error = ValueError("boom")
    manager.tasks[t2.id] = t2

    snapshot = manager.snapshot()

    assert len(snapshot) == 2
    assert manager.get_active_tasks() == []

    by_name = {s.name: s for s in snapshot}
    assert by_name["completed_task"].state == TaskState.COMPLETED
    assert by_name["completed_task"].error is None
    assert by_name["failed_task"].state == TaskState.FAILED
    assert by_name["failed_task"].error == "boom"


def test_snapshot_error_field_is_a_string_not_the_exception_object():
    """A snapshot is a plain value that may cross a thread or a wire — the raw
    exception (and its traceback) stays in the log line the failure already
    produced, not in a value object handed to arbitrary callers."""
    from sagittarius_engine.runtime.tasks.background_task import (
        BackgroundTask,
        TaskState,
    )

    context = MockContext()
    manager = TaskManager(context)

    t = BackgroundTask("boom_task")
    t.status = TaskState.FAILED
    t.error = RuntimeError("disk full")
    manager.tasks[t.id] = t

    (entry,) = manager.snapshot()
    assert entry.error == "disk full"
    assert isinstance(entry.error, str)


def test_snapshot_reports_critical_not_a_fabricated_thread_name():
    """No `thread` field: which OS thread ran a submission is not tracked
    anywhere in this engine, and `critical` — which pool it ran in — is the
    honest substitute, not a guess dressed up as a thread name."""
    from sagittarius_engine.runtime.tasks.background_task import (
        BackgroundTask,
        TaskState,
    )

    context = MockContext()
    manager = TaskManager(context)

    t = BackgroundTask("critical_task", critical=True)
    t.status = TaskState.RUNNING
    manager.tasks[t.id] = t

    (entry,) = manager.snapshot()
    assert entry.critical is True
    assert not hasattr(entry, "thread")


def test_snapshot_of_an_empty_manager_is_an_empty_tuple():
    context = MockContext()
    manager = TaskManager(context)
    assert manager.snapshot() == ()


# ------------------------------------------------------- EPIC-007B: pool_stats()


def test_pool_stats_reports_both_named_pools_even_when_idle():
    context = MockContext()
    manager = TaskManager(context)

    stats = manager.pool_stats()
    names = {s.name for s in stats}
    assert names == {"background", "critical"}
    for s in stats:
        assert s.in_flight == 0
        assert s.queue_depth == 0
        assert s.submitted == 0
        assert s.completed == 0
    by_name = {s.name: s for s in stats}
    assert by_name["background"].max_workers == TaskManager._BACKGROUND_MAX_WORKERS
    assert by_name["critical"].max_workers == TaskManager._CRITICAL_MAX_WORKERS


def test_pool_stats_counts_submitted_and_completed_sync_tasks():
    context = MockContext()
    manager = TaskManager(context)

    def quick(token=None):
        return "ok"

    task = manager.spawn(quick, name="quick")
    task.future.result(timeout=2.0)
    # add_done_callback fires as part of the future's own completion --
    # give it a moment to actually run before asserting on the counters.
    for _ in range(50):
        stats = {s.name: s for s in manager.pool_stats()}
        if stats["background"].completed >= 1:
            break
        time.sleep(0.02)

    stats = {s.name: s for s in manager.pool_stats()}
    assert stats["background"].submitted == 1
    assert stats["background"].completed == 1
    assert stats["background"].in_flight == 0


def test_pool_stats_queue_depth_is_derived_not_read_from_a_private_queue(monkeypatch):
    """Every submission beyond max_workers must be waiting -- there is no
    third state a ThreadPoolExecutor future can be in.

    `_BACKGROUND_MAX_WORKERS` is read once, in `__init__`, to size the real
    `ThreadPoolExecutor` -- patching it on an already-constructed instance
    would not shrink that executor. `monkeypatch` sets it on the *class*
    before construction instead, so this test exercises a genuinely
    one-worker pool rather than asserting a formula against a pool that
    still has 20 free threads to run both tasks concurrently in.
    """
    import threading

    monkeypatch.setattr(TaskManager, "_BACKGROUND_MAX_WORKERS", 1)
    context = MockContext()
    manager = TaskManager(context)
    release = threading.Event()

    def blocker(token=None):
        release.wait(timeout=2.0)

    def queued(token=None):
        pass

    blocking_task = manager.spawn(blocker, name="blocker")
    for _ in range(50):
        if blocking_task.status.name == "RUNNING":
            break
        time.sleep(0.01)

    manager.spawn(queued, name="queued")
    time.sleep(0.05)

    stats = {s.name: s for s in manager.pool_stats()}
    assert stats["background"].in_flight == 2
    assert stats["background"].max_workers == 1
    assert stats["background"].queue_depth == 1

    release.set()


# --------------------------------------- EPIC-007B: cancel_all() deadlock regression


def test_cancel_all_does_not_deadlock_on_a_queued_not_yet_started_task(monkeypatch):
    """Regression: cancelling a future that has not started yet invokes its
    done callbacks synchronously, on the calling thread. `cancel_all()` used
    to run `.cancel()` while still holding `self._lock`, and the new
    `pool_stats()` done-callback (EPIC-007B) also acquires that lock --
    self-deadlock on a non-reentrant `Lock`, found while adding it. This test
    must complete promptly; a regression here hangs the whole test process
    rather than failing an assertion, which is exactly what happened once.

    A one-worker pool (patched on the class before construction -- see
    `test_pool_stats_queue_depth_is_derived_not_read_from_a_private_queue`)
    is what forces the second task to be genuinely queued, and therefore
    genuinely cancellable, rather than already running when `cancel_all()`
    reaches it.
    """
    import threading

    monkeypatch.setattr(TaskManager, "_BACKGROUND_MAX_WORKERS", 1)
    context = MockContext()
    manager = TaskManager(context)
    release = threading.Event()

    def blocker(token=None):
        release.wait(timeout=2.0)

    def never_runs(token=None):
        raise AssertionError("must not run: cancelled before it started")

    blocking_task = manager.spawn(blocker, name="blocker")
    for _ in range(50):
        if blocking_task.status.name == "RUNNING":
            break
        time.sleep(0.01)

    manager.spawn(never_runs, name="queued")

    finished = threading.Event()

    def do_cancel_all():
        manager.cancel_all()
        finished.set()

    canceller = threading.Thread(target=do_cancel_all, daemon=True)
    canceller.start()
    canceller.join(timeout=2.0)

    assert finished.is_set(), "cancel_all() deadlocked"
    release.set()


def test_itaskmanager_snapshot_and_pool_stats_default_to_empty_tuples():
    """A third-party ITaskManager written before these methods existed must
    not fail to instantiate over them, and their inherited default must read
    as "not tracked" -- an empty tuple, never a fabricated task or pool."""
    from sagittarius_engine.interfaces.i_task_manager import ITaskManager

    class MinimalTaskManager(ITaskManager):
        def spawn(self, callable_or_coro, name=None, token=None, critical=False):
            raise NotImplementedError

        def get_active_tasks(self):
            return []

        def shutdown(self, timeout: float = 5.0) -> None:
            pass

    manager = MinimalTaskManager()
    assert manager.snapshot() == ()
    assert manager.pool_stats() == ()


def test_snapshot_is_safe_under_concurrent_spawn():
    """The lock in snapshot() bounds `self.tasks` from changing size mid-read
    -- without it, `list(self.tasks.values())` racing a concurrent `spawn()`
    inserting into the same dict can raise `RuntimeError: dictionary changed
    size during iteration`. Many spawns on other threads, many snapshot()
    calls on this one, for real wall-clock time, not one lucky interleaving.
    """
    import threading

    context = MockContext()
    manager = TaskManager(context)
    stop = threading.Event()
    errors: list[Exception] = []

    def spawn_loop():
        i = 0
        while not stop.is_set():
            try:
                manager.spawn(lambda token=None: None, name=f"t{i}")
            except Exception as e:  # pragma: no cover - failure path only
                errors.append(e)
            i += 1

    spawners = [threading.Thread(target=spawn_loop) for _ in range(4)]
    for t in spawners:
        t.start()

    deadline = time.monotonic() + 0.5
    while time.monotonic() < deadline:
        try:
            manager.snapshot()
        except Exception as e:  # pragma: no cover - failure path only
            errors.append(e)

    stop.set()
    for t in spawners:
        t.join(timeout=2.0)

    assert errors == []
