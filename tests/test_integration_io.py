import os
import sys
import tempfile
from io import StringIO
from unittest.mock import patch

from sagittarius_engine.adapters.batch import BatchInputPort, BatchOutputPort
from sagittarius_engine.adapters.batch.const import FILE_TYPE_CSV
from sagittarius_engine.adapters.cli import CLIInputPort, CLIOutputPort

# Dummy implementations of required interfaces for the in-memory app
from sagittarius_engine.exceptions import DependencyResolutionError
from sagittarius_engine.extensions.cqrs import ICommand, IQuery
from sagittarius_engine.interfaces import IContainer, IEventBus, ILogger, IModule
from sagittarius_engine.kernel import App
from sagittarius_engine.kernel.app_runner import ApplicationRunner


class DummyContainer(IContainer):
    def bind(self, abstract: type, concrete: type) -> None:
        pass

    def singleton(self, abstract: type, instance_or_factory: type | object) -> None:
        pass

    def resolve(self, abstract):
        if abstract == ILogger:
            raise DependencyResolutionError("No logger")
        return abstract()

    def scoped(self, abstract: type, concrete: type) -> None:
        pass

    def create_scope(self):
        from contextlib import contextmanager

        @contextmanager
        def _noop():
            yield

        return _noop()


class DummyEventBus(IEventBus):
    def on(self, event_name, handler) -> None:
        pass

    def off(self, event_name, handler) -> None:
        pass

    def emit(self, event_name, data=None) -> None:
        pass


class TestCommand(ICommand):
    def execute(self, dto):
        return f"Executed command with id: {dto.get('id')}"


class TestQuery(IQuery):
    def execute(self, dto):
        return f"Executed query with name: {dto.get('name')}"


class DummyModule(IModule):
    def register(self, app: App) -> None:
        pass

    def boot(self, app: App) -> None:
        pass

    def shutdown(self, app: App) -> None:
        pass


def test_integration_cli_flow():
    # Setup App
    app = App(DummyContainer(), DummyEventBus())
    app.use(DummyModule())
    app.boot()

    command_map = {"test_cmd": TestCommand}
    query_map = {"test_query": TestQuery}

    # We want to test two commands, but CLI run loop runs forever until exit.
    # To test integration, we will patch input port to simulate one command then exit.

    port_in = CLIInputPort()
    port_out = CLIOutputPort()

    runner = ApplicationRunner(app, port_in, port_out)

    # Simulate arguments
    test_args = ["prog", "test_cmd", "--id", "123"]
    with patch.object(sys, "argv", test_args):
        # We need to run receive once to get the dict, then second time it needs to exit to break loop.
        original_receive = port_in.receive

        call_count = 0

        def side_effect_receive():
            nonlocal call_count
            if call_count == 0:
                call_count += 1
                return original_receive()
            return {"command": "exit"}

        with patch.object(port_in, "receive", side_effect=side_effect_receive):
            with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
                runner.run_cli_loop(command_map, query_map)
                output = mock_stdout.getvalue()
                assert "Executed command with id: 123" in output


def test_integration_batch_flow():
    # Setup App
    app = App(DummyContainer(), DummyEventBus())
    app.use(DummyModule())
    app.boot()

    command_map = {"test_cmd": TestCommand}
    query_map = {}

    # Create temp files
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".csv") as in_tmp:
        in_tmp.write("command,id\ntest_cmd,456\ntest_cmd,789\n")
        in_tmp_path = in_tmp.name

    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as out_tmp:
        out_tmp_path = out_tmp.name

    tmp_dir = os.path.dirname(out_tmp_path)

    try:
        port_in = BatchInputPort(
            file_path=in_tmp_path,
            file_type=FILE_TYPE_CSV,
            base_path=os.path.dirname(in_tmp_path),
        )
        port_out = BatchOutputPort(output_path=out_tmp_path, base_path=tmp_dir)

        runner = ApplicationRunner(app, port_in, port_out)
        runner.run_cli_loop(command_map, query_map)

        with open(out_tmp_path) as f:
            lines = f.readlines()

        assert len(lines) == 2
        assert "Executed command with id: 456" in lines[0]
        assert "Executed command with id: 789" in lines[1]
    finally:
        os.remove(in_tmp_path)
        os.remove(out_tmp_path)
