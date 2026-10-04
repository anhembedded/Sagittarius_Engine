"""The sample app on the engine's `WorkbenchShell` (`EPIC-008D`/`008E`).

The smallest real consumer of the workbench: one mode (the roster), one
Options page and one Output channel. It shows the wiring order a consuming
application follows — registry, shell, modes, pages and channels, then
`finish_setup()` — without any of that application's vocabulary reaching the
engine.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QCheckBox, QFormLayout, QWidget

from sagittarius_engine.extensions.pyside_mvc import (
    ActionRegistry,
    LogListModel,
    MessageBoxConfirmer,
    OutputChannel,
    OutputPane,
    RegionHost,
    RegionKind,
    ShellMode,
    SurfaceDeclaration,
    WorkbenchShell,
)
from sagittarius_engine.interfaces.i_config import IConfig

APPLICATION_NAME = "Student Management"
ABOUT_TEXT = "The Sagittarius Engine sample application."
ROSTER_MODE = "roster"
COMPACT_KEY = "ui.compact_roster"
_PLACES = {"workspace": RegionKind.CENTRAL}


class GeneralOptionsPage:
    """Tools → Options → General: one check box backed by the config."""

    def __init__(self, config: IConfig) -> None:
        self._config = config
        self._box = QCheckBox("&Compact roster rows")
        self._box.setChecked(self._saved())
        self._listener: Callable[[], None] | None = None
        self._box.toggled.connect(self._edited)
        self._widget = QWidget()
        QFormLayout(self._widget).addRow(self._box)

    @property
    def title(self) -> str:
        return "General"

    def widget(self) -> QWidget:
        return self._widget

    def apply(self) -> None:
        self._config.set(COMPACT_KEY, self._box.isChecked())

    def revert(self) -> None:
        self._box.setChecked(self._saved())

    def is_dirty(self) -> bool:
        return self._box.isChecked() != self._saved()

    def validation_message(self) -> str | None:
        return None

    def set_change_listener(self, listener: Callable[[], None]) -> None:
        self._listener = listener

    def _saved(self) -> bool:
        return bool(self._config.get(COMPACT_KEY, False))

    def _edited(self, checked: bool) -> None:
        if self._listener is not None:
            self._listener()


def build_sample_shell(
    roster_view: QWidget, config: IConfig, action_owner: QObject
) -> tuple[WorkbenchShell, LogListModel]:
    """The window with the roster as its one mode. Returns the shell and the
    Output channel's model, which the caller appends its messages to."""
    registry = ActionRegistry(action_owner, MessageBoxConfirmer())
    shell = WorkbenchShell(
        registry, application_name=APPLICATION_NAME, about_text=ABOUT_TEXT
    )
    host = RegionHost(SurfaceDeclaration(ROSTER_MODE, frozenset(_PLACES)), _PLACES)
    host.place_widget("workspace", roster_view)
    shell.add_mode(ShellMode(ROSTER_MODE, "&Roster", host))
    shell.add_options_page(GeneralOptionsPage(config))
    log = LogListModel()
    pane = OutputPane()
    pane.add_channel(OutputChannel("app", APPLICATION_NAME, log))
    shell.set_output_pane(pane)
    shell.finish_setup()
    return shell, log
