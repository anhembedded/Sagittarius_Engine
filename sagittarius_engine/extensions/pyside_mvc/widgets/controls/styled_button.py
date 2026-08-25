"""
@brief `StyledButton` — a `QPushButton` styled by role.
"""

from __future__ import annotations

from PySide6.QtWidgets import QPushButton, QWidget

from ..style import StyleRole, WidgetState, apply_role

#: Roles `StyledButton` accepts — the subset of `StyleRole` with a button
#: QSS block (`style._build_qss`'s accent-lookup dict). Passing a
#: non-button role raises `KeyError` from that lookup — fails fast rather
#: than silently rendering unstyled.
_BUTTON_ROLES = (
    StyleRole.PRIMARY_BUTTON,
    StyleRole.SECONDARY_BUTTON,
    StyleRole.DANGER_BUTTON,
)


class StyledButton(QPushButton):
    """A `QPushButton` styled by role (`PRIMARY_BUTTON`/`SECONDARY_BUTTON`/
    `DANGER_BUTTON`) — which flavour is tier-2 knowledge (varies per use,
    passed as a parameter), not something this class hardcodes."""

    def __init__(
        self,
        text: str = "",
        *,
        role: StyleRole = StyleRole.SECONDARY_BUTTON,
        parent: QWidget | None = None,
    ) -> None:
        if role not in _BUTTON_ROLES:
            raise ValueError(
                f"StyledButton role must be one of {_BUTTON_ROLES}, got {role}"
            )
        super().__init__(text, parent)
        self._role = role
        apply_role(self, role)

    def setEnabled(self, enabled: bool) -> None:
        super().setEnabled(enabled)
        # QSS is a static string, not a live binding — re-render the role's
        # disabled variant explicitly rather than relying on Qt's default
        # :disabled pseudo-state, which this role's QSS overrides anyway.
        apply_role(
            self,
            self._role,
            state=WidgetState.NORMAL if enabled else WidgetState.DISABLED,
        )
