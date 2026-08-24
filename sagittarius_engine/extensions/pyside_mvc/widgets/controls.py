"""
@brief Token-styled leaf controls — each a direct, single-inheritance
subclass of its own distinct Qt base (`QPushButton`/`QCheckBox`/
`QLineEdit`/`QDateTimeEdit`). No shared base among them: unlike `Surface`'s
family, there is no real "Control" abstraction these four have in common
beyond "calls `apply_role()` once" — inventing one would either force a
second QObject lineage onto a class that already has one (forbidden, see
`widgets.style`) or add a non-Qt mixin for no behaviour beyond what
composition already gives for free.

`DateTimeField` extends `QDateTimeEdit`, not `StyledField` — `QDateTimeEdit`
inherits `QAbstractSpinBox`, not `QLineEdit` (verified against the real Qt
class hierarchy; an earlier draft of this package's architecture had this
wrong for the same reason its first draft wrongly gave `Overlay` two Qt
bases).
"""

from __future__ import annotations

from PySide6.QtWidgets import QCheckBox, QDateTimeEdit, QLineEdit, QPushButton, QWidget

from .style import StyleRole, WidgetState, apply_role

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


class StyledCheckBox(QCheckBox):
    """A `QCheckBox` styled for readable label text on this app's dark
    surfaces — Qt's own indicator box is left native, not reskinned; no
    consumer of the QML `StyledCheck` this replaces needed a custom
    indicator glyph, so this doesn't build one speculatively."""

    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        apply_role(self, StyleRole.CHECKBOX)


class StyledField(QLineEdit):
    """A `QLineEdit` styled to match the app's field chrome."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        apply_role(self, StyleRole.FIELD)


class DateTimeField(QDateTimeEdit):
    """A `QDateTimeEdit` styled to match the app's field chrome — the
    QtWidgets replacement for the QML kit's hand-rolled `DateTimePicker`
    (400 LOC), most of which was reimplementing calendar/time popups
    `QDateTimeEdit` already provides."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        apply_role(self, StyleRole.FIELD)
