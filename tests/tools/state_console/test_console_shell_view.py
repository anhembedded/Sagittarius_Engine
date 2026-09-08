"""`ConsoleShellView` — `EPIC-007E` §3's navigation shell. Real
`PresenterManager` wiring, real `App`: every screen is lazily instantiated
on first navigation and torn down cleanly on `shutdown()`."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")
pytest.importorskip("websockets")

from sagittarius_engine.extensions.pyside_mvc import configure_app_qml  # noqa: E402
from tools.state_console.app import build_console_app  # noqa: E402
from tools.state_console.infrastructure.console_mvc_extension import (  # noqa: E402
    ConsoleMvcExtension,
)
from tools.state_console.presentation.shell.console_shell_view import (  # noqa: E402
    SCREENS,
    ConsoleShellView,
)
from tools.state_console.presentation.theme.icon_loader import (  # noqa: E402
    SimpleIconLoader,
)
from tools.state_console.presentation.theme.palette import (  # noqa: E402
    STATE_CONSOLE_ICON_PALETTE,
    STATE_CONSOLE_PALETTE,
)

#: A closed local port -- ConsoleConnectionExtension fails fast against it
#: (OSError on connect) and emits ConsoleDetached rather than hanging, so
#: the shell can be built and torn down without a real server.
_UNREACHABLE_URI = "ws://127.0.0.1:1"


@pytest.fixture(scope="module", autouse=True)
def _configure_theme():
    configure_app_qml(
        STATE_CONSOLE_PALETTE, SimpleIconLoader(), STATE_CONSOLE_ICON_PALETTE
    )


@pytest.fixture
def app():
    application = build_console_app(
        _UNREACHABLE_URI, extra_extensions=[ConsoleMvcExtension()]
    )
    yield application
    application.stop()


def test_shell_registers_all_five_screens_and_defaults_to_overview(qtbot, app):
    shell = ConsoleShellView(app.container)
    qtbot.addWidget(shell)

    assert set(shell.manager._registry.keys()) == {name for name, _ in SCREENS}  # noqa: SLF001
    assert shell._buttons["overview"].isChecked()  # noqa: SLF001
    for name, _ in SCREENS[1:]:
        assert not shell._buttons[name].isChecked()  # noqa: SLF001


def test_navigating_lazily_instantiates_and_switches_screens(qtbot, app):
    shell = ConsoleShellView(app.container)
    qtbot.addWidget(shell)
    shell.show()

    # Only "overview" has been instantiated so far (constructor default).
    registry = shell.manager._registry  # noqa: SLF001
    assert registry["overview"]["presenter_instance"] is not None
    assert registry["events"]["presenter_instance"] is None

    shell.navigate_to("events")
    for _ in range(5):
        qtbot.wait(1)

    assert registry["events"]["presenter_instance"] is not None
    assert shell._buttons["events"].isChecked()  # noqa: SLF001
    assert not shell._buttons["overview"].isChecked()  # noqa: SLF001

    shell.navigate_to("tasks")
    for _ in range(5):
        qtbot.wait(1)
    assert registry["tasks"]["presenter_instance"] is not None
    assert shell._buttons["tasks"].isChecked()  # noqa: SLF001


def test_shell_shutdown_disposes_every_instantiated_presenter(qtbot, app):
    shell = ConsoleShellView(app.container)
    qtbot.addWidget(shell)
    shell.navigate_to("container")
    shell.navigate_to("signals")

    registry = shell.manager._registry  # noqa: SLF001
    instantiated = [
        config["presenter_instance"]
        for config in registry.values()
        if config["presenter_instance"] is not None
    ]
    assert len(instantiated) >= 3  # overview (default) + container + signals

    shell.shutdown()

    for presenter in instantiated:
        assert presenter._disposed is True  # noqa: SLF001
