from typing import Any

from sagittarius_engine.interfaces import IConfig


class DictConfig(IConfig):
    """
    @brief A simple implementation of IConfig that stores configurations in memory (Dictionary).

    @details Suitable for use in Tests or very small applications.

    @par Tutorial / Usage Example:
    @code
    config = DictConfig()
    config.set("db.host", "127.0.0.1")
    print(config.get("db.host"))
    @endcode
    """

    def __init__(self, initial_data: dict[str, Any] | None = None) -> None:
        """
        @brief Constructor.

        @param initial_data Optional initial dictionary to populate the configuration.
        """
        self._config: dict[str, Any] = initial_data if initial_data is not None else {}

    def get(self, key: str, default: Any = None, cast: type[Any] | None = None) -> Any:
        val = self._config.get(key, default)
        if cast is not None and val is not None and not isinstance(val, cast):
            try:
                return cast(val)
            except (ValueError, TypeError):
                return val
        return val

    def set(self, key: str, value: Any) -> None:
        """
        @brief Sets a configuration value.

        @param key The configuration key.
        @param value The configuration value to store.
        """
        self._config[key] = value

    def get_all(self) -> dict[str, Any]:
        """
        @brief Returns a copy of all configurations.
        """
        return dict(self._config)
