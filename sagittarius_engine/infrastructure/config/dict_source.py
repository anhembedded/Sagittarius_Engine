from typing import Any

from sagittarius_engine.infrastructure.config.config_source import ConfigSource


class DictSource(ConfigSource):
    """
    @brief Configuration source from a provided Python Dictionary.
    """

    def __init__(self, data: dict[str, Any]) -> None:
        """
        @brief Constructor.
        @param data The dictionary data.
        """
        self.data = data

    def read(self) -> dict[str, Any]:
        """@brief Reads the configuration from the dictionary."""
        return self.data
