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
