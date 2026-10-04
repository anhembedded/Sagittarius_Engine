"""Every command in the application, validated once and built once
(`EPIC-008C`).

Extensions contribute `ActionDescriptor`s at boot; this registry refuses the
shapes that would look fine and be wrong — a duplicate id, two commands on
one key, a standard key bound to a new meaning, two items in one menu on one
access key — and builds one `QAction` per command. A presenter later `bind`s
its handler and, optionally, the signals that enable or check it. The shell
asks `menu_actions()` and `toolbar_actions()` to build its menus and toolbars
(`EPIC-008D`), so the menu bar is the complete catalogue by construction.

Scope: a command with `surface_id=None` exists in every mode and conflicts
with everything; two commands of two different modes may share a key or an
access key, because only one mode is active at a time.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import partial

from PySide6.QtCore import QObject, SignalInstance
from PySide6.QtGui import QAction, QIcon, QKeySequence
from PySide6.QtWidgets import QApplication

from sagittarius_engine.extensions.pyside_mvc.workbench.action_confirmation import (
    IActionConfirmer,
)
from sagittarius_engine.extensions.pyside_mvc.workbench.action_descriptor import (
    ActionDeclarationError,
    ActionDescriptor,
)
from sagittarius_engine.extensions.pyside_mvc.workbench.action_text import (
    access_keys,
    plain_text,
)
from sagittarius_engine.extensions.pyside_mvc.workbench.shortcut_policy import (
    key_sequence,
)

logger = logging.getLogger("App")

_PORTABLE = QKeySequence.SequenceFormat.PortableText
_NATIVE = QKeySequence.SequenceFormat.NativeText

type ActionHandler = Callable[[bool], None]
type IconLoader = Callable[[str], QIcon]


@dataclass(slots=True)
class _Entry:
    descriptor: ActionDescriptor
    action: QAction
    keys: frozenset[str]
    handler: ActionHandler | None = field(default=None)


def _scopes_meet(first: str | None, second: str | None) -> bool:
    return first is None or second is None or first == second


def _bound_keys(descriptor: ActionDescriptor) -> frozenset[str]:
    if descriptor.shortcut is None:
        return frozenset()
    if isinstance(descriptor.shortcut, QKeySequence.StandardKey):
        bindings = QKeySequence.keyBindings(descriptor.shortcut)
        return frozenset(binding.toString(_PORTABLE) for binding in bindings)
    return frozenset({key_sequence(descriptor.shortcut).toString(_PORTABLE)})


def _standard_bindings() -> dict[str, str]:
    """Every key the platform gives a standard meaning, with that meaning."""
    meanings: dict[str, str] = {}
    for standard in QKeySequence.StandardKey:
        if standard is QKeySequence.StandardKey.UnknownKey:
            continue
        for binding in QKeySequence.keyBindings(standard):
            meanings.setdefault(binding.toString(_PORTABLE), standard.name)
    return meanings


class ActionRegistry:
    """Builds and owns one `QAction` per contributed command."""

    def __init__(
        self,
        owner: QObject,
        confirmer: IActionConfirmer,
        icon_loader: IconLoader | None = None,
    ) -> None:
        self._owner = owner
        self._confirmer = confirmer
        self._icon_loader = icon_loader
        self._entries: dict[str, _Entry] = {}
        self._standard = _standard_bindings()

    # -- contributing ------------------------------------------------------

    def contribute(self, descriptor: ActionDescriptor) -> QAction:
        """Validates `descriptor` against every command so far and builds its
        action, disabled until a handler is bound."""
        keys = _bound_keys(descriptor)
        self._refuse_conflicts(descriptor, keys)
        action = self._build(descriptor)
        self._entries[descriptor.action_id] = _Entry(descriptor, action, keys)
        return action

    def _refuse_conflicts(
        self, descriptor: ActionDescriptor, keys: frozenset[str]
    ) -> None:
        if descriptor.action_id in self._entries:
            raise ActionDeclarationError(
                f"action id {descriptor.action_id!r} is already contributed"
            )
        if isinstance(descriptor.shortcut, str):
            for key in keys:
                meaning = self._standard.get(key)
                if meaning is not None:
                    raise ActionDeclarationError(
                        f"{descriptor.action_id!r} binds {key}, which the "
                        f"platform reserves for {meaning}; use "
                        f"QKeySequence.StandardKey.{meaning} if it is that command"
                    )
        for other in self._entries.values():
            if _scopes_meet(other.descriptor.surface_id, descriptor.surface_id):
                self._refuse_against(descriptor, keys, other)

    def _refuse_against(
        self, descriptor: ActionDescriptor, keys: frozenset[str], other: _Entry
    ) -> None:
        shared = keys & other.keys
        if shared:
            raise ActionDeclarationError(
                f"{descriptor.action_id!r} and {other.descriptor.action_id!r} "
                f"both bind {sorted(shared)}"
            )
        for mine, theirs in zip(
            descriptor.menu_path, other.descriptor.menu_path, strict=False
        ):
            if plain_text(mine) != plain_text(theirs):
                return
            if mine != theirs:
                raise ActionDeclarationError(
                    f"menu {plain_text(mine)!r} is spelled {mine!r} by "
                    f"{descriptor.action_id!r} and {theirs!r} by "
                    f"{other.descriptor.action_id!r}; one menu has one access key"
                )
        if descriptor.menu_path != other.descriptor.menu_path:
            return
        if access_keys(descriptor.text) == access_keys(other.descriptor.text):
            raise ActionDeclarationError(
                f"{descriptor.text!r} and {other.descriptor.text!r} share an "
                f"access key in menu {descriptor.menu_path!r}"
            )

    def _build(self, descriptor: ActionDescriptor) -> QAction:
        action = QAction(descriptor.text, self._owner)
        action.setObjectName(f"action::{descriptor.action_id}")
        action.setCheckable(descriptor.checkable)
        action.setEnabled(False)
        tooltip = descriptor.plain_text
        if descriptor.shortcut is not None:
            sequence = key_sequence(descriptor.shortcut)
            action.setShortcut(sequence)
            native = sequence.toString(_NATIVE)
            if native:
                tooltip = f"{tooltip} ({native})"
        action.setToolTip(tooltip)
        if descriptor.icon_name is not None and self._icon_loader is not None:
            action.setIcon(self._icon_loader(descriptor.icon_name))
        action.triggered.connect(partial(self._run, descriptor.action_id))
        return action

    # -- binding -------------------------------------------------------------

    def bind(
        self,
        action_id: str,
        handler: ActionHandler,
        *,
        enabled: SignalInstance | None = None,
        checked: SignalInstance | None = None,
    ) -> None:
        """Connects the presenter that performs `action_id`. `handler` gets
        the checked state (always `False` for a plain command)."""
        entry = self._entry(action_id)
        if entry.handler is not None:
            raise ActionDeclarationError(f"action {action_id!r} is already bound")
        entry.handler = handler
        entry.action.setEnabled(True)
        if enabled is not None:
            enabled.connect(entry.action.setEnabled)
        if checked is not None:
            checked.connect(entry.action.setChecked)

    def unbound(self) -> tuple[str, ...]:
        """Contributed commands nothing performs, in contribution order."""
        return tuple(
            action_id
            for action_id, entry in self._entries.items()
            if entry.handler is None
        )

    def report_unbound(self) -> tuple[str, ...]:
        """Logs the unbound commands once, at the end of boot, and returns
        them: a menu entry that does nothing is a defect, not a quiet one."""
        missing = self.unbound()
        if missing:
            logger.warning(
                "%d command(s) have no handler and stay disabled: %s",
                len(missing),
                ", ".join(missing),
            )
        return missing

    # -- reading -------------------------------------------------------------

    def action(self, action_id: str) -> QAction:
        return self._entry(action_id).action

    def menu_actions(
        self, menu_path: tuple[str, ...], surface_id: str | None
    ) -> tuple[QAction, ...]:
        """The actions of one menu in mode `surface_id`, in contribution order."""
        return tuple(
            entry.action
            for entry in self._entries.values()
            if entry.descriptor.menu_path == menu_path
            and _scopes_meet(entry.descriptor.surface_id, surface_id)
        )

    def menu_paths(self) -> tuple[tuple[str, ...], ...]:
        """Every distinct menu path, in first-contribution order."""
        return tuple(
            dict.fromkeys(
                entry.descriptor.menu_path for entry in self._entries.values()
            )
        )

    def toolbar_actions(self, surface_id: str, toolbar: str) -> tuple[QAction, ...]:
        """The actions a mode's toolbar place shows, in contribution order."""
        return tuple(
            entry.action
            for entry in self._entries.values()
            if entry.descriptor.toolbar == toolbar
            and _scopes_meet(entry.descriptor.surface_id, surface_id)
        )

    # -- running -------------------------------------------------------------

    def _entry(self, action_id: str) -> _Entry:
        entry = self._entries.get(action_id)
        if entry is None:
            raise ActionDeclarationError(f"no action {action_id!r} was contributed")
        return entry

    def _run(self, action_id: str) -> None:
        # The checked state is read from the action rather than taken from
        # `triggered(bool)`: PySide picks the zero-argument overload for a
        # `partial`, so the argument would never arrive.
        entry = self._entries[action_id]
        if entry.handler is None:
            return
        checked = entry.action.isChecked()
        confirmation = entry.descriptor.confirm
        if confirmation is not None and not self._confirmer.confirm(
            QApplication.activeWindow(), confirmation
        ):
            if entry.descriptor.checkable:
                entry.action.blockSignals(True)
                entry.action.setChecked(not checked)
                entry.action.blockSignals(False)
            return
        entry.handler(checked)
