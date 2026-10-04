"""Which mode is showing, and whether it may stop showing (`EPIC-008D`;
`TASK-043` E3).

A mode is one job of the application, a `RegionHost`. Navigation is a
request, not a command: the mode being left is asked `can_leave(source)`
first, so a mode with unsaved edits can refuse a click on the mode bar, and
can tell a click (`USER_INTENT`) from the shell restoring last session's mode
at start (`RESTORE`), when there is nothing to ask the user about.

The service knows mode ids and guards; it never touches a widget. The shell
listens to `mode_changed` and shows the host.
"""

from __future__ import annotations

from collections.abc import Callable
from enum import Enum

from PySide6.QtCore import QObject, Signal


class NavigationSource(Enum):
    """Why a mode change was asked for."""

    #: The user clicked a mode, pressed its shortcut or chose it in View.
    USER_INTENT = "user_intent"
    #: The shell restores the mode the last session ended in.
    RESTORE = "restore"


type LeaveGuard = Callable[[NavigationSource], bool]


def _always_leave(source: NavigationSource) -> bool:
    return True


class NavigationService(QObject):
    """Holds the current mode; asks before leaving it."""

    #: The mode now showing, after a change that went through.
    mode_changed = Signal(str)
    #: A change `can_leave` refused: (the mode kept, the mode asked for).
    navigation_refused = Signal(str, str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._guards: dict[str, LeaveGuard] = {}
        self._current: str | None = None

    @property
    def current(self) -> str | None:
        return self._current

    def modes(self) -> tuple[str, ...]:
        """Every registered mode id, in registration order."""
        return tuple(self._guards)

    def register(self, mode_id: str, can_leave: LeaveGuard | None = None) -> None:
        """Adds a mode. The first registered becomes current."""
        if mode_id in self._guards:
            raise ValueError(f"mode {mode_id!r} is already registered")
        self._guards[mode_id] = can_leave or _always_leave
        if self._current is None:
            self._current = mode_id
            self.mode_changed.emit(mode_id)

    def navigate(self, mode_id: str, source: NavigationSource) -> bool:
        """Shows `mode_id` unless the current mode refuses to be left.
        `True` when `mode_id` is showing afterwards."""
        if mode_id not in self._guards:
            raise ValueError(
                f"no mode {mode_id!r}; registered modes are {list(self._guards)}"
            )
        if mode_id == self._current:
            return True
        leaving = self._current
        if leaving is not None and not self._guards[leaving](source):
            self.navigation_refused.emit(leaving, mode_id)
            return False
        self._current = mode_id
        self.mode_changed.emit(mode_id)
        return True
