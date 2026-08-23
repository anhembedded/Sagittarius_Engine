import os
from typing import Any

from sagittarius_engine.infrastructure.config.config_source import ConfigSource


class EnvSource(ConfigSource):
    """
    @brief Configuration source from Environment Variables.

    @details Example: EnvSource(prefix="APP_") will read the `APP_HOST` variable and store it with the key `HOST`.
    """

    def __init__(self, prefix: str = "") -> None:
        """
        @brief Constructor.
        @param prefix The prefix to filter environment variables by.
        """
        self.prefix = prefix

    def read(self) -> dict[str, Any]:
        """@brief Reads the configuration from environment variables."""
        result = {}
        for k, v in os.environ.items():
            if k.startswith(self.prefix):
                key = k[len(self.prefix) :]
                result[key] = v
        return result
