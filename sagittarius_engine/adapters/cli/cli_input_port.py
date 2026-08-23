import argparse
import sys
from typing import Any

from sagittarius_engine.adapters.cli.const import COMMAND_KEY
from sagittarius_engine.base.base_input_port import BaseInputPort


class CLIInputPort(BaseInputPort):
    """
    @brief CLI Input Port that uses argparse to parse command-line arguments.
    """

    def receive(self) -> dict[str, Any]:
        """
        @brief Parses CLI arguments into a dictionary.

        @return A dictionary containing the command and any parsed arguments.
        """
        parser = argparse.ArgumentParser(description="CLI Input Port")
        parser.add_argument(COMMAND_KEY, type=str, help="The command to execute")
        args, unknown = parser.parse_known_args()
        result = {COMMAND_KEY: getattr(args, COMMAND_KEY)}
        i = 0
        while i < len(unknown):
            arg = unknown[i]
            if arg.startswith("--"):
                key = arg[2:]
                value = None
                if i + 1 < len(unknown) and (not unknown[i + 1].startswith("--")):
                    value = unknown[i + 1]
                    i += 1
                result[key] = value
            else:
                sys.exit(f"error: unrecognized arguments: {arg}")
            i += 1
        return result
