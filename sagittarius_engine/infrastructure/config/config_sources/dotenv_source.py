import os
from typing import Any

from sagittarius_engine.infrastructure.config.config_source import ConfigSource

try:
    from dotenv import load_dotenv

    DOTENV_INSTALLED = True
except ImportError:
    DOTENV_INSTALLED = False


class DotenvSource(ConfigSource):
    """
    @brief Configuration source from a .env file.

    @details Uses the `python-dotenv` package to load the .env file into os.environ.
    If `python-dotenv` is not installed, it falls back to parsing the file manually.

    @par Requirement:
    It is recommended to install `python-dotenv`.

    @par Tutorial / Usage Example:
    @code
    config = ConfigManager()
    config.add_source(DotenvSource(".env"))

    db_host = config.get("DB_HOST")
    @endcode
    """

    def __init__(self, filepath: str = ".env") -> None:
        """
        @brief Constructor.
        @param filepath The path to the .env file.
        """
        self.filepath = filepath

    @property
    def label(self) -> str:
        return f"dotenv:{self.filepath}"

    def read(self) -> dict[str, Any]:
        """@brief Reads the configuration from the .env file."""
        if not os.path.exists(self.filepath):
            return {}

        result = {}
        if DOTENV_INSTALLED:
            load_dotenv(dotenv_path=self.filepath)
            # After load_dotenv, the vars are in os.environ.
            # We don't want to return all of os.environ, only what we read,
            # but load_dotenv doesn't return a dict directly.
            # We can use dotenv_values for a dict.
            from dotenv import dotenv_values

            return dotenv_values(dotenv_path=self.filepath)
        # Fallback manual parsing
        with open(self.filepath) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip()
                    # Remove quotes if present
                    if (v.startswith('"') and v.endswith('"')) or (
                        v.startswith("'") and v.endswith("'")
                    ):
                        v = v[1:-1]
                    result[k] = v
                    # Also set in os.environ for consistency
                    os.environ[k] = v
        return result
