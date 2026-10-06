"""The sample app runs on the engine's shell (`EPIC-008D` acceptance)."""

from __future__ import annotations

import os
import threading
from collections.abc import Iterator

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
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

_RUNTIME_THREADS = ("SagittariusScheduler", "AsyncRuntimeLoop")


@pytest.fixture(autouse=True)
def no_leaked_runtime_threads() -> Iterator[None]:
    """`BUG-020`: `build_app()` boots a real `App`, which starts a scheduler
    and an async-runtime thread. Fails any test here that leaves one running.
    Autouse fixtures tear down last, so `config` has already stopped its app.
    """
    before = {t.ident for t in threading.enumerate()}
    yield
    leaked = [
        t.name
        for t in threading.enumerate()
        if t.ident not in before and t.name in _RUNTIME_THREADS
    ]
    assert not leaked, f"test left runtime threads running: {leaked}"


@pytest.fixture
def config(tmp_path) -> Iterator[IConfig]:
    app = build_app(db_url=f"sqlite:///{tmp_path / 'test.db'}")
    yield app.container.resolve(IConfig)
    app.stop()


def test_the_sample_window_has_the_standard_menus_and_its_mode(qtbot, config) -> None:
    owner = QObject()
    shell, log = build_sample_shell(QLabel("roster"), config, owner)
    qtbot.addWidget(shell)

    titles = [action.text().replace("&", "") for action in shell.menuBar().actions()]
    assert titles == ["File", "Edit", "View", "Tools", "Window", "Help"]
    assert shell.current_mode == "roster"
    log.append("started")
    assert log.rowCount() == 1


def test_the_options_page_applies_to_the_config(qtbot, config) -> None:
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


def test_tools_options_opens_with_the_general_page(qtbot, config) -> None:
    owner = QObject()
    shell, _ = build_sample_shell(QLabel("roster"), config, owner)
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
