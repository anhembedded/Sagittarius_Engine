"""Each table's column order, widths and sort, remembered (`EPIC-008F`).

Microsoft (`ctrl-list-views`): a list view the user arranged comes back
arranged. `QHeaderView.saveState()` holds exactly that; this contributor
carries it through `ui_state`, one entry per registered view, keyed by an id
the consumer chooses and keeps stable.
"""

from __future__ import annotations

import base64
import binascii
import logging
from functools import partial

from PySide6.QtCore import QByteArray
from PySide6.QtWidgets import QHeaderView

from sagittarius_engine.extensions.ui_state.state_scope import (
    JsonValue,
    StateData,
    StateScope,
)

logger = logging.getLogger("App")

#: The `ui_state` owner every saved header lives under.
ITEM_VIEW_SCOPE_KEY = "workbench.item_views"


class ItemViewStateStore:
    """Captures and restores registered headers."""

    def __init__(self) -> None:
        self._headers: dict[str, QHeaderView] = {}

    @property
    def state_scope(self) -> StateScope:
        return StateScope(key=ITEM_VIEW_SCOPE_KEY)

    def register(self, view_id: str, header: QHeaderView) -> None:
        if view_id in self._headers:
            raise ValueError(f"a view {view_id!r} is already registered")
        self._headers[view_id] = header
        header.destroyed.connect(partial(self.unregister, view_id))

    def unregister(self, view_id: str) -> None:
        """Forgets a view; unknown ids are ignored."""
        self._headers.pop(view_id, None)

    def capture_state(self) -> StateData:
        captured: dict[str, JsonValue] = {}
        for view_id, header in self._headers.items():
            blob = bytes(header.saveState().data())
            captured[view_id] = base64.b64encode(blob).decode("ascii")
        return captured

    def restore_state(self, data: StateData) -> None:
        for view_id, header in self._headers.items():
            encoded = data.get(view_id)
            if not isinstance(encoded, str):
                continue
            try:
                blob = base64.b64decode(encoded, validate=True)
            except binascii.Error:
                logger.info(
                    "Table %r kept its default columns: unreadable state.", view_id
                )
                continue
            if not header.restoreState(QByteArray(blob)):
                logger.info(
                    "Table %r kept its default columns: state does not apply.", view_id
                )
