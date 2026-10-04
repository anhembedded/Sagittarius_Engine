"""Each mode's dock and toolbar layout, remembered across runs (`EPIC-008B`).

`RegionHost` can save and restore its own layout, but nothing called it: the
reference consumer's users rearranged a mode and found it reset on the next
start. This is the caller. It is an `IStateContributor` (satisfied
structurally, like every contributor), so the layouts travel through the same
`ui_state` store as every other remembered value instead of a second file.

One entry per host, keyed `perspective::<surface_id>`, holding the host's
layout version beside the base64 of `QMainWindow.saveState()`. A version that
no longer matches restores the host's captured default and says so once: a
layout saved before a dock was renamed must not half-apply.
"""

from __future__ import annotations

import base64
import binascii
import logging
from collections.abc import Mapping
from functools import partial

from sagittarius_engine.extensions.pyside_mvc.runtime.region_host import RegionHost
from sagittarius_engine.extensions.ui_state.state_scope import (
    JsonValue,
    StateData,
    StateScope,
)

logger = logging.getLogger("App")

#: The `ui_state` owner every saved perspective lives under.
PERSPECTIVE_SCOPE_KEY = "workbench.perspectives"
_KEY_PREFIX = "perspective::"
_VERSION_FIELD = "version"
_STATE_FIELD = "state"


def perspective_key(surface_id: str) -> str:
    """The key one host's layout is stored under."""
    return f"{_KEY_PREFIX}{surface_id}"


class PerspectiveStore:
    """Captures and restores the layout of every registered host."""

    def __init__(self) -> None:
        self._hosts: dict[str, RegionHost] = {}

    @property
    def state_scope(self) -> StateScope:
        return StateScope(key=PERSPECTIVE_SCOPE_KEY)

    def register(self, host: RegionHost) -> None:
        """Remembers `host`'s layout from now on. One host per surface id."""
        if host.surface_id in self._hosts:
            raise ValueError(
                f"a host for surface {host.surface_id!r} is already registered; "
                "two hosts would overwrite each other's saved layout."
            )
        self._hosts[host.surface_id] = host
        # A host destroyed before shutdown must not be captured: its C++
        # object is gone and `saveState()` would raise.
        host.destroyed.connect(partial(self.unregister, host.surface_id))

    def unregister(self, surface_id: str) -> None:
        """Forgets a host; unknown ids are ignored."""
        self._hosts.pop(surface_id, None)

    def capture_state(self) -> StateData:
        captured: dict[str, JsonValue] = {}
        for surface_id, host in self._hosts.items():
            captured[perspective_key(surface_id)] = {
                _VERSION_FIELD: host.layout_version,
                _STATE_FIELD: base64.b64encode(host.save_perspective()).decode("ascii"),
            }
        return captured

    def restore_state(self, data: StateData) -> None:
        for surface_id, host in self._hosts.items():
            entry = data.get(perspective_key(surface_id))
            if isinstance(entry, Mapping):
                self._restore_one(host, entry)

    def _restore_one(self, host: RegionHost, entry: Mapping[str, JsonValue]) -> None:
        version = entry.get(_VERSION_FIELD)
        encoded = entry.get(_STATE_FIELD)
        if version != host.layout_version or not isinstance(encoded, str):
            logger.info(
                "Surface %r opened with its default layout: the saved one has "
                "layout version %r, this build has %d.",
                host.surface_id,
                version,
                host.layout_version,
            )
            host.reset_perspective()
            return
        try:
            blob = base64.b64decode(encoded, validate=True)
        except binascii.Error:
            logger.info(
                "Surface %r opened with its default layout: the saved one is "
                "not valid base64.",
                host.surface_id,
            )
            host.reset_perspective()
            return
        if not host.restore_perspective(blob):
            host.reset_perspective()
