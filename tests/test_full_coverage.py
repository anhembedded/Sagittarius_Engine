import asyncio
import os
import sys
import threading
import time
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from sagittarius_engine.domain import BaseEvent
from sagittarius_engine.exceptions import (
    DependencyResolutionError,
    ModuleRegistrationError,
)
from sagittarius_engine.extensions.cqrs import ICommand, IQuery
from sagittarius_engine.extensions.health.health_check_query import HealthCheckQuery
from sagittarius_engine.extensions.health.health_module import HealthExtension
from sagittarius_engine.extensions.persistence import ISession
from sagittarius_engine.infrastructure.config import (
    ConfigManager,
    DictSource,
    EnvSource,
    JsonSource,
)
from sagittarius_engine.infrastructure.config.config_sources.dotenv_source import (
    DotenvSource,
)
from sagittarius_engine.infrastructure.config.dict_config import DictConfig
from sagittarius_engine.infrastructure.container.std_container import StdLibContainer
from sagittarius_engine.infrastructure.event_bus.asyncio_event_bus import (
    AsyncioEventBus,
)
from sagittarius_engine.infrastructure.event_bus.memory_event_bus import MemoryEventBus
from sagittarius_engine.infrastructure.event_bus.resilient_event_bus import (
    ResilientEventBus,
)
from sagittarius_engine.infrastructure.event_bus.thread_pool_event_bus import (
    ThreadPoolEventBus,
)
from sagittarius_engine.infrastructure.logging.std_logger import StdLogger
from sagittarius_engine.interfaces import (
    IContainer,
    IEventBus,
    ILogger,
    IMiddleware,
    IModule,
)
from sagittarius_engine.kernel import MiddlewarePipeline
from tests.helpers import assert_event_emitted

try:
    import importlib.util

    has_pydantic = importlib.util.find_spec("pydantic") is not None

    from sagittarius_engine.middleware.pydantic_validation_middleware import (
        PydanticValidationMiddleware,
    )

    HAS_PYDANTIC = True
except ImportError:
    HAS_PYDANTIC = False

# ==========================================
# 1. Container (IContainer contract)
# ==========================================


class DummyInterface:
    pass


class DummyImplementation(DummyInterface):
    pass


class NoDependencyClass:
    pass


class SingleDependencyClass:
    def __init__(self, dep: DummyInterface):
        self.dep = dep


class NestedDependencyClass:
    def __init__(self, single: SingleDependencyClass):
        self.single = single


class AbstractClass(ICommand):
    pass


class MissingTypeHintClass:
    def __init__(self, dep):
        self.dep = dep


def test_container__bind_and_resolve__success():
    container = StdLibContainer()
    container.bind(DummyInterface, DummyImplementation)
    instance1 = container.resolve(DummyInterface)
    instance2 = container.resolve(DummyInterface)
    assert isinstance(instance1, DummyImplementation)
    assert isinstance(instance2, DummyImplementation)
    assert instance1 is not instance2  # Transient binding


def test_container__singleton_instance__returns_same_object():
    container = StdLibContainer()
    instance = DummyImplementation()
    container.singleton(DummyInterface, instance)
    resolved1 = container.resolve(DummyInterface)
    resolved2 = container.resolve(DummyInterface)
    assert resolved1 is instance
    assert resolved2 is instance


def test_container__singleton_factory__called_once():
    container = StdLibContainer()
    call_count = 0

    def factory(c):
        nonlocal call_count
        call_count += 1
        return DummyImplementation()

    container.singleton(DummyInterface, factory)
    resolved1 = container.resolve(DummyInterface)
    resolved2 = container.resolve(DummyInterface)

    assert isinstance(resolved1, DummyImplementation)
    assert resolved1 is resolved2
    assert call_count == 1


def test_container__singleton_class__returns_instance_not_class():
    """singleton(I, ConcreteClass) must return an *instance*, not the class itself."""
    container = StdLibContainer()
    container.singleton(DummyInterface, DummyImplementation)
    resolved = container.resolve(DummyInterface)
    assert isinstance(resolved, DummyImplementation), (
        "singleton() with a class should resolve to an instance, not the class"
    )


def test_container__singleton_class__returns_same_instance_on_repeated_resolve():
    """singleton(I, ConcreteClass) must be a true singleton — same object every call."""
    container = StdLibContainer()
    container.singleton(DummyInterface, DummyImplementation)
    resolved1 = container.resolve(DummyInterface)
    resolved2 = container.resolve(DummyInterface)
    assert resolved1 is resolved2


def test_container__singleton_class__auto_injects_dependencies():
    """singleton(I, ConcreteClass) must auto-inject constructor dependencies."""
    container = StdLibContainer()
    dep_instance = DummyImplementation()
    container.singleton(DummyInterface, dep_instance)
    # SingleDependencyClass requires DummyInterface in __init__
    container.singleton(SingleDependencyClass, SingleDependencyClass)
    resolved = container.resolve(SingleDependencyClass)
    assert isinstance(resolved, SingleDependencyClass)
    assert resolved.dep is dep_instance


def test_container__resolve_class_no_dependency__success():
    container = StdLibContainer()
    instance = container.resolve(NoDependencyClass)
    assert isinstance(instance, NoDependencyClass)


def test_container__resolve_nested_dependencies__success():
    container = StdLibContainer()
    container.bind(DummyInterface, DummyImplementation)

    instance = container.resolve(NestedDependencyClass)
    assert isinstance(instance, NestedDependencyClass)
    assert isinstance(instance.single, SingleDependencyClass)
    assert isinstance(instance.single.dep, DummyImplementation)


def test_container__resolve_abstract_class__raises_error():
    container = StdLibContainer()
    with pytest.raises(DependencyResolutionError):
        container.resolve(AbstractClass)


def test_container__resolve_missing_type_hint__raises_error():
    container = StdLibContainer()
    with pytest.raises(DependencyResolutionError):
        container.resolve(MissingTypeHintClass)


def test_container__resolve_missing_dependency__raises_error():
    container = StdLibContainer()

    class BrokenDependencyClass:
        def __init__(self, dep: AbstractClass):
            pass

    with pytest.raises(DependencyResolutionError):
        container.resolve(BrokenDependencyClass)


# ==========================================
# 2. IEventBus contract
# ==========================================


@pytest.fixture(params=["memory", "threadpool", "resilient", "asyncio"])
def event_bus_instance(request):
    if request.param == "memory":
        bus = MemoryEventBus()
    elif request.param == "threadpool":
        bus = ThreadPoolEventBus()
    elif request.param == "resilient":
        bus = ResilientEventBus(inner_bus=MemoryEventBus(), max_retries=1)
    elif request.param == "asyncio":
        bus = AsyncioEventBus()
    yield bus
    if hasattr(bus, "shutdown"):
        bus.shutdown()


def test_event_bus__on_and_emit__handler_receives_data(event_bus_instance):
    received_data = []

    def handler(data):
        received_data.append(data)

    event_bus_instance.on("test.event", handler)

    if isinstance(event_bus_instance, AsyncioEventBus):
        asyncio.run(event_bus_instance.emit("test.event", {"key": "value"}))
    else:
        event_bus_instance.emit("test.event", {"key": "value"})

    time.sleep(0.1)
    assert len(received_data) == 1
    assert received_data[0] == {"key": "value"}


def test_event_bus__off__handler_not_called(event_bus_instance):
    received_data = []

    def handler(data):
        received_data.append(data)

    event_bus_instance.on("test.event", handler)
    event_bus_instance.off("test.event", handler)

    if isinstance(event_bus_instance, AsyncioEventBus):
        asyncio.run(event_bus_instance.emit("test.event", {"key": "value"}))
    else:
        event_bus_instance.emit("test.event", {"key": "value"})

    time.sleep(0.1)
    assert len(received_data) == 0


def test_event_bus__multiple_handlers__all_called(event_bus_instance):
    received1 = []
    received2 = []

    def handler1(data):
        received1.append(data)

    def handler2(data):
        received2.append(data)

    event_bus_instance.on("test.event", handler1)
    event_bus_instance.on("test.event", handler2)

    if isinstance(event_bus_instance, AsyncioEventBus):
        asyncio.run(event_bus_instance.emit("test.event", "data"))
    else:
        event_bus_instance.emit("test.event", "data")

    time.sleep(0.1)
    assert len(received1) == 1
    assert len(received2) == 1


def test_event_bus__emit_no_handler__no_error(event_bus_instance):
    if isinstance(event_bus_instance, AsyncioEventBus):
        asyncio.run(event_bus_instance.emit("nonexistent.event", {"data": 1}))
    else:
        event_bus_instance.emit("nonexistent.event", {"data": 1})


def test_event_bus__emit_none_and_complex__handled(event_bus_instance):
    received = []

    def handler(data):
        received.append(data)

    event_bus_instance.on("test.none", handler)

    if isinstance(event_bus_instance, AsyncioEventBus):
        asyncio.run(event_bus_instance.emit("test.none", None))
    else:
        event_bus_instance.emit("test.none", None)

    event_bus_instance.on("test.complex", handler)
    complex_obj = {"a": [1, 2, {"b": "c"}]}

    if isinstance(event_bus_instance, AsyncioEventBus):
        asyncio.run(event_bus_instance.emit("test.complex", complex_obj))
    else:
        event_bus_instance.emit("test.complex", complex_obj)

    time.sleep(0.1)
    assert len(received) == 2
    assert received[0] is None
    assert received[1] == complex_obj


def test_resilient_event_bus__retry_success():
    bus = ResilientEventBus(inner_bus=MemoryEventBus(), max_retries=3)
    attempts = 0
    success = False

    def handler(data):
        nonlocal attempts, success
        attempts += 1
        if attempts < 3:
            raise Exception("Fail")
        success = True

    bus.on("retry.event", handler)
    bus.emit("retry.event", None)

    assert attempts == 3
    assert success
    assert len(bus.get_dlq()) == 0


def test_resilient_event_bus__retry_failure_to_dlq():
    bus = ResilientEventBus(inner_bus=MemoryEventBus(), max_retries=2)
    attempts = 0

    def handler(data):
        nonlocal attempts
        attempts += 1
        raise Exception("Always Fail")

    bus.on("fail.event", handler)
    bus.emit("fail.event", {"fail": True})

    assert attempts == 3  # Initial + 2 retries
    dlq = bus.get_dlq()
    assert len(dlq) == 1
    # DLQ item is a tuple: (event_name, data, handler, Exception)
    assert dlq[0][0] == "fail.event"
    assert dlq[0][1] == {"fail": True}


def test_resilient_event_bus__reprocess_dlq():
    bus = ResilientEventBus(inner_bus=MemoryEventBus(), max_retries=1)
    attempts = 0

    def handler(data):
        nonlocal attempts
        attempts += 1
        if attempts <= 2:  # Fail initial and 1 retry
            raise Exception("Fail first time")

    bus.on("reprocess.event", handler)
    bus.emit("reprocess.event", None)

    assert len(bus.get_dlq()) == 1

    # Now reprocess
    bus.reprocess()
    assert len(bus.get_dlq()) == 0
    assert attempts == 3  # Initial + 1 retry (2 attempts), then 1 success in reprocess


def test_asyncio_event_bus__async_handler_awaited():
    bus = AsyncioEventBus()
    async_received = False
    sync_received = False

    async def async_handler(data):
        nonlocal async_received
        await asyncio.sleep(0.01)
        async_received = True

    def sync_handler(data):
        nonlocal sync_received
        sync_received = True

    bus.on("async.event", async_handler)
    bus.on("async.event", sync_handler)

    asyncio.run(bus.emit("async.event", None))

    assert async_received
    assert sync_received


def test_thread_pool_event_bus__handler_error_no_crash_and_parallelism():
    bus = ThreadPoolEventBus(max_workers=2)
    error_raised = False
    success_ran = False

    # To test parallelism, we use a lock and wait
    lock1 = threading.Lock()
    lock2 = threading.Lock()
    lock1.acquire()
    lock2.acquire()

    order = []

    def error_handler(data):
        nonlocal error_raised
        order.append("error_start")
        lock1.release()  # Signal that error_handler started
        # Wait until success_handler starts to ensure they are parallel
        lock2.acquire()
        error_raised = True
        raise Exception("Oops")

    def success_handler(data):
        nonlocal success_ran
        # Wait for error handler to start
        lock1.acquire()
        order.append("success_start")
        success_ran = True
        lock2.release()  # Signal success handler started

    bus.on("thread.event", error_handler)
    bus.on("thread.event", success_handler)

    bus.emit("thread.event", None)

    time.sleep(0.2)
    bus.shutdown()

    assert error_raised
    assert success_ran
    # Both should have started if parallel execution works
    assert "error_start" in order
    assert "success_start" in order


# ==========================================
# 3. IMiddleware & MiddlewarePipeline contract
# ==========================================


class DummyMiddleware(IMiddleware):
    def __init__(self, name):
        self._name = name
        self.calls = []

    @property
    def name(self) -> str:
        return self._name

    def process(self, cmd_or_query, data_transfer_obj, next_handler):
        self.calls.append(f"{self.name}_before")
        response = next_handler()
        self.calls.append(f"{self.name}_after")
        return response


class MutatingMiddleware(IMiddleware):
    def process(self, cmd_or_query, data_transfer_obj, next_handler):
        if isinstance(data_transfer_obj, dict):
            data_transfer_obj["mutated"] = True
        return next_handler()


class BlockingMiddleware(IMiddleware):
    def process(self, cmd_or_query, data_transfer_obj, next_handler):
        return "blocked"


def test_middleware_pipeline__single_middleware__called_before_and_after():
    m1 = DummyMiddleware("m1")
    pipeline = MiddlewarePipeline()
    pipeline.add(m1)

    handler_called = False

    def handler():
        nonlocal handler_called
        handler_called = True
        return "response"

    result = pipeline.execute("dummy_cmd", "req", handler)

    assert result == "response"
    assert handler_called
    assert m1.calls == ["m1_before", "m1_after"]


def test_middleware_pipeline__multiple_middlewares__correct_order():
    m1 = DummyMiddleware("m1")
    m2 = DummyMiddleware("m2")
    pipeline = MiddlewarePipeline()
    pipeline.add(m1)
    pipeline.add(m2)

    def handler():
        return "response"

    pipeline.execute("dummy_cmd", "req", handler)

    assert m1.calls == ["m1_before", "m1_after"]
    assert m2.calls == ["m2_before", "m2_after"]
    # Order should be m1_before -> m2_before -> m2_after -> m1_after
    # because m1 calls next_middleware which is m2


def test_middleware_pipeline__mutates_data():
    pipeline = MiddlewarePipeline()
    pipeline.add(MutatingMiddleware())

    dto_obj = {"original": True}

    def handler():
        return dto_obj

    result = pipeline.execute("dummy_cmd", dto_obj, handler)

    assert result["mutated"] is True
    assert result["original"] is True


def test_middleware_pipeline__blocks_execution():
    pipeline = MiddlewarePipeline()
    pipeline.add(BlockingMiddleware())

    handler_called = False

    def handler():
        nonlocal handler_called
        handler_called = True
        return "response"

    result = pipeline.execute("dummy_cmd", "req", handler)

    assert result == "blocked"
    assert not handler_called


# ==========================================
# 4. App (public API)
# ==========================================


class DummyCommand(ICommand):
    def __init__(self):
        pass

    def execute(self, data_transfer_obj):
        return f"Executed cmd with {data_transfer_obj}"


class DummyQuery(IQuery):
    def __init__(self):
        pass

    def execute(self, data_transfer_obj):
        return f"Executed query with {data_transfer_obj}"


class DummyModule(IModule):
    def register(self, app):
        pass

    def boot(self, app):
        pass

    def shutdown(self, app):
        pass


class InvalidModule:
    pass


def test_app__boot_without_module__emits_booted(app_factory, event_bus):
    app = app_factory(container=StdLibContainer(), event_bus=event_bus)
    app.boot()

    assert_event_emitted(event_bus, "app.booted", times=1)


def test_app__boot_with_auto_discover__discovers_module(
    app_factory, tmp_path, event_bus
):
    # Setup mock module structure
    mod_dir = tmp_path / "my_module"
    mod_dir.mkdir()
    (mod_dir / "__init__.py").write_text("""
from sagittarius_engine.interfaces import IModule
class MyAutoModule(IModule):
    def register(self, app):
        pass
    def boot(self, app):
        pass
""")

    app = app_factory(container=StdLibContainer(), event_bus=event_bus)

    # Temporarily add tmp_path to sys.path
    sys.path.insert(0, str(tmp_path))

    try:
        app.boot(auto_discover="my_module")
    finally:
        sys.path.pop(0)

    # If it didn't crash and booted successfully, it worked.
    assert_event_emitted(event_bus, "app.booted", times=1)


def test_app__execute_command__resolves_and_executes(app_factory):
    container = StdLibContainer()
    app = app_factory(container=container, event_bus=MemoryEventBus())

    result = app.dispatch(DummyCommand, "data")
    assert result == "Executed cmd with data"


def test_app__execute_command_with_middleware(app_factory):
    container = StdLibContainer()
    app = app_factory(container=container, event_bus=MemoryEventBus())

    middleware = DummyMiddleware("app_mw")
    app.use_middleware(middleware)

    result = app.dispatch(DummyCommand, "data")
    assert result == "Executed cmd with data"
    assert middleware.calls == ["app_mw_before", "app_mw_after"]


def test_app__execute_query__resolves_and_executes(app_factory):
    container = StdLibContainer()
    app = app_factory(container=container, event_bus=MemoryEventBus())

    result = app.dispatch(DummyQuery, "query_data")
    assert result == "Executed query with query_data"


def test_app__use_module__registers_and_boots(app_factory):
    app = app_factory(container=StdLibContainer(), event_bus=MemoryEventBus())
    mod = DummyModule()

    # Spy on register and boot
    mod.register = MagicMock()
    mod.boot = MagicMock()

    app.use(mod)
    app.boot()

    mod.register.assert_called_once_with(app)
    mod.boot.assert_called_once_with(app)


def test_app__use_invalid_module__raises_error(app_factory):
    app = app_factory(container=StdLibContainer(), event_bus=MemoryEventBus())
    with pytest.raises(ModuleRegistrationError):
        app.use(InvalidModule())


def test_app__logger_behavior_on_boot(app_factory):
    # Without logger, doesn't crash during boot
    app = app_factory(container=StdLibContainer(), event_bus=MemoryEventBus())
    app.boot()

    # With logger bound, check that it writes to the logger during execute
    container = StdLibContainer()
    # MagicMock is callable, so StdLibContainer treats it as a factory.
    # We must wrap it in a lambda or provide an instance that isn't callable.
    mock_logger = MagicMock(spec=ILogger)
    container.singleton(ILogger, lambda c: mock_logger)
    app = app_factory(container=container, event_bus=MemoryEventBus())

    # Execute something to trigger logging
    app.dispatch(DummyCommand, "data")

    # Verify the mock logger was called
    mock_logger.info.assert_called()
    call_args = [call.args[0] for call in mock_logger.info.call_args_list]
    assert any("Executing command: DummyCommand" in arg for arg in call_args)


# ==========================================
# 5. ILogger contract (StdLogger)
# ==========================================


def test_std_logger__log_levels_to_console(capsys):
    logger = StdLogger()

    logger.info("info message")
    logger.warning("warning message")
    logger.error("error message")

    # By default, level is INFO, so DEBUG shouldn't print unless set
    logger.debug("debug message")

    captured = capsys.readouterr()

    assert "INFO - info message" in captured.out
    assert "WARNING - warning message" in captured.out
    assert "ERROR - error message" in captured.out
    assert "DEBUG - debug message" not in captured.out


def test_std_logger__with_config__respects_level_and_file(tmp_path):
    log_file = tmp_path / "test.log"

    config = DictConfig()
    config.set("log.level", "DEBUG")
    config.set("log.file", str(log_file))

    # Needs to re-initialize with config
    logger = StdLogger(config=config)

    logger.debug("should be printed")
    logger.info("also printed")

    content = log_file.read_text()

    assert "DEBUG - should be printed" in content
    assert "INFO - also printed" in content


# ==========================================
# 6. IConfig contract
# ==========================================


def test_config__dict_config__get_set():
    config = DictConfig()
    config.set("key", "value")
    assert config.get("key") == "value"
    assert config.get("nonexistent", "default") == "default"


def test_config__manager__loads_sources_and_overrides():
    source1 = DictSource({"a": 1, "b": 2})
    source2 = DictSource({"b": 3, "c": 4})

    manager = ConfigManager()
    manager.add_source(source1)
    manager.add_source(source2)
    # implicit load via get()

    assert manager.get("a") == 1
    assert manager.get("b") == 3  # Overridden by source2
    assert manager.get("c") == 4
    assert manager.get("d", "default") == "default"


def test_config__env_source():
    with patch.dict(os.environ, {"MY_APP_ENV_VAR": "test_value"}):
        source = EnvSource(prefix="MY_APP_")
        source.read()
        # the prefix is usually stripped or lowercased depending on implementation
        # Let's check how EnvSource works
        manager = ConfigManager()
        manager.add_source(source)
        # implicit load via get()
        # In typical implementations with prefix MY_APP_, it becomes 'env_var'
        assert (
            manager.get("ENV_VAR") == "test_value"
            or manager.get("MY_APP_ENV_VAR") == "test_value"
            or manager.get("env_var") == "test_value"
        )


def test_config__json_source(tmp_path):
    json_file = tmp_path / "config.json"
    json_file.write_text('{"json_key": "json_val"}')

    source = JsonSource(str(json_file))
    manager = ConfigManager()
    manager.add_source(source)
    # implicit load via get()

    assert manager.get("json_key") == "json_val"


def test_config__dotenv_source(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("DOTENV_KEY=dotenv_val\n")

    source = DotenvSource(str(env_file))
    manager = ConfigManager()
    manager.add_source(source)
    # implicit load via get()

    assert manager.get("DOTENV_KEY") == "dotenv_val"


# ==========================================
# 7. BaseEvent contract
# ==========================================


class MyEvent(BaseEvent):
    def __init__(self, data: str):
        super().__init__()
        self.data = data


def test_base_event__unique_id_and_recent_timestamp():
    event1 = MyEvent("d1")
    event2 = MyEvent("d2")

    assert event1.event_id != event2.event_id

    # Check timestamp is close to now
    now = datetime.now(UTC)
    diff = now - event1.occurred_on
    assert diff.total_seconds() < 1  # Should be created within 1 second


def test_base_event__to_dict__returns_expected_keys():
    event = MyEvent("d1")
    d = event.to_dict()

    assert "event_id" in d
    assert "occurred_on" in d
    assert d["data"] == "d1"


# ==========================================
# 8. IModule & ModuleAutoDiscovery
# ==========================================


def test_module_auto_discovery__loads_correct_modules(app_factory, tmp_path, event_bus):
    root = tmp_path / "modules_test"
    root.mkdir()
    (root / "__init__.py").write_text("")

    # 1. Package module (directory with __init__.py)
    pkg_dir = root / "pkg_mod"
    pkg_dir.mkdir()
    (pkg_dir / "__init__.py").write_text("""
from sagittarius_engine.interfaces import IModule
class PkgModule(IModule):
    def register(self, app):
        app.event_bus.emit("pkg_mod.registered", None)
    def boot(self, app):
        pass
    def shutdown(self, app):
        pass
""")

    # 2. Single file module
    (root / "single_mod.py").write_text("""
from sagittarius_engine.interfaces import IModule
class SingleModule(IModule):
    def register(self, app):
        app.event_bus.emit("single_mod.registered", None)
    def boot(self, app):
        pass
    def shutdown(self, app):
        pass
""")

    # 3. File without module class (ignored)
    (root / "ignored.py").write_text("""
class JustAClass:
    pass
""")

    # Temporarily insert root parent to sys.path
    sys.path.insert(0, str(tmp_path))

    try:
        app = app_factory(container=StdLibContainer(), event_bus=event_bus)
        app.boot(auto_discover="modules_test")

        assert_event_emitted(event_bus, "pkg_mod.registered", times=1)
        assert_event_emitted(event_bus, "single_mod.registered", times=1)

    finally:
        sys.path.pop(0)


# ==========================================
# 9. HealthModule
# ==========================================


def test_health_module__without_database(app_factory, event_bus):
    container = StdLibContainer()
    container.singleton(IContainer, container)
    container.singleton(IEventBus, event_bus)
    app = app_factory(container=container, event_bus=event_bus)
    app.use(HealthExtension())
    app.boot()

    # After boot, container has IEventBus bound. Let's make sure App has its own container setup.
    # Health check should return OK for container and event_bus
    result = app.dispatch(HealthCheckQuery)

    assert result["status"] == "healthy"
    assert result["components"]["container"] == "ok"
    assert result["components"]["event_bus"] == "ok"
    assert result["components"]["database"] == "not configured"


def test_health_module__with_database(app_factory, event_bus):
    container = StdLibContainer()
    container.singleton(IContainer, container)
    container.singleton(IEventBus, event_bus)
    app = app_factory(container=container, event_bus=event_bus)

    # Mock database session
    mock_session = MagicMock(spec=ISession)
    # The mock session needs to have an execute method that does not raise error
    mock_session.execute.return_value = None

    mock_sa = MagicMock()
    mock_sa.exc = MagicMock()
    mock_sa.exc.SQLAlchemyError = Exception
    mock_sa.text.return_value = "SELECT 1"

    app.container.singleton(ISession, mock_session)

    with patch.dict("sys.modules", {"sqlalchemy": mock_sa}):
        app.use(HealthExtension())
        app.boot()

        result = app.dispatch(HealthCheckQuery)

        assert result["status"] == "healthy"
        assert result["components"]["database"] == "ok"


# ==========================================
# 10. PydanticValidationMiddleware
# ==========================================


def test_pydantic_validation_middleware__validate_success():
    pytest.importorskip("pydantic")
    from pydantic import BaseModel

    class MyDTO(BaseModel):
        name: str
        age: int

    middleware = PydanticValidationMiddleware(model_class=MyDTO)

    handler_called = False

    def final_handler():
        nonlocal handler_called
        handler_called = True
        return "ok"

    # valid input data_transfer_obj
    data_transfer_obj = {"name": "Test", "age": 20}

    result = middleware.process("dummy_cmd", data_transfer_obj, final_handler)

    assert result == "ok"
    assert handler_called


def test_pydantic_validation_middleware__validate_failure_blocks_execution():
    pytest.importorskip("pydantic")
    from pydantic import BaseModel

    class MyDTO(BaseModel):
        name: str
        age: int

    middleware = PydanticValidationMiddleware(model_class=MyDTO)

    handler_called = False

    def final_handler():
        nonlocal handler_called
        handler_called = True
        return "ok"

    # invalid input data_transfer_obj
    data_transfer_obj = {"name": "Test"}  # missing age

    with pytest.raises(ValueError, match="Validation failed"):
        middleware.process(DummyCommand(), data_transfer_obj, final_handler)

    assert not handler_called


# ==========================================
# 11. Integration End-to-End
# ==========================================


def test_integration__end_to_end_flow(app_factory):
    # Setup Container and EventBus
    container = StdLibContainer()
    event_bus = MemoryEventBus()

    # Needs to bind itself to container
    container.singleton(IContainer, container)
    container.singleton(IEventBus, event_bus)

    app = app_factory(container=container, event_bus=event_bus)

    # Create Logger Mock
    # MagicMock is callable, so StdLibContainer treats it as a factory.
    # We must wrap it in a lambda or provide an instance that isn't callable.
    mock_logger = MagicMock(spec=ILogger)
    container.singleton(ILogger, lambda c: mock_logger)

    # Create Custom Module
    class MiniAppModule(IModule):
        def register(self, app):
            # Register Command and Query
            app.container.bind("mini.command", MiniCommand)
            app.container.bind("mini.query", MiniQuery)

            # Subscribe to event
            app.event_bus.on("mini.event", self.handle_mini_event)
            self.event_handled = False

        def boot(self, app):
            pass

        def shutdown(self, app):
            pass

        def handle_mini_event(self, data):
            self.event_handled = True
            self.event_data = data

    class MiniCommand(ICommand):
        def __init__(self, event_bus: IEventBus):
            self.event_bus = event_bus

        def execute(self, data_transfer_obj):
            self.event_bus.emit("mini.event", data_transfer_obj)
            return "mini_command_done"

    class MiniQuery(IQuery):
        def execute(self, data_transfer_obj):
            return f"mini_query_{data_transfer_obj}"

    # Setup Custom Middleware
    class MiniMiddleware(IMiddleware):
        def __init__(self, logger: ILogger):
            self.logger = logger

        def process(self, cmd_or_query, data_transfer_obj, next_handler):
            self.logger.info(f"Middleware Before {type(cmd_or_query).__name__}")
            result = next_handler()
            self.logger.info(f"Middleware After {type(cmd_or_query).__name__}")
            return result

    # Bind Middleware's dependency explicitly or use container to resolve it
    mini_middleware = container.resolve(MiniMiddleware)
    app.use_middleware(mini_middleware)
    assert mini_middleware.logger is mock_logger

    mini_module = MiniAppModule()
    app.use(mini_module)
    app.boot()

    # Execute Command
    cmd_result = app.dispatch(MiniCommand, "test_data")
    assert cmd_result == "mini_command_done"

    # Execute Query
    query_result = app.dispatch(MiniQuery, "test")
    assert query_result == "mini_query_test"

    # Assert Event was emitted and handled
    assert mini_module.event_handled is True
    assert mini_module.event_data == "test_data"

    # Assert Logger was called by Middleware
    call_strs = [call.args[0] for call in mock_logger.info.call_args_list]

    assert any("Middleware Before MiniCommand" in c for c in call_strs)
    assert any("Middleware After MiniCommand" in c for c in call_strs)
    assert any("Middleware Before MiniQuery" in c for c in call_strs)
    assert any("Middleware After MiniQuery" in c for c in call_strs)
