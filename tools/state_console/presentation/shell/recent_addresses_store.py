"""`RecentAddressesStore` — `EPIC-008B` §3.

Owns persistence for the connect flow's "recent addresses" list
(`reference/handoff.md` §5: "five most recent, most-recent-first, persisted
between runs"). Tier 3 per `ui-architecture.md`: what a "recent address" is
and how long the list gets are this tool's own concern, not the kit's.

Wraps a `QSettings` instance rather than constructing its own: production
code points it at the real, named settings file
(`default_recent_addresses_settings()`); tests point it at a throwaway
`QSettings(path, QSettings.Format.IniFormat)` so a test run never touches a
developer's real recent-address history.
"""

from __future__ import annotations

from PySide6.QtCore import QSettings

#: Single settings key -- a JSON-free, native QSettings string list.
_KEY = "connect/recentAddresses"

#: `reference/handoff.md` §5: "five most recent".
_MAX_RECENTS = 5


def default_recent_addresses_settings() -> QSettings:
    return QSettings("SagittariusEngine", "StateConsole")


class RecentAddressesStore:
    def __init__(self, settings: QSettings) -> None:
        self._settings = settings

    def list(self) -> list[str]:
        value: object = self._settings.value(_KEY, [])
        if isinstance(value, str):
            # A single remaining entry comes back as a bare str, not a
            # 1-element list -- QSettings' own well-known stringlist quirk.
            return [value] if value else []
        if isinstance(value, list):
            return list(value)
        return []

    def record(self, address: str) -> None:
        addresses = [a for a in self.list() if a != address]
        addresses.insert(0, address)
        self._settings.setValue(_KEY, addresses[:_MAX_RECENTS])
