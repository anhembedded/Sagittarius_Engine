import json
import os
from typing import Any

from sagittarius_engine.infrastructure.config.config_source import ConfigSource


class JsonSource(ConfigSource):
    """
    @brief Configuration source from a JSON file.
    """

    def __init__(self, filepath: str) -> None:
        """
        @brief Constructor.
        @param filepath The path to the JSON file.
        """
        self.filepath = filepath

    def read(self) -> dict[str, Any]:
        """@brief Reads the configuration from the JSON file."""
        if not os.path.exists(self.filepath):
            return {}
        try:
            with open(self.filepath) as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}
