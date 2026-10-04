"""The menu bar, built from the registry each time a menu opens (`EPIC-008D`).

Windows order (MS `cmd-menus`): File, Edit, View, the application's own
menus, Tools, Window, Help. Each menu is filled when it is about to show, so
it lists exactly the commands of the mode now showing: a command of another
mode is not on screen, and neither are its access keys. A top-level menu with
nothing in it for this mode is disabled, never hidden.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu, QMenuBar

from sagittarius_engine.extensions.pyside_mvc.workbench.access_key_assignment import (
    assign_access_keys,
)
from sagittarius_engine.extensions.pyside_mvc.workbench.action_registry import (
    ActionRegistry,
)
from sagittarius_engine.extensions.pyside_mvc.workbench.action_text import (
    access_keys,
    plain_text,
)

FILE_MENU = "&File"
EDIT_MENU = "&Edit"
VIEW_MENU = "&View"
TOOLS_MENU = "&Tools"
WINDOW_MENU = "&Window"
HELP_MENU = "&Help"
TOOLBARS_MENU = "T&oolbars"
#: Before the application's own menus, then after them.
_LEADING = (FILE_MENU, EDIT_MENU, VIEW_MENU)
_TRAILING = (TOOLS_MENU, WINDOW_MENU, HELP_MENU)

type Path = tuple[str, ...]
#: Extra toggles a menu shows after its registered commands, by path.
type ExtraActions = Callable[[Path], Sequence[QAction]]


def _empty(menu: QMenu) -> None:
    """Clears `menu` and destroys its submenus.

    `QMenu.clear()` deletes the actions the menu owns but not the submenu
    `QMenu`s, which are its children; refilled on every open, they would
    accumulate. Detached first so a lookup by object name never finds one
    still waiting for `deleteLater()`.
    """
    for action in menu.actions():
        submenu = action.menu()
        if isinstance(submenu, QMenu):
            _empty(submenu)
            submenu.setParent(None)
            submenu.deleteLater()
    menu.clear()


def menu_order(top_titles: Sequence[str]) -> tuple[str, ...]:
    """The standard menus around the application's own, in Windows order."""
    standard = {plain_text(title) for title in (*_LEADING, *_TRAILING)}
    own = [title for title in top_titles if plain_text(title) not in standard]
    return (*_LEADING, *dict.fromkeys(own), *_TRAILING)


class MenuBarBuilder:
    """Fills a `QMenuBar` from an `ActionRegistry` for the current mode."""

    def __init__(
        self,
        menu_bar: QMenuBar,
        registry: ActionRegistry,
        current_mode: Callable[[], str | None],
        extra_actions: ExtraActions,
    ) -> None:
        self._menu_bar = menu_bar
        self._registry = registry
        self._current_mode = current_mode
        self._extra_actions = extra_actions
        self._top: dict[str, QMenu] = {}

    def build(self) -> None:
        """Creates the top-level menus once; their contents follow the mode."""
        tops = [path[0] for path in self._registry.menu_paths()]
        for title in menu_order(tops):
            menu = self._menu_bar.addMenu(title)
            menu.setObjectName(f"menu::{plain_text(title)}")
            menu.aboutToShow.connect(
                lambda menu=menu, title=title: self._fill(menu, (title,))
            )
            self._top[title] = menu
        self.refresh_enabled()

    def menu(self, title: str) -> QMenu:
        return self._top[title]

    def empty_all(self) -> None:
        """Empties every menu, on a mode change.

        A filled `QMenu` keeps its `QAction`s, and Qt treats an action held
        by a menu whose menu-bar entry is enabled as live for shortcuts. So a
        menu filled in the mode just left would keep that mode's commands
        reachable, or make a key two modes share ambiguous. Each menu refills
        when it next opens.
        """
        for menu in self._top.values():
            _empty(menu)

    def refresh_enabled(self) -> None:
        """Disables a top-level menu with nothing in it for this mode."""
        for title, menu in self._top.items():
            menu.setEnabled(self._has_content((title,)))

    def fill_now(self, title: str) -> QMenu:
        """Fills one top-level menu immediately, as opening it would."""
        menu = self._top[title]
        self._fill(menu, (title,))
        return menu

    # -- filling ---------------------------------------------------------------

    def _fill(self, menu: QMenu, path: Path) -> None:
        _empty(menu)
        mode = self._current_mode()
        for action in self._registry.menu_actions(path, mode):
            menu.addAction(action)
        for child in self._children(path):
            submenu = menu.addMenu(child)
            submenu.setObjectName(f"menu::{plain_text(child)}")
            self._fill(submenu, (*path, child))
        extras = list(self._extra_actions(path))
        if extras:
            menu.addSeparator()
            taken = [key for item in menu.actions() for key in access_keys(item.text())]
            labels = assign_access_keys([plain_text(a.text()) for a in extras], taken)
            for action, label in zip(extras, labels, strict=True):
                action.setText(label)
                menu.addAction(action)

    def _children(self, path: Path) -> tuple[str, ...]:
        depth = len(path)
        mode = self._current_mode()
        children: dict[str, None] = {}
        for candidate in self._registry.menu_paths():
            if len(candidate) > depth and candidate[:depth] == path:
                if self._has_actions(candidate[: depth + 1], mode):
                    children[candidate[depth]] = None
        return tuple(children)

    def _has_actions(self, prefix: Path, mode: str | None) -> bool:
        return any(
            path[: len(prefix)] == prefix and self._registry.menu_actions(path, mode)
            for path in self._registry.menu_paths()
        )

    def _has_content(self, path: Path) -> bool:
        return self._has_actions(path, self._current_mode()) or bool(
            self._extra_actions(path)
        )
