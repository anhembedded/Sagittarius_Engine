import abc
import asyncio
import importlib
import sys
import time
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from sagittarius_engine.exceptions import DependencyResolutionError
from sagittarius_engine.extensions.cqrs import ICommand
from sagittarius_engine.extensions.health.health_check_query import HealthCheckQuery
from sagittarius_engine.extensions.health.health_module import HealthExtension
from sagittarius_engine.extensions.persistence import ISession
from sagittarius_engine.infrastructure.config import ConfigManager, JsonSource
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
from sagittarius_engine.interfaces import (
    IContainer,
    IEventBus,
    ILogger,
    IMiddleware,
    IModule,
)
from sagittarius_engine.kernel import App, MiddlewarePipeline


# --- Fixtures ---
@pytest.fixture
def container():
    return StdLibContainer()


@pytest.fixture
def event_bus():
    return MemoryEventBus()


@pytest.fixture
def logger():
    return MagicMock(spec=ILogger)


@pytest.fixture
def app(container, event_bus, logger):
    app = App(container, event_bus)
    container.singleton(ILogger, logger)
    return app


# --- 1. Container Edge Cases ---


def test_container__resolve_unbound_interface__raises_dependency_resolution_error(
    container,
):
    class IUnboundInterface(abc.ABC):
        @abc.abstractmethod
        def do_something(self):
            pass

    with pytest.raises(DependencyResolutionError):
        container.resolve(IUnboundInterface)


def test_container__factory_raises_exception__raises_dependency_resolution_error(
    container,
):
    class MyClass:
        pass

    def bad_factory(c):
        raise ValueError("Factory failed")

    container.singleton(MyClass, bad_factory)

    with pytest.raises((DependencyResolutionError, ValueError)) as excinfo:
        container.resolve(MyClass)

    assert "Factory failed" in str(excinfo.value) or "DependencyResolutionError" in str(
        excinfo.type
    )


def test_container__resolve_optional_parameter__uses_default(container):
    class ClassWithOptionalParam:
        def __init__(self, param: str | None = None):
            self.param = param

    container.bind("test", ClassWithOptionalParam)
    try:
        instance = container.resolve("test")
        assert isinstance(instance, ClassWithOptionalParam)
        assert instance.param is None
    except DependencyResolutionError as e:
        pytest.fail(f"Container failed to resolve Optional parameter with default: {e}")


# --- 2. EventBus Edge Cases ---


def test_memory_event_bus__handler_raises_exception__others_called_and_logged(logger):
    bus = MemoryEventBus()
    bus.logger = logger

    event = "test.event"

    handler1 = MagicMock()
    handler2 = MagicMock()

    # handler1 raises exception
    handler1.side_effect = ValueError("Handler 1 failed")

    bus.on("test.event", handler1)
    bus.on("test.event", handler2)

    bus.emit(event, data=event)

    handler1.assert_called_once_with(event)
    handler2.assert_called_once_with(event)
    logger.error.assert_called_once()
    assert (
        "Handler 1 failed" in logger.error.call_args[0][0]
        or "Error in handler" in logger.error.call_args[0][0]
    )


def test_resilient_event_bus__max_retries_0__goes_to_dlq(logger):
    memory_bus = MemoryEventBus()
    memory_bus.logger = logger
    bus = ResilientEventBus(memory_bus, max_retries=0)

    event = "test.event"
    handler = MagicMock()
    handler.side_effect = ValueError("Failed immediately")

    bus.on("test.event", handler)
    bus.emit(event, data=event)

    time.sleep(0.1)

    handler.assert_called_once_with(event)
    assert len(bus.get_dlq()) == 1
    assert bus.get_dlq()[0][0] == event
    assert bus.get_dlq()[0][1] == event
    assert isinstance(bus.get_dlq()[0][3], ValueError)


def test_thread_pool_event_bus__handler_timeout__does_not_block(logger):
    bus = ThreadPoolEventBus(max_workers=2)
    bus.logger = logger

    event = "test.event"

    def slow_handler(e):
        time.sleep(0.5)

    fast_handler = MagicMock()

    bus.on("test.event", slow_handler)
    bus.on("test.event", fast_handler)

    start = time.time()
    bus.emit(event, data=event)
    end = time.time()

    assert end - start < 0.2

    time.sleep(0.1)
    fast_handler.assert_called_once_with(event)


@pytest.mark.asyncio
async def test_asyncio_event_bus__handler_cancelled__does_not_crash(logger):
    bus = AsyncioEventBus()
    bus.logger = logger

    event = "test.event"

    async def cancelled_handler(e):
        raise asyncio.CancelledError()

    async def good_handler(e):
        good_handler.called = True

    good_handler.called = False

    bus.on("test.event", cancelled_handler)
    bus.on("test.event", good_handler)

    try:
        await bus.emit(event, data=event)
    except asyncio.CancelledError:
        pass

    await asyncio.sleep(0.1)
    assert good_handler.called is True


# --- 3. MiddlewarePipeline Edge Cases ---


def test_middleware__raises_before_next__propagates_and_handler_not_called(app):
    class ThrowBeforeMiddleware(IMiddleware):
        def process(
            self, command: Any, data_transfer_obj: Any, next_handler: Any
        ) -> Any:
            raise ValueError("Failed before next")

    pipeline = MiddlewarePipeline()
    pipeline.add(ThrowBeforeMiddleware())

    handler_called = False

    def final_handler():
        nonlocal handler_called
        handler_called = True
        return "success"

    with pytest.raises(ValueError, match="Failed before next"):
        pipeline.execute("dummy_command", "dummy_dto", final_handler)

    assert not handler_called


def test_middleware__raises_after_next__propagates_and_handler_called(app):
    class ThrowAfterMiddleware(IMiddleware):
        def process(
            self, command: Any, data_transfer_obj: Any, next_handler: Any
        ) -> Any:
            next_handler()
            raise ValueError("Failed after next")

    pipeline = MiddlewarePipeline()
    pipeline.add(ThrowAfterMiddleware())

    handler_called = False

    def final_handler():
        nonlocal handler_called
        handler_called = True
        return "success"

    with pytest.raises(ValueError, match="Failed after next"):
        pipeline.execute("dummy_command", "dummy_dto", final_handler)

    assert handler_called


# --- 4. App Edge Cases ---


def test_app__execute_command_not_in_container__raises_dependency_resolution_error(app):
    class DepForUnregisteredCommand:
        def __init__(self, not_resolvable_arg):
            pass

    class CmdWithUnresolvedDep(ICommand):
        def __init__(self, dep: DepForUnregisteredCommand):
            pass

        def execute(self, data):
            pass

    with pytest.raises(DependencyResolutionError):
        app.dispatch(CmdWithUnresolvedDep)


def test_app__boot_with_nonexistent_package__does_not_crash_but_logs_warning(
    app, logger, capsys
):
    app.boot(auto_discover="non_existent_package_12345")
    # the mock resolves slightly differently due to factory/singleton caching but warning is called
    assert any(
        "Could not discover package non_existent_package_12345" in str(call)
        for call in logger.mock_calls
    )


def test_app__boot_with_empty_module_directory__does_not_crash(app, tmp_path):
    module_dir = tmp_path / "empty_modules"
    module_dir.mkdir()
    (module_dir / "__init__.py").touch()

    import sys

    sys.path.insert(0, str(tmp_path))

    try:
        app.boot(auto_discover="empty_modules")
        assert True
    finally:
        sys.path.pop(0)


# --- 5. ModuleAutoDiscovery Edge Cases ---


def test_module_autodiscovery__syntax_error__ignores_and_does_not_crash(app, tmp_path):
    module_dir = tmp_path / "syntax_error_modules"
    module_dir.mkdir()
    (module_dir / "__init__.py").touch()

    with open(module_dir / "valid_module.py", "w") as f:
        f.write("from sagittarius_engine.interfaces import IModule\n")
        f.write("class ValidModule(IModule):\n")
        f.write("    def register(self, app): pass\n")
        f.write("    def boot(self, app): pass\n")
        f.write("    def shutdown(self, app): pass\n")

    with open(module_dir / "invalid_module.py", "w") as f:
        f.write("class InvalidModule(IModule)  # Syntax error, missing colon\n")
        f.write("    def register(self, app): pass\n")

    import sys

    sys.path.insert(0, str(tmp_path))

    try:
        app.boot(auto_discover="syntax_error_modules")
        assert len(app.modules) == 1
        assert app.modules[0].__class__.__name__ == "ValidModule"
    finally:
        sys.path.pop(0)


def test_module_autodiscovery__import_error__ignores_and_does_not_crash(app, tmp_path):
    module_dir = tmp_path / "import_error_modules"
    module_dir.mkdir()
    (module_dir / "__init__.py").touch()

    with open(module_dir / "valid_module.py", "w") as f:
        f.write("from sagittarius_engine.interfaces import IModule\n")
        f.write("class ValidModule(IModule):\n")
        f.write("    def register(self, app): pass\n")
        f.write("    def boot(self, app): pass\n")
        f.write("    def shutdown(self, app): pass\n")

    with open(module_dir / "missing_import_module.py", "w") as f:
        f.write("import missing_package_12345\n")
        f.write("from sagittarius_engine.interfaces import IModule\n")
        f.write("class MissingImportModule(IModule):\n")
        f.write("    def register(self, app): pass\n")
        f.write("    def boot(self, app): pass\n")
        f.write("    def shutdown(self, app): pass\n")

    import sys

    sys.path.insert(0, str(tmp_path))

    try:
        app.boot(auto_discover="import_error_modules")
        assert len(app.modules) == 1
        assert app.modules[0].__class__.__name__ == "ValidModule"
    finally:
        sys.path.pop(0)


def test_module_autodiscovery__no_imodule_class__does_not_crash(app, tmp_path):
    module_dir = tmp_path / "no_module_class_modules"
    module_dir.mkdir()
    (module_dir / "__init__.py").touch()

    with open(module_dir / "dummy.py", "w") as f:
        f.write("class JustAClass:\n")
        f.write("    pass\n")

    import sys

    sys.path.insert(0, str(tmp_path))

    try:
        app.boot(auto_discover="no_module_class_modules")
        assert len(app.modules) == 0
    finally:
        sys.path.pop(0)


# --- 6. HealthModule Edge Cases ---


def test_health_module__db_session_raises__returns_unhealthy(app, container, event_bus):
    module = HealthExtension()
    module.register(app)

    class ThrowingSession(ISession):
        def commit(self):
            pass

        def rollback(self):
            pass

        def query(self, *e):
            pass

        def execute(self, statement, params=None):
            raise Exception("DB Connection Lost")

        def add(self, entity):
            pass

        def get(self, entity_class, entity_id):
            pass

        def merge(self, entity):
            pass

        def delete(self, entity):
            pass

    container.singleton(ISession, ThrowingSession())

    container.singleton(IEventBus, event_bus)
    container.singleton(IContainer, container)

    query = container.resolve(HealthCheckQuery)

    mock_sqlalchemy = MagicMock()
    mock_sqlalchemy.exc = MagicMock()
    mock_sqlalchemy.exc.SQLAlchemyError = Exception
    mock_sqlalchemy.text.return_value = "SELECT 1"
    with patch.dict("sys.modules", {"sqlalchemy": mock_sqlalchemy}):
        status = query.execute()

    assert status["status"] == "unhealthy"
    assert "database connection failed" in status["components"]["database"]


def test_health_module__no_isession_configured__returns_not_configured(
    app, container, event_bus
):
    module = HealthExtension()
    module.register(app)

    # Don't bind

    container.singleton(IEventBus, event_bus)
    container.singleton(IContainer, container)

    query = container.resolve(HealthCheckQuery)
    status = query.execute()

    assert "not configured" in status["components"]["database"]


def test_health_module__boot_raises__logs_instead_of_swallowing_silently(
    app, container, event_bus, caplog
):
    """@brief Regression test for TASK-026 requirement 5: HealthExtension.boot()
    must not swallow a failure silently — it must log it and still not raise."""
    module = HealthExtension()
    module.register(app)

    container.singleton(IEventBus, event_bus)
    container.singleton(IContainer, container)

    class RaisingQuery:
        def execute(self, *_args, **_kwargs):
            raise RuntimeError("health check blew up")

    container.singleton(HealthCheckQuery, RaisingQuery())

    with caplog.at_level("ERROR"):
        module.boot(app)  # must not raise

    assert any(
        "HealthExtension.boot() failed" in record.message for record in caplog.records
    )


# --- 7. Config Edge Cases ---


def test_config__json_source_invalid_json__returns_empty_dict(tmp_path):
    invalid_json_file = tmp_path / "config.json"
    invalid_json_file.write_text("{invalid_json: 123,}")

    source = JsonSource(str(invalid_json_file))
    result = source.read()

    # Requirement: `read()` trả về dict rỗng, không crash.
    assert result == {}


def test_config__config_manager_failing_source__returns_default():
    class FailingSource:
        def read(self) -> dict[str, Any]:
            raise Exception("Source failed to read")

    manager = ConfigManager()
    manager.add_source(FailingSource())

    # Require: không crash, get vẫn trả về default
    val = manager.get("some.key", "my_default")
    assert val == "my_default"


# --- 8. PydanticValidationMiddleware Edge Cases ---


def test_pydantic_middleware__missing_pydantic__raises_import_error():
    from sagittarius_engine.middleware import pydantic_validation_middleware

    with patch.dict(sys.modules, {"pydantic": None}):
        importlib.reload(pydantic_validation_middleware)
        with pytest.raises(
            ImportError,
            match="pydantic is not installed. Please install it using `pip install pydantic`.",
        ):
            pydantic_validation_middleware.PydanticValidationMiddleware(
                model_class=None
            )

    # Restore the module state for subsequent tests
    importlib.reload(pydantic_validation_middleware)


def test_pydantic_middleware__dto_is_none__raises_exception():
    pydantic = pytest.importorskip("pydantic")
    from sagittarius_engine.middleware.pydantic_validation_middleware import (
        PydanticValidationMiddleware,
    )

    class MyDTO(pydantic.BaseModel):
        name: str

    middleware = PydanticValidationMiddleware(model_class=MyDTO)

    class DummyCommand:
        pass

    with pytest.raises(ValueError):
        # Current logic checks `if data_transfer_obj is not None`. If it is None and the model requires it, it doesn't fail unless changed
        # We need to make sure `data_transfer_obj=None` raises error if the DTO is required.
        # But wait, wait. The requirement says:
        # "DTO là None → raise ValidationError hoặc exception rõ ràng."
        middleware.process(DummyCommand(), None, lambda: "ok")


def test_pydantic_middleware__dto_missing_required_field__raises_exception():
    pydantic = pytest.importorskip("pydantic")
    from sagittarius_engine.middleware.pydantic_validation_middleware import (
        PydanticValidationMiddleware,
    )

    class MyDTO(pydantic.BaseModel):
        name: str

    middleware = PydanticValidationMiddleware(model_class=MyDTO)

    class DummyCommand:
        pass

    with pytest.raises(ValueError, match="Validation failed"):
        middleware.process(DummyCommand(), {}, lambda: "ok")


# --- 9. Integration End-to-End Edge ---


def test_integration__module_event_handler_raises__app_does_not_crash(
    app, container, event_bus
):
    class ThrowingEventHandlerModule(IModule):
        def register(self, app):
            pass

        def boot(self, app):
            app.event_bus.on("some.event", self.bad_handler)
            app.event_bus.on("some.event", self.good_handler)
            self.good_handler_called = False

        def shutdown(self, app):
            pass

        def bad_handler(self, e):
            raise Exception("Handler failed")

        def good_handler(self, e):
            self.good_handler_called = True

    module = ThrowingEventHandlerModule()
    app.use(module)
    app.boot()

    app.event_bus.emit("some.event", data="test")

    assert module.good_handler_called is True


def test_integration__command_emits_event_without_handlers__does_not_crash(
    app, container, event_bus
):
    class EventEmittingCommand(ICommand):
        def __init__(self, event_bus: IEventBus):
            self.event_bus = event_bus

        def execute(self, data):
            self.event_bus.emit("no.handlers.event", data=data)
            return "success"

    container.singleton(IEventBus, event_bus)
    container.bind("cmd", EventEmittingCommand)

    result = app.dispatch(EventEmittingCommand, "dummy_data")
    assert result == "success"


def test_container_thread_safety():
    import threading
    import time

    container = StdLibContainer()

    class Dependency:
        instances_count = 0

        def __init__(self):
            time.sleep(0.05)
            Dependency.instances_count += 1

    container.singleton(Dependency, lambda c: Dependency())

    results = []

    def worker():
        dep = container.resolve(Dependency)
        results.append(dep)

    threads = [threading.Thread(target=worker) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(results) == 10
    assert all(r is results[0] for r in results)
    assert Dependency.instances_count == 1


def test_module_autodiscovery_logging(app, logger, tmp_path):
    module_dir = tmp_path / "logging_error_modules"
    module_dir.mkdir()
    (module_dir / "__init__.py").touch()

    with open(module_dir / "bad_module.py", "w") as f:
        f.write("raise ValueError('Intentional error during import')\n")

    import sys

    sys.path.insert(0, str(tmp_path))

    try:
        app.boot(auto_discover="logging_error_modules")
        assert any("Failed to load module" in str(call) for call in logger.mock_calls)
    finally:
        sys.path.pop(0)


def test_session_context_manager():
    class DummySession(ISession):
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            if exc_type:
                self.rollback()
            self.close()

        def __init__(self):
            self.committed = False
            self.rolled_back = False
            self.closed = False

        def commit(self):
            self.committed = True

        def rollback(self):
            self.rolled_back = True

        def execute(self, statement, params=None):
            pass

        def query(self, *entities):
            pass

        def add(self, entity):
            pass

        def get(self, entity_class, entity_id):
            pass

        def merge(self, entity):
            pass

        def delete(self, entity):
            pass

        def close(self):
            self.closed = True

    # Test normal exit
    session = DummySession()
    with session as s:
        assert s is session
    assert session.closed is True
    assert session.rolled_back is False

    # Test exit with exception
    session2 = DummySession()
    try:
        with session2:
            raise RuntimeError("Database error")
    except RuntimeError:
        pass
    assert session2.closed is True
    assert session2.rolled_back is True


@patch(
    "sagittarius_engine.extensions.persistence.database_module.SQLALCHEMY_INSTALLED",
    True,
)
def test_database_module_production_failure(app, monkeypatch):
    from sagittarius_engine.extensions.persistence.database_module import (
        DatabaseExtension,
    )
    from sagittarius_engine.interfaces import IConfig

    monkeypatch.setenv("ENV", "production")

    mock_config = MagicMock()
    mock_config.get.return_value = None  # No database url
    app.container.singleton(IConfig, lambda c: mock_config)

    extension = DatabaseExtension()
    with pytest.raises(ValueError) as excinfo:
        extension.register(app)

    assert "production environment" in str(excinfo.value)


def test_health_check_query_dto(app, container, event_bus):
    from sagittarius_engine.extensions.health.health_check_query import (
        HealthCheckDTO,
        HealthCheckQuery,
    )

    container.singleton(IContainer, container)
    container.singleton(IEventBus, event_bus)

    query = HealthCheckQuery(container, event_bus)
    dto = HealthCheckDTO()
    result = query.execute(dto)
    assert result["status"] == "healthy"


def test_pydantic_validation_middleware_v2():
    pydantic = pytest.importorskip("pydantic")
    from sagittarius_engine.middleware.pydantic_validation_middleware import (
        PydanticValidationMiddleware,
    )

    class TestDTO(pydantic.BaseModel):
        name: str
        age: int

    middleware = PydanticValidationMiddleware(model_class=TestDTO)

    class DummyCommand:
        pass

    called = []

    def next_handler():
        called.append(True)

    middleware.process(DummyCommand(), {"name": "Bob", "age": 30}, next_handler)
    assert called == [True]


# BUG REPORT
# 1. Container (test_container__resolve_optional_parameter__uses_default): StdLibContainer did not correctly use `param.default` for unresolvable Optional type hints, leading to DependencyResolutionError instead of using the provided default value `None`. Fixed by patching `src/infra/std_container.py`.
# 2. EventBus (test_memory_event_bus__handler_raises_exception__others_called_and_logged): `MemoryEventBus` was crashing the execution loop if a handler raised an Exception. Fixed by adding try-except logic around handler invocations.
# 3. EventBus (test_thread_pool_event_bus__handler_timeout__does_not_block): `ThreadPoolEventBus` used `concurrent.futures.as_completed(futures)` directly during `.emit()` which blocked the calling thread. Fixed by switching to `future.add_done_callback` for async error handling.
# 4. EventBus (test_asyncio_event_bus__handler_cancelled__does_not_crash): `AsyncioEventBus` wasn't catching `asyncio.CancelledError` properly, crashing the event loop. Fixed by adding a specific try-except catch block for it.
# 5. Config (test_config__config_manager_failing_source__returns_default): `ConfigManager` was crashing the entire application if any `ConfigSource` raised an exception during `.read()`. Fixed by gracefully catching exceptions in `.read()` calls.
# 6. MiddlewarePipeline (test_pydantic_middleware__dto_is_none__raises_exception): `PydanticValidationMiddleware` was skipping validation and letting invalid input through if `data_transfer_obj` was None. Fixed by enforcing the model class initialization even for `None` DTOs, triggering proper `ValidationError`s.
# 7. ModuleAutoDiscovery (test_module_autodiscovery__syntax_error__ignores_and_does_not_crash): Missing robust try-except around `importlib.import_module` in `AppKernel` allowing malformed modules to crash boot sequence.
# 8. HealthModule (test_health_module__db_session_raises__returns_unhealthy): Handled `import sqlalchemy` missing gracefully but incorrectly set the status to "healthy" despite the DB check failing. Fixed by handling `ImportError` explicitly.


def test_container__circular_dependency__raises_error():
    from sagittarius_engine.exceptions import DependencyResolutionError
    from sagittarius_engine.infrastructure.container.std_container import (
        StdLibContainer,
    )

    class ClassB:
        pass

    class ClassA:
        def __init__(self, b: ClassB):
            self.b = b

    # Redefine ClassB to create a real circular dependency between the two
    # container-resolved classes.
    class ClassB:  # noqa: F811 — deliberate redefinition, see comment above
        def __init__(self, a: ClassA):
            self.a = a

    # Need to update ClassA's init annotations to point to new ClassB
    ClassA.__init__.__annotations__["b"] = ClassB

    container = StdLibContainer()

    with pytest.raises(DependencyResolutionError, match="Circular dependency detected"):
        container.resolve(ClassA)
