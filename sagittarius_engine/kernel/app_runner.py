from collections.abc import Mapping
from typing import Any

from sagittarius_engine.interfaces.i_input_port import IInputPort
from sagittarius_engine.interfaces.i_output_port import IOutputPort
from sagittarius_engine.kernel import App

COMMAND_KEY = "command"
EXIT_COMMAND = "exit"


class ApplicationRunner:
    """
    @brief ApplicationRunner orchestrates the execution of an application core via ports.
    """

    def __init__(
        self, app: App, input_port: IInputPort, output_port: IOutputPort
    ) -> None:
        self.app = app
        self.input_port = input_port
        self.output_port = output_port

    def run_cli_loop(
        self,
        command_map: Mapping[str, type] | None = None,
        query_map: Mapping[str, type] | None = None,
    ) -> None:
        """
        @brief Runs a loop processing commands from input_port and presenting to output_port.
        """
        cmd_map = command_map or {}
        q_map = query_map or {}

        while True:
            try:
                data = self.input_port.receive()
                if not data:
                    break

                command_name = data.get(COMMAND_KEY)
                if not isinstance(command_name, str) or command_name == EXIT_COMMAND:
                    break

                if command_name in cmd_map:
                    cmd_class = cmd_map[command_name]
                    result = self.execute(cmd_class, data)
                    self.output_port.present(result)
                elif command_name in q_map:
                    query_class = q_map[command_name]
                    result = self.query(query_class, data)
                    self.output_port.present(result)
                else:
                    self.output_port.present_error(
                        ValueError(f"Unknown command: {command_name}")
                    )

            except KeyboardInterrupt:
                break
            except Exception as e:
                self.output_port.present_error(e)

    def execute(self, command_class: type, dto: object | None = None) -> Any:
        """
        @brief Convenience method for executing a command via the app.
        """
        return self.app.dispatch(command_class, dto)

    def query(self, query_class: type, dto: object | None = None) -> Any:
        """
        @brief Convenience method for executing a query via the app.
        """
        return self.app.dispatch(query_class, dto)
