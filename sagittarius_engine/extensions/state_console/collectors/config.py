"""`ConfigCollector` — `EPIC-007C`.

Thin: `mask_config()` already does the real work (`EPIC-007A`), built for
exactly this call site.
"""

from __future__ import annotations

from sagittarius_engine.extensions.audit.contracts import ConfigEntry, mask_config
from sagittarius_engine.extensions.state_console.collector import ISnapshotSection
from sagittarius_engine.interfaces.i_config import IConfig


class ConfigCollector(ISnapshotSection[tuple[ConfigEntry, ...]]):
    """
    @brief Config, masked by default.

    @param reveal Producer-side only, per `ADR-001` §2.8 — a client cannot
        turn this on by asking; it is set once, here, at construction, by
        whoever configured `StateConsoleExtension`.
    """

    def __init__(self, config: IConfig, *, reveal: bool = False) -> None:
        self._config = config
        self._reveal = reveal

    def collect(self) -> tuple[ConfigEntry, ...]:
        return mask_config(
            self._config.get_all(),
            reveal=self._reveal,
            sources=self._config.sources(),
        )
