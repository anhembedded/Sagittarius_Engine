from sagittarius_engine.interfaces import IMiddleware
from sagittarius_engine.kernel import MiddlewarePipeline


class DummyMiddleware(IMiddleware):
    def __init__(self, name: str, tracer: list):
        self._name = name
        self.tracer = tracer

    @property
    def name(self) -> str:
        return self._name

    def process(self, cmd_or_query, data_transfer_obj, next_handler):
        self.tracer.append(f"{self.name}_start")
        result = next_handler()
        self.tracer.append(f"{self.name}_end")
        return result


def test_middleware_pipeline_execution_order():
    pipeline = MiddlewarePipeline()
    tracer = []

    pipeline.add(DummyMiddleware("mw1", tracer))
    pipeline.add(DummyMiddleware("mw2", tracer))

    def final_handler():
        tracer.append("final")
        return "result"

    result = pipeline.execute("cmd", "data_transfer_obj", final_handler)

    assert result == "result"
    assert tracer == ["mw1_start", "mw2_start", "final", "mw2_end", "mw1_end"]


def test_transaction_middleware_commits_on_success():
    from unittest.mock import MagicMock

    from sagittarius_engine.extensions.persistence import ISession
    from sagittarius_engine.extensions.persistence.transaction_middleware import (
        TransactionMiddleware,
    )
    from sagittarius_engine.interfaces import IContainer

    mock_container = MagicMock(spec=IContainer)
    mock_session = MagicMock(spec=ISession)
    mock_container.resolve.return_value = mock_session

    middleware = TransactionMiddleware(mock_container)

    def next_handler():
        return "success"

    result = middleware.process(None, None, next_handler)

    assert result == "success"
    mock_session.commit.assert_called_once()
    mock_session.rollback.assert_not_called()


def test_transaction_middleware_rollbacks_on_exception():
    from unittest.mock import MagicMock

    import pytest

    from sagittarius_engine.extensions.persistence import ISession
    from sagittarius_engine.extensions.persistence.transaction_middleware import (
        TransactionMiddleware,
    )
    from sagittarius_engine.interfaces import IContainer

    mock_container = MagicMock(spec=IContainer)
    mock_session = MagicMock(spec=ISession)
    mock_container.resolve.return_value = mock_session

    middleware = TransactionMiddleware(mock_container)

    def next_handler():
        raise RuntimeError("Command failed")

    with pytest.raises(RuntimeError, match="Command failed"):
        middleware.process(None, None, next_handler)

    mock_session.rollback.assert_called_once()
    mock_session.commit.assert_not_called()


def test_core_boot_does_not_require_persistence_extension():
    """@brief Regression test for TASK-017 issue 3: the core engine must boot
    with no ImportError even when the database extension's dependency
    (sqlalchemy) is not installed — TransactionMiddleware moved out of core
    middleware/ into extensions/persistence/, which guards its own sqlalchemy
    import. Run in a subprocess with sqlalchemy sabotaged via sys.modules, the
    standard way to simulate "not installed" without needing a second venv."""
    import subprocess
    import sys

    script = (
        "import sys\n"
        "sys.modules['sqlalchemy'] = None\n"  # simulate sqlalchemy not installed
        "from sagittarius_engine.kernel import App\n"
        "from sagittarius_engine.infrastructure.container.std_container import StdLibContainer\n"
        "from sagittarius_engine.infrastructure.event_bus.memory_event_bus import MemoryEventBus\n"
        "app = App(StdLibContainer(), MemoryEventBus())\n"
        "app.boot()\n"
        "print('OK')\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, timeout=30
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "OK" in result.stdout


def test_middleware_pipeline_concurrent_execution():
    import concurrent.futures
    import random
    import time
    import uuid

    from sagittarius_engine.interfaces import IMiddleware
    from sagittarius_engine.kernel import MiddlewarePipeline

    class DummyConcurrentMiddleware(IMiddleware):
        def process(self, cmd_or_query, data_transfer_obj, next_handler):
            # Inject thread-specific data
            thread_id = str(uuid.uuid4())
            data_transfer_obj["thread_id"] = thread_id

            # Simulate some work / delay
            time.sleep(random.uniform(0.001, 0.005))

            result = next_handler()

            # Verify state is not contaminated
            assert data_transfer_obj["thread_id"] == thread_id

            # Simulate more work
            time.sleep(random.uniform(0.001, 0.005))

            # Verify again
            assert data_transfer_obj["thread_id"] == thread_id

            return result

    pipeline = MiddlewarePipeline()
    pipeline.add(DummyConcurrentMiddleware())

    def execute_request():
        dto = {}

        # final_handler takes no arguments in MiddlewarePipeline
        def final_handler():
            # simulate work
            time.sleep(random.uniform(0.001, 0.005))
            return dto["thread_id"]

        return pipeline.execute("cmd", dto, final_handler)

    num_requests = 100
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        futures = [executor.submit(execute_request) for _ in range(num_requests)]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]

    # Assert exactly 100 successful responses
    assert len(results) == num_requests
    # Assert no state contamination (all IDs are unique)
    assert len(set(results)) == num_requests


def test_timing_middleware_process(capsys):
    from sagittarius_engine.middleware.timing_middleware import TimingMiddleware

    middleware = TimingMiddleware()

    class DummyCommand:
        pass

    cmd = DummyCommand()

    def next_handler():
        return "success_result"

    result = middleware.process(cmd, None, next_handler)

    assert result == "success_result"

    captured = capsys.readouterr()
    assert "[TimingMiddleware] DummyCommand executed in" in captured.out
    assert "ms" in captured.out


def test_logging_middleware_fallback_on_missing_logger(capsys):
    from unittest.mock import MagicMock

    from sagittarius_engine.interfaces import IContainer
    from sagittarius_engine.middleware.logging_middleware import LoggingMiddleware

    mock_container = MagicMock(spec=IContainer)
    mock_container.resolve.side_effect = Exception("Logger not found")

    middleware = LoggingMiddleware(mock_container)

    class DummyCommand:
        pass

    cmd = DummyCommand()

    def next_handler():
        return "success_result"

    result = middleware.process(cmd, None, next_handler)

    assert result == "success_result"

    captured = capsys.readouterr()
    assert "[LoggingMiddleware] Starting DummyCommand" in captured.out
    assert "[LoggingMiddleware] Finished DummyCommand" in captured.out
