import json
import os
import sys
import tempfile
from io import StringIO
from unittest.mock import MagicMock, patch

import pytest

from sagittarius_engine.adapters.batch import BatchInputPort, BatchOutputPort
from sagittarius_engine.adapters.batch.const import FILE_TYPE_CSV, FILE_TYPE_JSON
from sagittarius_engine.adapters.cli import CLIInputPort, CLIOutputPort
from sagittarius_engine.exceptions import PathTraversalError
from sagittarius_engine.kernel.app_runner import (
    COMMAND_KEY,
    EXIT_COMMAND,
    ApplicationRunner,
)


def test_cli_input_port_normal():
    port = CLIInputPort()
    test_args = ["prog", "add", "--id", "SV001", "--name", "Alice"]
    with patch.object(sys, "argv", test_args):
        result = port.receive()
    assert result == {"command": "add", "id": "SV001", "name": "Alice"}


def test_cli_input_port_missing_command():
    port = CLIInputPort()
    test_args = ["prog"]
    with patch.object(sys, "argv", test_args), pytest.raises(SystemExit):
        port.receive()


def test_cli_input_port_extra_unknown():
    port = CLIInputPort()
    test_args = ["prog", "add", "unknown_arg"]
    with patch.object(sys, "argv", test_args), pytest.raises(SystemExit):
        port.receive()


def test_cli_output_port_present():
    port = CLIOutputPort()
    result = {"id": 1, "name": "Test"}
    with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
        port.present(result)
        assert "'id': 1" in mock_stdout.getvalue()
        assert "'name': 'Test'" in mock_stdout.getvalue()


def test_cli_output_port_present_error():
    port = CLIOutputPort()
    error = ValueError("Something went wrong")
    with patch("sys.stderr", new_callable=StringIO) as mock_stderr:
        port.present_error(error)
        assert "ERROR: Something went wrong" in mock_stderr.getvalue()


def test_batch_input_port_csv_normal():
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".csv") as tmp:
        tmp.write("id,name\n1,Alice\n2,Bob\n")
        tmp_path = tmp.name

    try:
        port = BatchInputPort(
            file_path=tmp_path,
            file_type=FILE_TYPE_CSV,
            base_path=os.path.dirname(tmp_path),
        )

        row1 = port.receive()
        assert row1 == {"id": "1", "name": "Alice"}

        row2 = port.receive()
        assert row2 == {"id": "2", "name": "Bob"}

        row3 = port.receive()
        assert row3 == {COMMAND_KEY: EXIT_COMMAND}
    finally:
        os.remove(tmp_path)


def test_batch_input_port_csv_empty():
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".csv") as tmp:
        tmp.write("")
        tmp_path = tmp.name

    try:
        port = BatchInputPort(
            file_path=tmp_path,
            file_type=FILE_TYPE_CSV,
            base_path=os.path.dirname(tmp_path),
        )

        row1 = port.receive()
        assert row1 == {COMMAND_KEY: EXIT_COMMAND}
    finally:
        os.remove(tmp_path)


def test_batch_input_port_json_normal():
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as tmp:
        data = [{"id": "1", "name": "Alice"}, {"id": "2", "name": "Bob"}]
        json.dump(data, tmp)
        tmp_path = tmp.name

    try:
        port = BatchInputPort(
            file_path=tmp_path,
            file_type=FILE_TYPE_JSON,
            base_path=os.path.dirname(tmp_path),
        )

        row1 = port.receive()
        assert row1 == {"id": "1", "name": "Alice"}

        row2 = port.receive()
        assert row2 == {"id": "2", "name": "Bob"}

        row3 = port.receive()
        assert row3 == {COMMAND_KEY: EXIT_COMMAND}
    finally:
        os.remove(tmp_path)


def test_batch_input_port_json_invalid(caplog):
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as tmp:
        tmp.write('{"invalid": "format"}')  # not an array
        tmp_path = tmp.name

    try:
        mock_logger = MagicMock()
        port = BatchInputPort(
            file_path=tmp_path,
            file_type=FILE_TYPE_JSON,
            base_path=os.path.dirname(tmp_path),
        )
        port.logger = mock_logger
        row1 = port.receive()

        assert row1 == {COMMAND_KEY: EXIT_COMMAND}
        mock_logger.error.assert_called_once_with(
            "JSON file must contain an array of objects"
        )
    finally:
        os.remove(tmp_path)


def test_batch_input_port_unsupported_file_type():
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as tmp:
        tmp.write("dummy content")
        tmp_path = tmp.name

    try:
        mock_logger = MagicMock()
        port = BatchInputPort(
            file_path=tmp_path,
            file_type="UNKNOWN_TYPE",
            base_path=os.path.dirname(tmp_path),
        )
        port.logger = mock_logger
        row = port.receive()

        assert row == {COMMAND_KEY: EXIT_COMMAND}
        mock_logger.error.assert_called_once_with("Unsupported file type: UNKNOWN_TYPE")
    finally:
        os.remove(tmp_path)


def test_batch_input_port_file_not_found():
    mock_logger = MagicMock()
    port = BatchInputPort(file_path="nonexistent_file.csv", file_type=FILE_TYPE_CSV)
    port.logger = mock_logger

    row = port.receive()

    assert row == {COMMAND_KEY: EXIT_COMMAND}
    mock_logger.error.assert_called_once_with(
        f"File not found: {os.path.realpath('nonexistent_file.csv')}"
    )


def test_batch_output_port():
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as tmp:
        tmp_path = tmp.name

    tmp_dir = os.path.dirname(tmp_path)

    try:
        port = BatchOutputPort(output_path=tmp_path, base_path=tmp_dir)

        # Test normal present
        port.present({"id": 1, "name": "Test"})

        # Test error present
        port.present_error(ValueError("Failed"))

        with open(tmp_path) as f:
            lines = f.readlines()

        assert len(lines) == 2
        assert json.loads(lines[0].strip()) == {"id": 1, "name": "Test"}
        assert lines[1].strip() == "ERROR: Failed"
    finally:
        os.remove(tmp_path)


def test_batch_output_port_path_traversal():
    with pytest.raises(PathTraversalError):
        BatchOutputPort(output_path="../../../etc/passwd", base_path="/tmp")

    with pytest.raises(PathTraversalError):
        BatchOutputPort(output_path="/etc/passwd", base_path="/tmp")

    # Should not raise exception
    port = BatchOutputPort(output_path="valid.txt", base_path="/tmp")
    assert port.output_path == os.path.realpath("/tmp/valid.txt")


def test_application_runner():
    mock_app = MagicMock()
    mock_input_port = MagicMock()
    mock_output_port = MagicMock()

    # Mock receive to return valid command, then exit command
    mock_input_port.receive.side_effect = [
        {"command": "add", "id": "1"},
        {"command": "get", "id": "2"},
        {"command": "unknown", "id": "3"},
        {"command": "exit"},
    ]
    # Setup App returns
    mock_app.dispatch.side_effect = ["Added", "Found"]

    runner = ApplicationRunner(
        app=mock_app, input_port=mock_input_port, output_port=mock_output_port
    )

    class DummyCommand:
        pass

    class DummyQuery:
        pass

    command_map = {"add": DummyCommand}
    query_map = {"get": DummyQuery}

    runner.run_cli_loop(command_map, query_map)

    # Assert App was called properly
    mock_app.dispatch.assert_any_call(DummyCommand, {"command": "add", "id": "1"})
    mock_app.dispatch.assert_any_call(DummyQuery, {"command": "get", "id": "2"})

    # Assert Output Port was called
    mock_output_port.present.assert_any_call("Added")
    mock_output_port.present.assert_any_call("Found")

    # Check error presentation for unknown command
    assert mock_output_port.present_error.call_count == 1
    error_arg = mock_output_port.present_error.call_args[0][0]
    assert isinstance(error_arg, ValueError)
    assert str(error_arg) == "Unknown command: unknown"


def test_application_runner_exception():
    mock_app = MagicMock()
    mock_input_port = MagicMock()
    mock_output_port = MagicMock()

    # Setup app to raise exception
    mock_input_port.receive.side_effect = [
        {"command": "add", "id": "1"},
        {"command": "exit"},
    ]
    mock_app.dispatch.side_effect = Exception("Crash")

    runner = ApplicationRunner(
        app=mock_app, input_port=mock_input_port, output_port=mock_output_port
    )

    class DummyCommand:
        pass

    command_map = {"add": DummyCommand}

    runner.run_cli_loop(command_map, {})

    assert mock_output_port.present_error.call_count == 1
    error_arg = mock_output_port.present_error.call_args[0][0]
    assert isinstance(error_arg, Exception)
    assert str(error_arg) == "Crash"


def test_application_runner_keyboard_interrupt():
    mock_app = MagicMock()
    mock_input_port = MagicMock()
    mock_output_port = MagicMock()

    mock_input_port.receive.side_effect = KeyboardInterrupt()

    runner = ApplicationRunner(
        app=mock_app, input_port=mock_input_port, output_port=mock_output_port
    )

    runner.run_cli_loop({}, {})

    mock_output_port.present.assert_not_called()
    mock_output_port.present_error.assert_not_called()
