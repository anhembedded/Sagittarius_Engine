# Dependencies

Rewritten 2026-08-23 from the real `requirements.txt`/`requirements-dev.txt` — the previous
version omitted `sqlalchemy` entirely and claimed `PySide6` "is NOT a core dependency," which
`requirements.txt` itself contradicts.

## Runtime (`requirements.txt`)

Exhaustive as of 2026-08-23:

`cryptography`, `requests`, `aiohttp`, `python-binance`, `python-dotenv`, `loguru`,
`pytest>=7.0`, `pytest-cov>=4.0`, `cmd2>=4.0.0`, `pydantic`, `sqlalchemy`, `alembic`, `boto3`,
`azure-storage-blob`, `anyio`, `pytest-asyncio`, `PySide6`, `pyqtgraph`.

Notably: **`sqlalchemy` and `PySide6` are both real, top-level runtime dependencies** —
`sqlalchemy` backs the `persistence` extension (`DatabaseExtension`, `ISession`), `PySide6`
backs the `pyside_mvc` extension. Neither is optional/soft — a consuming app doesn't need to
declare them separately to use those extensions. (`pytest`/`pytest-cov`/`pytest-asyncio` are
also listed here rather than only in the dev file — check both if a dependency seems missing
from one.)

## Dev/test (`requirements-dev.txt`)

Check the file directly for the current exhaustive list — known to include `mypy`, `ruff`,
`bandit`, `pip-audit`, `build`, `twine` (used by the CI jobs in `.github/workflows/ci.yml`,
see `build.md`).

## Why this matters for `IConfig` specifically

`configuration.md` used to recommend `pydantic.BaseSettings` as *the* configuration pattern.
`pydantic` is a real dependency, but the engine's own shipped `IConfig` implementation
(`infrastructure/config/config_manager.py`'s `ConfigManager`) is a plain multi-source
JSON/env-var reader, **not** pydantic-based — see `configuration.md` for the corrected,
verified pattern.
