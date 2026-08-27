from abc import ABC, abstractmethod
from typing import Any


class ConfigSource(ABC):
    """
    @brief Configuration Source (Dict, Env, Json).
    """

    @abstractmethod
    def read(self) -> dict[str, Any]:
        """
        @brief Reads the configuration from the source.
        @return A dictionary containing the configuration data.
        """
        ...

    @property
    def label(self) -> str:
        """
        @brief What `ConfigManager.sources()` (`EPIC-007B`) reports for a key this
        source supplied.

        @details Concrete with a generic default (the class name) — a source with
        nothing distinguishing about it (`DictSource`) has no honest reason to override
        this; one with a real identity (a filepath, an env prefix) does.
        """
        return type(self).__name__
