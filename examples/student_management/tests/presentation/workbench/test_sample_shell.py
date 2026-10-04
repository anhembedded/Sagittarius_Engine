"""The sample app runs on the engine's shell (`EPIC-008D` acceptance)."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QObject, QTimer
from PySide6.QtWidgets import QApplication, QCheckBox, QLabel

from examples.student_management.main import build_app
from examples.student_management.presentation.workbench.sample_shell import (
    COMPACT_KEY,
    GeneralOptionsPage,
    build_sample_shell,
)
from sagittarius_engine.extensions.pyside_mvc import OptionsDialog
from sagittarius_engine.interfaces.i_config import IConfig


def _config(tmp_path) -> IConfig:
    app = build_app(db_url=f"sqlite:///{tmp_path / 'test.db'}")
    return app.container.resolve(IConfig)


def test_the_sample_window_has_the_standard_menus_and_its_mode(qtbot, tmp_path) -> None:
    owner = QObject()
    shell, log = build_sample_shell(QLabel("roster"), _config(tmp_path), owner)
    qtbot.addWidget(shell)

    titles = [action.text().replace("&", "") for action in shell.menuBar().actions()]
    assert titles == ["File", "Edit", "View", "Tools", "Window", "Help"]
    assert shell.current_mode == "roster"
    log.append("started")
    assert log.rowCount() == 1


def test_the_options_page_applies_to_the_config(qtbot, tmp_path) -> None:
    config = _config(tmp_path)
    page = GeneralOptionsPage(config)
    qtbot.addWidget(page.widget())
    page.set_change_listener(lambda: None)

    box = page.widget().findChild(QCheckBox)
    assert box is not None
    box.setChecked(True)
    assert page.is_dirty()
    page.apply()

    assert config.get(COMPACT_KEY) is True
    assert not page.is_dirty()


def test_tools_options_opens_with_the_general_page(qtbot, tmp_path) -> None:
    owner = QObject()
    shell, _ = build_sample_shell(QLabel("roster"), _config(tmp_path), owner)
    qtbot.addWidget(shell)
    seen: list[str] = []

    def close_it() -> None:
        dialog = QApplication.activeModalWidget()
        assert isinstance(dialog, OptionsDialog)
        seen.append(dialog.windowTitle())
        dialog.reject()

    QTimer.singleShot(0, close_it)
    shell.show_options()

    assert seen == ["Options"]
