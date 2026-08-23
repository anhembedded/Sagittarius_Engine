import time

import pytest

from sagittarius_engine.infrastructure.container.std_container import StdLibContainer
from sagittarius_engine.infrastructure.event_bus.memory_event_bus import MemoryEventBus
from sagittarius_engine.kernel.app import App
from sagittarius_engine.runtime.hosted.hosted_service import IHostedService
from sagittarius_engine.runtime.tasks.background_task import TaskState
from sagittarius_engine.runtime.tasks.cancellation_token import CancellationToken


class DummyHostedService(IHostedService):
    def __init__(self, should_fail: bool = False) -> None:
        self.should_fail = should_fail
        self.started = False
        self.stopped = False

    def start(self, context) -> None:
        if self.should_fail:
            raise RuntimeError("Start failed")
        self.started = True

    def stop(self, context) -> None:
        self.stopped = True


def test_hosted_service_lifecycle_and_rollback():
    container = StdLibContainer()
    event_bus = MemoryEventBus()
    app = App(container, event_bus)

    srv_a = DummyHostedService()
    srv_b = DummyHostedService()

    app.context.hosted_services.register(srv_a)
    app.context.hosted_services.register(srv_b)

    # Listen to events
    events = []
    event_bus.on(
        "runtime.hosted.started",
        lambda e: events.append(("started", e.service_name)),
    )
    event_bus.on(
        "runtime.hosted.stopped",
        lambda e: events.append(("stopped", e.service_name)),
    )

    # Start Hosted Services
    app.context.hosted_services.start()

    assert srv_a.started is True
    assert srv_b.started is True
    assert len(events) == 2
    assert events[0] == ("started", "DummyHostedService")

    # Stop Hosted Services
    app.context.hosted_services.stop()

    assert srv_a.stopped is True
    assert srv_b.stopped is True
    assert len(events) == 4
    assert events[2] == ("stopped", "DummyHostedService")

    # Test Rollback
    app2 = App(StdLibContainer(), MemoryEventBus())
    srv_ok = DummyHostedService()
    srv_err = DummyHostedService(should_fail=True)

    app2.context.hosted_services.register(srv_ok)
    app2.context.hosted_services.register(srv_err)

    with pytest.raises(RuntimeError, match="Start failed"):
        app2.context.hosted_services.start()

    assert srv_ok.started is True
    assert srv_ok.stopped is True  # Stopped during rollback!
    assert srv_err.started is False


def test_cancellation_token():
    token = CancellationToken()
    assert token.is_cancelled() is False

    token.cancel()
    assert token.is_cancelled() is True
    assert token.is_cancellation_requested is True

    # Test wait with short timeout
    token2 = CancellationToken()
    res = token2.wait(timeout=0.01)
    assert res is False  # Timed out

    def cancel_later():
        time.sleep(0.02)
        token2.cancel()

    import threading

    t = threading.Thread(target=cancel_later)
    t.start()
    res2 = token2.wait(timeout=1.0)
    assert res2 is True  # Cancelled!
    t.join()


def test_task_manager_sync_and_async():
    container = StdLibContainer()
    event_bus = MemoryEventBus()
    app = App(container, event_bus)

    app.context.async_runtime.start()

    events = []
    event_bus.on(
        "runtime.tasks.started", lambda e: events.append(("started", e.task_name))
    )
    event_bus.on(
        "runtime.tasks.completed",
        lambda e: events.append(("completed", e.task_name)),
    )
    event_bus.on(
        "runtime.tasks.failed", lambda e: events.append(("failed", e.task_name))
    )

    # 1. Sync Task
    executed = False

    def sync_work():
        nonlocal executed
        executed = True
        return "sync_result"

    task = app.context.tasks.spawn(sync_work, name="SyncTask")
    task.future.result(timeout=1.0)

    assert executed is True
    assert task.status == TaskState.COMPLETED
    assert task.start_time is not None
    assert task.end_time is not None
    assert (task.end_time - task.start_time).total_seconds() >= 0

    # 2. Async Task
    async_executed = False

    async def async_work(token):
        nonlocal async_executed
        async_executed = True
        return "async_result"

    task2 = app.context.tasks.spawn(async_work, name="AsyncTask")
    res = task2.future.result(timeout=1.0)

    assert async_executed is True
    assert res == "async_result"
    assert task2.status == TaskState.COMPLETED
    assert task2.start_time is not None
    assert task2.end_time is not None

    # 3. Failing Task
    def failing_work():
        raise ValueError("Oops")

    task3 = app.context.tasks.spawn(failing_work, name="FailingTask")
    with pytest.raises(Exception):
        task3.future.result(timeout=1.0)

    assert task3.status == TaskState.FAILED
    assert task3.start_time is not None
    assert task3.end_time is not None

    # Wait for events to process
    time.sleep(0.05)
    event_names = [e[0] for e in events]
    assert "started" in event_names
    assert "completed" in event_names
    assert "failed" in event_names

    app.context.async_runtime.stop()
    app.context.tasks.shutdown()


def test_scheduler_fixed_interval():
    container = StdLibContainer()
    event_bus = MemoryEventBus()
    app = App(container, event_bus)

    # Scheduler depends on tasks and async_runtime being started
    app.context.async_runtime.start()

    events = []
    event_bus.on("runtime.scheduler.started", lambda e: events.append("started"))
    event_bus.on("runtime.scheduler.stopped", lambda e: events.append("stopped"))

    app.context.scheduler.start()

    run_count = 0

    def job():
        nonlocal run_count
        run_count += 1

    # Schedule recurring job every 10ms
    app.context.scheduler.every(seconds=0.01).do(job)

    # Let it run a few times
    deadline = time.time() + 0.5
    while run_count < 2 and time.time() < deadline:
        time.sleep(0.01)

    assert run_count >= 2
    assert "started" in events

    # Check error robustness
    failing_runs = 0

    def bad_job():
        nonlocal failing_runs
        failing_runs += 1
        raise RuntimeError("Job failed")

    app.context.scheduler.every(seconds=0.01).do(bad_job)
    deadline = time.time() + 0.5
    while failing_runs < 1 and time.time() < deadline:
        time.sleep(0.01)

    assert failing_runs >= 1
    assert run_count >= 3  # Good job continues running!

    app.context.scheduler.stop()
    app.context.async_runtime.stop()
    app.context.tasks.shutdown()

    assert "stopped" in events


def test_graceful_shutdown():
    container = StdLibContainer()
    event_bus = MemoryEventBus()
    app = App(container, event_bus)

    app.boot()

    # Schedule a recurring job
    job_called = False

    def my_job():
        nonlocal job_called
        job_called = True

    app.context.scheduler.every(seconds=0.01).do(my_job)
    time.sleep(0.02)

    assert app.context.lifecycle.is_booted is True

    # Shutdown
    app.stop()

    assert app.context.lifecycle.is_stopped is True
    assert (
        getattr(app.context.scheduler, "_thread", None) is None
        or not app.context.scheduler._thread.is_alive()
    )
    assert (
        getattr(app.context.async_runtime, "_thread", None) is None
        or not app.context.async_runtime._thread.is_alive()
    )


def test_engine_context_and_task_handle_interfaces():
    """
    [Unit Test - UT]
    Verifies that EngineContext, TaskManager, and BackgroundTask correctly implement
    their abstract interfaces (IEngineContext, ITaskManager, ITaskHandle) for DIP compliance.
    """
    from sagittarius_engine.interfaces import (
        IEngineContext,
        ITaskHandle,
        ITaskManager,
    )

    container = StdLibContainer()
    event_bus = MemoryEventBus()
    app = App(container, event_bus)

    # 1. Verify EngineContext implements IEngineContext interface
    assert isinstance(app.context, IEngineContext)
    assert app.context.container is container
    assert app.context.event_bus is event_bus

    # 2. Verify TaskManager implements ITaskManager interface
    assert isinstance(app.context.tasks, ITaskManager)

    # 3. Verify spawned BackgroundTask implements ITaskHandle interface
    handle = app.context.tasks.spawn(lambda: time.sleep(0.01), name="UnitTestTask")
    assert isinstance(handle, ITaskHandle)
    assert handle.id is not None
    assert handle.name == "UnitTestTask"
    assert handle.token is not None
    assert handle.status in (TaskState.PENDING, TaskState.RUNNING, TaskState.COMPLETED)

    if handle.future:
        handle.future.result()
    app.stop()


def test_hosted_service_integration_with_itask_handle():
    """
    [Integration Test - IT]
    Verifies full integration flow: HostedService receiving IEngineContext,
    subscribing to EventBus events, spawning background task via ITaskManager,
    and returning ITaskHandle with strong-typed .future access.
    """
    from sagittarius_engine.interfaces import IEngineContext, ITaskHandle

    executed = False
    event_received = False

    class IntegrationHostedService(IHostedService):
        def __init__(self) -> None:
            self.task_handle: ITaskHandle | None = None

        def start(self, context: IEngineContext) -> None:
            context.event_bus.on("custom.event", self._on_event)

            def bg_job():
                nonlocal executed
                executed = True

            self.task_handle = context.tasks.spawn(bg_job, name="IntegrationJob")

        def _on_event(self, data):
            nonlocal event_received
            event_received = True

        def stop(self, context: IEngineContext) -> None:
            context.event_bus.off("custom.event", self._on_event)

    container = StdLibContainer()
    event_bus = MemoryEventBus()
    app = App(container, event_bus)

    service = IntegrationHostedService()
    app.context.hosted_services.register(service)

    app.boot()

    # Emit event to test EventBus integration
    event_bus.emit("custom.event", {"msg": "hello"})
    assert event_received is True

    # Check task handle execution
    assert service.task_handle is not None
    if service.task_handle.future:
        service.task_handle.future.result()

    assert executed is True

    app.stop()


def test_background_service_pattern():
    """
    [Unit Test - UT]
    Verifies that BackgroundService automatically spawns background thread,
    manages CancellationToken, and provides graceful shutdown without manual task spawning.
    """
    from sagittarius_engine.runtime import BackgroundService

    loop_count = 0

    class MyLoopWorker(BackgroundService):
        def run(self, token: CancellationToken) -> None:
            nonlocal loop_count
            while not token.is_cancelled():
                loop_count += 1
                time.sleep(0.01)

    container = StdLibContainer()
    event_bus = MemoryEventBus()
    app = App(container, event_bus)

    worker = MyLoopWorker()
    app.context.hosted_services.register(worker)

    app.boot()
    time.sleep(0.03)

    assert worker.task is not None
    assert loop_count >= 1

    app.stop()
    assert worker.token.is_cancelled() is True
