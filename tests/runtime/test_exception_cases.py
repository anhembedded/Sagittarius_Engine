import time
from unittest.mock import MagicMock

import pytest

from sagittarius_engine.infrastructure.container.std_container import StdLibContainer
from sagittarius_engine.infrastructure.event_bus.memory_event_bus import MemoryEventBus
from sagittarius_engine.infrastructure.event_bus.resilient_event_bus import (
    ResilientEventBus,
)
from sagittarius_engine.infrastructure.event_bus.thread_pool_event_bus import (
    ThreadPoolEventBus,
)
from sagittarius_engine.interfaces.i_extension import ExtensionDescriptor, IExtension
from sagittarius_engine.kernel.app import App
from sagittarius_engine.runtime.hosted.hosted_service import IHostedService
from sagittarius_engine.runtime.hosted.hosted_service_manager import (
    HostedServiceManager,
)
from sagittarius_engine.runtime.scheduler.scheduler import JobBuilder
from sagittarius_engine.runtime.scheduler.triggers import IntervalTrigger
from sagittarius_engine.runtime.tasks.background_task import TaskState

# ==========================================================
# 1. KERNEL / App.stop() Exception Cases
# ==========================================================


def test_app_stop__scheduler_raises__other_subsystems_still_stop():
    container = StdLibContainer()
    event_bus = MemoryEventBus()
    app = App(container, event_bus)
    app.boot()

    # Mock scheduler to raise on stop
    app.context.scheduler.stop = MagicMock(side_effect=RuntimeError("Scheduler Error"))
    # Mock hosted_services to track stop call
    app.context.hosted_services.stop = MagicMock()

    app.stop()

    assert app.context.hosted_services.stop.called is True
    assert app.context.lifecycle.is_stopped is True


def test_app_stop__extension_dispose_fails__no_resource_leak():
    class BrokenDisposeExtension(IExtension):
        @property
        def descriptor(self) -> ExtensionDescriptor:
            return ExtensionDescriptor(name="BrokenDispose")

        def register(self, c):
            pass

        def boot(self, c):
            pass

        def initialize(self, c):
            pass

        def start(self, c):
            pass

        def stop(self, c):
            pass

        def shutdown(self, c):
            pass

        def dispose(self, c):
            raise RuntimeError("Dispose Boom")

    container = StdLibContainer()
    event_bus = MemoryEventBus()
    app = App(container, event_bus)
    app.use(BrokenDisposeExtension())
    app.boot()

    # App stop should complete gracefully without raising
    app.stop()
    assert app.context.lifecycle.is_stopped is True


def test_app_stop__multiple_failures__logs_all_errors():
    container = StdLibContainer()
    event_bus = MemoryEventBus()
    app = App(container, event_bus)
    app.boot()

    app.context.scheduler.stop = MagicMock(side_effect=RuntimeError("Err1"))
    app.context.hosted_services.stop = MagicMock(side_effect=RuntimeError("Err2"))
    app.context.tasks.shutdown = MagicMock(side_effect=RuntimeError("Err3"))

    app.stop()
    assert app.context.lifecycle.is_stopped is True


def test_app_stop__already_stopped__idempotent_safe():
    container = StdLibContainer()
    event_bus = MemoryEventBus()
    app = App(container, event_bus)
    app.boot()

    app.stop()
    app.stop()
    assert app.context.lifecycle.is_stopped is True


# ==========================================================
# 2. KERNEL / Bootstrap.boot() Rollback Exception Cases
# ==========================================================


def test_bootstrap_boot__extension_init_fails__rollback_cleans_initialized():
    history = []

    class ExtNormal(IExtension):
        @property
        def descriptor(self) -> ExtensionDescriptor:
            return ExtensionDescriptor(name="ExtNormal")

        def register(self, c):
            pass

        def boot(self, c):
            pass

        def initialize(self, c):
            history.append("init_normal")

        def start(self, c):
            pass

        def stop(self, c):
            pass

        def shutdown(self, c):
            pass

        def dispose(self, c):
            history.append("dispose_normal")

    class ExtFailingInit(IExtension):
        @property
        def descriptor(self) -> ExtensionDescriptor:
            return ExtensionDescriptor(
                name="ExtFailingInit", dependencies=["ExtNormal"]
            )

        def register(self, c):
            pass

        def boot(self, c):
            pass

        def initialize(self, c):
            raise RuntimeError("Init Boom")

        def start(self, c):
            pass

        def stop(self, c):
            pass

        def shutdown(self, c):
            pass

        def dispose(self, c):
            history.append("dispose_failing")

    container = StdLibContainer()
    event_bus = MemoryEventBus()
    app = App(container, event_bus)
    app.use(ExtNormal())

    with pytest.raises(RuntimeError) as exc:
        app.use(ExtFailingInit())

    assert "Init Boom" in str(exc.value)
    assert "dispose_normal" in history


def test_bootstrap_boot__rollback_cleanup_fails__logs_error_without_crash():
    container = StdLibContainer()
    event_bus = MemoryEventBus()
    app = App(container, event_bus)

    # Force error during hosted services start inside app.boot()
    app.context.hosted_services.start = MagicMock(
        side_effect=RuntimeError("Boot Failure")
    )

    # Mock cleanup handlers to throw during rollback
    app.context.scheduler.stop = MagicMock(
        side_effect=RuntimeError("Scheduler Cleanup Fail")
    )
    app.context.async_runtime.stop = MagicMock(
        side_effect=RuntimeError("Async Cleanup Fail")
    )

    with pytest.raises(RuntimeError) as exc:
        app.boot()

    assert "Boot Failure" in str(exc.value)


# ==========================================================
# 3. KERNEL / ExtensionManager Exception Cases
# ==========================================================


def test_extension_manager__initialize_raises__rollback_disposes_previous():
    history = []

    class Ext1(IExtension):
        @property
        def descriptor(self) -> ExtensionDescriptor:
            return ExtensionDescriptor(name="Ext1")

        def register(self, c):
            pass

        def boot(self, c):
            pass

        def initialize(self, c):
            history.append("init_1")

        def start(self, c):
            pass

        def stop(self, c):
            pass

        def shutdown(self, c):
            pass

        def dispose(self, c):
            history.append("dispose_1")

    class Ext2(IExtension):
        @property
        def descriptor(self) -> ExtensionDescriptor:
            return ExtensionDescriptor(name="Ext2", dependencies=["Ext1"])

        def register(self, c):
            pass

        def boot(self, c):
            pass

        def initialize(self, c):
            raise RuntimeError("Init 2 Fail")

        def start(self, c):
            pass

        def stop(self, c):
            pass

        def shutdown(self, c):
            pass

        def dispose(self, c):
            history.append("dispose_2")

    container = StdLibContainer()
    event_bus = MemoryEventBus()
    app = App(container, event_bus)

    app.use(Ext1())
    with pytest.raises(RuntimeError) as exc:
        app.use(Ext2())

    assert "Init 2 Fail" in str(exc.value)
    assert "dispose_1" in history


def test_extension_manager__stop_raises__dispose_still_called():
    history = []

    class ExtBadStop(IExtension):
        @property
        def descriptor(self) -> ExtensionDescriptor:
            return ExtensionDescriptor(name="BadStop")

        def register(self, c):
            pass

        def boot(self, c):
            pass

        def initialize(self, c):
            pass

        def start(self, c):
            pass

        def stop(self, c):
            raise RuntimeError("Stop Fail")

        def shutdown(self, c):
            pass

        def dispose(self, c):
            history.append("disposed")

    container = StdLibContainer()
    event_bus = MemoryEventBus()
    app = App(container, event_bus)
    app.use(ExtBadStop())
    app.boot()

    app.context.extension_manager.stop_and_dispose()
    assert history == ["disposed"]


# ==========================================================
# 4. RUNTIME / TaskManager Exception Cases
# ==========================================================


def test_task_manager__critical_task_raises__logged_and_tracked():
    container = StdLibContainer()
    event_bus = MemoryEventBus()
    app = App(container, event_bus)
    task_mgr = app.context.tasks

    def failing_fn():
        raise ValueError("Task Boom")

    bg_task = task_mgr.spawn(failing_fn, critical=True)

    # Wait for completion
    with pytest.raises(ValueError):
        bg_task.future.result(timeout=2.0)

    assert bg_task.status == TaskState.FAILED
    assert isinstance(bg_task.error, ValueError)
    task_mgr.shutdown()


def test_task_manager__spawn_during_shutdown__rejects_gracefully():
    container = StdLibContainer()
    event_bus = MemoryEventBus()
    app = App(container, event_bus)
    task_mgr = app.context.tasks

    task_mgr.shutdown()

    # Submitting to shut down executor raises RuntimeError
    with pytest.raises(RuntimeError):
        task_mgr.spawn(lambda: 42, critical=False)


# ==========================================================
# 5. RUNTIME / HostedServiceManager Exception Cases
# ==========================================================


def test_hosted_service_manager__second_start_fails__first_stopped():
    history = []

    class Svc1(IHostedService):
        def start(self, context):
            history.append("s1_start")

        def stop(self, context):
            history.append("s1_stop")

    class Svc2(IHostedService):
        def start(self, context):
            raise RuntimeError("Svc2 Fail")

        def stop(self, context):
            history.append("s2_stop")

    container = StdLibContainer()
    event_bus = MemoryEventBus()
    app = App(container, event_bus)

    mgr = HostedServiceManager(app.context)
    mgr.register(Svc1())
    mgr.register(Svc2())

    with pytest.raises(RuntimeError) as exc:
        mgr.start()

    assert "Svc2 Fail" in str(exc.value)
    assert history == ["s1_start", "s1_stop"]


def test_hosted_service_manager__service_stop_raises__others_still_stopped():
    history = []

    class SvcBadStop(IHostedService):
        def start(self, context):
            pass

        def stop(self, context):
            raise RuntimeError("Stop Svc Fail")

    class SvcGoodStop(IHostedService):
        def start(self, context):
            pass

        def stop(self, context):
            history.append("good_svc_stopped")

    container = StdLibContainer()
    event_bus = MemoryEventBus()
    app = App(container, event_bus)

    mgr = HostedServiceManager(app.context)
    mgr.register(SvcGoodStop())
    mgr.register(SvcBadStop())
    mgr.start()

    with pytest.raises(RuntimeError) as exc:
        mgr.stop()

    assert "Multiple errors" in str(exc.value) or "Stop Svc Fail" in str(exc.value)
    assert "good_svc_stopped" in history


# ==========================================================
# 6. RUNTIME / Scheduler Exception Cases
# ==========================================================


def test_scheduler__job_raises__other_jobs_still_run():
    container = StdLibContainer()
    event_bus = MemoryEventBus()
    app = App(container, event_bus)
    scheduler = app.context.scheduler

    calls = []

    def bad_job():
        raise ValueError("Job Fail")

    def good_job():
        calls.append("good")

    scheduler.after(seconds=0.01).do(bad_job)
    scheduler.after(seconds=0.01).do(good_job)

    scheduler.start()
    time.sleep(0.15)
    scheduler.stop()

    assert "good" in calls


def test_scheduler__trigger_calculation_fails__job_skipped():
    from datetime import timedelta

    class BrokenTrigger(IntervalTrigger):
        def __init__(self):
            super().__init__(timedelta(seconds=1))

        def get_next_run(self, now):
            raise RuntimeError("Trigger Calc Error")

    container = StdLibContainer()
    event_bus = MemoryEventBus()
    app = App(container, event_bus)
    scheduler = app.context.scheduler

    def dummy():
        pass

    with pytest.raises(RuntimeError) as exc:
        JobBuilder(scheduler, BrokenTrigger()).do(dummy)

    assert "Trigger Calc Error" in str(exc.value)


# ==========================================================
# 7. RUNTIME / AsyncRuntime Exception Cases
# ==========================================================


def test_async_runtime__run_coroutine_after_stop__raises_runtime_error():
    container = StdLibContainer()
    event_bus = MemoryEventBus()
    app = App(container, event_bus)
    async_rt = app.context.async_runtime

    async_rt.start()
    async_rt.stop()

    async def sample_coro():
        return 42

    coro = sample_coro()
    try:
        with pytest.raises(RuntimeError) as exc:
            async_rt.run_coroutine(coro)

        assert "loop is not running" in str(exc.value)
    finally:
        coro.close()


def test_async_runtime__background_coro_raises__logged_not_crashed():
    container = StdLibContainer()
    event_bus = MemoryEventBus()
    app = App(container, event_bus)
    async_rt = app.context.async_runtime

    async_rt.start()

    async def failing_coro():
        raise ValueError("Coro Failure")

    fut = async_rt.run_coroutine(failing_coro())

    with pytest.raises(ValueError) as exc:
        fut.result(timeout=2.0)

    assert "Coro Failure" in str(exc.value)
    async_rt.stop()


def test_async_runtime__stop_thread_still_alive__does_not_close_the_running_loop(
    caplog,
):
    """`BUG-014`: `stop()` used to run `close()` on the loop unconditionally
    after `join(timeout=...)`, whether or not the background thread's own
    `run_forever()` had actually returned -- closing a loop still running on
    another thread is unsafe in asyncio and a live suspect for this bug's
    segfaults, not just its leaked threads. Drives the real thread-lifecycle
    mechanism directly: a thread blocking on a controllable `threading.Event`
    stands in for a loop slow to notice `loop.stop()` was called."""
    import logging
    import threading

    from sagittarius_engine.runtime.async_runtime.async_runtime import AsyncRuntime

    async_rt = AsyncRuntime(context=MagicMock())
    real_loop = async_rt.loop = MagicMock()
    release = threading.Event()
    async_rt._thread = threading.Thread(target=release.wait, daemon=True)
    async_rt._thread.start()

    with caplog.at_level(logging.ERROR, logger="App"):
        async_rt.stop(timeout=0.05)

    assert async_rt._thread is not None
    assert async_rt._thread.is_alive()
    assert any("did not stop" in record.message for record in caplog.records)
    # A loop still running on its own thread must never be closed out from
    # under it.
    real_loop.close.assert_not_called()
    assert async_rt.loop is real_loop

    # Letting the real thread finish and retrying now succeeds and closes it.
    release.set()
    async_rt.stop(timeout=1.0)
    assert async_rt._thread is None
    real_loop.close.assert_called_once()
    assert async_rt.loop is None


# ==========================================================
# 8. INFRASTRUCTURE / StdLibContainer Exception Cases
# ==========================================================


def test_container__factory_raises__dependency_resolution_error_clear():
    container = StdLibContainer()

    def broken_factory(c):
        raise ValueError("Factory Failure")

    class IService:
        pass

    container.singleton(IService, broken_factory)

    with pytest.raises(ValueError) as exc:
        container.resolve(IService)

    assert "Factory Failure" in str(exc.value)


def test_container__constructor_partial_init_fails__cleanup_dependencies():
    container = StdLibContainer()

    class DepA:
        pass

    class DepB:
        def __init__(self, dep_a: DepA):
            raise RuntimeError("DepB Constructor Fail")

    container.singleton(DepA, DepA)
    container.bind(DepB, DepB)

    with pytest.raises(RuntimeError) as exc:
        container.resolve(DepB)

    assert "DepB Constructor Fail" in str(exc.value)


# ==========================================================
# 9. INFRASTRUCTURE / EventBus Variants Exception Cases
# ==========================================================


def test_thread_pool_event_bus__shutdown_during_emit__graceful():
    tp_bus = ThreadPoolEventBus(max_workers=2)

    def slow_handler(data):
        time.sleep(0.05)

    tp_bus.on("slow.evt", slow_handler)
    tp_bus.emit("slow.evt", "data")
    tp_bus.shutdown(wait=False)
    # Ensure shutdown does not throw uncaught error


def test_resilient_event_bus__reprocess_fails_again__dlq_preserved():
    inner_bus = MemoryEventBus()
    res_bus = ResilientEventBus(inner_bus=inner_bus, max_retries=1)

    def always_fails(data):
        raise ValueError("Persistent DLQ Fail")

    res_bus.on("dlq.evt", always_fails)
    res_bus.emit("dlq.evt", "payload")

    assert len(res_bus.get_dlq()) == 1

    # Reprocess again
    res_bus.reprocess()

    # DLQ should still hold the failing event
    assert len(res_bus.get_dlq()) == 1
    assert res_bus.get_dlq()[0][0] == "dlq.evt"
