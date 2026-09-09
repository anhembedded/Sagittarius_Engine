"""`ConsoleShellView` — `EPIC-007E` §3's navigation shell. Real
`PresenterManager` wiring, real `App`: every screen is lazily instantiated
on first navigation and torn down cleanly on `shutdown()`."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")
pytest.importorskip("websockets")

from PySide6.QtCore import QSettings  # noqa: E402

from sagittarius_engine.extensions.pyside_mvc import configure_app_qml  # noqa: E402
from sagittarius_engine.extensions.state_console import (  # noqa: E402
    StateConsoleExtension,
)
from sagittarius_engine.infrastructure.container.std_container import (  # noqa: E402
    StdLibContainer,
)
from sagittarius_engine.infrastructure.event_bus.memory_event_bus import (  # noqa: E402
    MemoryEventBus,
)
from sagittarius_engine.kernel import App  # noqa: E402
from tools.state_console.app import build_console_app  # noqa: E402
from tools.state_console.infrastructure.console_mvc_extension import (  # noqa: E402
    ConsoleMvcExtension,
)
from tools.state_console.presentation.shell.console_shell_view import (  # noqa: E402
    SCREENS,
    ConsoleShellView,
)
from tools.state_console.presentation.shell.recent_addresses_store import (  # noqa: E402
    RecentAddressesStore,
)
from tools.state_console.presentation.theme.icon_loader import (  # noqa: E402
    SimpleIconLoader,
)
from tools.state_console.presentation.theme.palette import (  # noqa: E402
    STATE_CONSOLE_ICON_PALETTE,
    STATE_CONSOLE_PALETTE,
)

#: A closed local port -- ConsoleConnectionExtension fails fast against it
#: (OSError on connect) and emits ConsoleFailed rather than hanging, so the
#: shell can be built and torn down without a real server.
_UNREACHABLE_URI = "ws://127.0.0.1:1"


@pytest.fixture(scope="module", autouse=True)
def _configure_theme():
    configure_app_qml(
        STATE_CONSOLE_PALETTE, SimpleIconLoader(), STATE_CONSOLE_ICON_PALETTE
    )


@pytest.fixture
def app():
    # boot=False: see build_console_app()'s own docstring -- the shell (and
    # ShellPresenter's subscription to the connection's events) must exist
    # before boot() fires the one-shot connection attempt, or a fast
    # failure fires and vanishes unseen. _make_shell() below is every
    # test's way of doing that in the right order.
    application = build_console_app(
        _UNREACHABLE_URI, extra_extensions=[ConsoleMvcExtension()], boot=False
    )
    yield application
    application.stop()


def _make_shell(app, tmp_path=None, *, recent_addresses=None) -> ConsoleShellView:
    """@brief Builds the shell and boots the app, in the order `main.py`
    itself now uses -- see `build_console_app()`'s docstring. Defaults to a
    throwaway `QSettings` file rather than the real, persisted one so a
    test run never touches (or is affected by) a developer's real recent
    address history."""
    if recent_addresses is None and tmp_path is not None:
        settings = QSettings(str(tmp_path / "recents.ini"), QSettings.Format.IniFormat)
        recent_addresses = RecentAddressesStore(settings)
    shell = ConsoleShellView(app.container, recent_addresses=recent_addresses)
    app.boot()
    return shell


@pytest.fixture
def server_app():
    server_ext = StateConsoleExtension(port=0)
    server = App(StdLibContainer(), MemoryEventBus())
    server.use(server_ext)
    server.boot()
    assert server_ext._server is not None  # noqa: SLF001
    assert server_ext._server.ready_event.wait(timeout=3.0)  # noqa: SLF001
    yield server_ext
    server.stop()


@pytest.fixture
def reachable_app(server_app):
    uri = f"ws://{server_app.host}:{server_app._server.port}"  # noqa: SLF001
    application = build_console_app(
        uri, extra_extensions=[ConsoleMvcExtension()], boot=False
    )
    yield application
    application.stop()


@pytest.fixture
def cold_app():
    """@brief `uri=None`: `ConsoleConnectionExtension.boot()` no-ops (no
    target to connect to), so the shell starts and stays `COLD` until the
    connect flow's own `requestConnect()` gives it one -- `EPIC-008B` §3."""
    application = build_console_app(
        None, extra_extensions=[ConsoleMvcExtension()], boot=False
    )
    yield application
    application.stop()


def test_shell_registers_all_five_screens_and_defaults_to_overview(
    qtbot, app, tmp_path
):
    shell = _make_shell(app, tmp_path)
    qtbot.addWidget(shell)

    assert set(shell.manager._registry.keys()) == {name for name, _ in SCREENS}  # noqa: SLF001
    assert shell.shell_presenter.rail_view_model.activeSectionId == "overview"


def test_navigating_lazily_instantiates_and_switches_screens(qtbot, app, tmp_path):
    shell = _make_shell(app, tmp_path)
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
    assert shell.shell_presenter.rail_view_model.activeSectionId == "events"

    shell.navigate_to("tasks")
    for _ in range(5):
        qtbot.wait(1)
    assert registry["tasks"]["presenter_instance"] is not None
    assert shell.shell_presenter.rail_view_model.activeSectionId == "tasks"


def test_shell_shutdown_disposes_every_instantiated_presenter(qtbot, app, tmp_path):
    shell = _make_shell(app, tmp_path)
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
    assert shell.shell_presenter._disposed is True  # noqa: SLF001


def test_rail_sections_match_screens_in_order(qtbot, app, tmp_path):
    shell = _make_shell(app, tmp_path)
    qtbot.addWidget(shell)

    sections = shell.shell_presenter.rail_view_model.sections
    assert [(s["id"], s["label"]) for s in sections] == list(SCREENS)


def test_band_reaches_failed_against_an_unreachable_target(qtbot, app, tmp_path):
    """`EPIC-008B` §2's connection band, driven end to end: a real
    `ConsoleConnectionExtension` attempt against `_UNREACHABLE_URI` reaches
    `ConsoleFailed`, and `ShellPresenter` reflects that as the `FAILED`
    state with a `Retry` action -- `reference/handoff.md` §4's copy table."""
    shell = _make_shell(app, tmp_path)
    qtbot.addWidget(shell)

    band = shell.shell_presenter.band_view_model
    qtbot.waitUntil(lambda: band.state == "failed", timeout=3000)

    assert band.actionLabel == "Retry"
    assert band.targetText == _UNREACHABLE_URI
    assert "ECONNREFUSED" in band.stateNote


def test_band_reaches_reading_against_a_real_server(qtbot, reachable_app, tmp_path):
    shell = _make_shell(reachable_app, tmp_path)
    qtbot.addWidget(shell)

    band = shell.shell_presenter.band_view_model
    qtbot.waitUntil(lambda: band.state == "reading", timeout=3000)

    assert band.actionLabel == "Detach"
    assert band.heartbeatTicks


def test_detach_action_on_the_band_moves_the_connection_to_stale(
    qtbot, reachable_app, tmp_path
):
    """`ShellPresenter._on_action_requested()`'s READING/IDLE branch: the
    band's own `Detach` button, not a test calling the extension directly."""
    shell = _make_shell(reachable_app, tmp_path)
    qtbot.addWidget(shell)

    band = shell.shell_presenter.band_view_model
    qtbot.waitUntil(lambda: band.state == "reading", timeout=3000)

    band.requestAction()

    qtbot.waitUntil(lambda: band.state == "stale", timeout=3000)
    assert band.actionLabel == "Reconnect"


def test_retry_action_on_the_band_reconnects_to_the_same_target(
    qtbot, reachable_app, tmp_path
):
    """`ShellPresenter._on_action_requested()`'s FAILED/STALE branch: after
    detaching, the band's own `Reconnect` button re-attaches without a new
    address -- `connect_to()` reusing the last `uri`."""
    shell = _make_shell(reachable_app, tmp_path)
    qtbot.addWidget(shell)

    band = shell.shell_presenter.band_view_model
    qtbot.waitUntil(lambda: band.state == "reading", timeout=3000)

    band.requestAction()  # Detach
    qtbot.waitUntil(lambda: band.state == "stale", timeout=3000)

    band.requestAction()  # Reconnect
    qtbot.waitUntil(lambda: band.state == "reading", timeout=3000)


def test_rail_badges_reflect_signal_counts_from_a_real_snapshot(
    qtbot, reachable_app, tmp_path
):
    shell = _make_shell(reachable_app, tmp_path)
    qtbot.addWidget(shell)

    band = shell.shell_presenter.band_view_model
    qtbot.waitUntil(lambda: band.state == "reading", timeout=3000)

    sections = {
        s["id"]: s["badgeCount"] for s in shell.shell_presenter.rail_view_model.sections
    }
    # A vanilla server with no seeded faults: every badge starts at zero.
    assert sections == {
        "overview": 0,
        "events": 0,
        "container": 0,
        "tasks": 0,
        "signals": 0,
    }


# ------------------------------------------------------- EPIC-008B §3: connect flow


def test_cold_shell_shows_no_target_and_an_attach_action(qtbot, cold_app, tmp_path):
    shell = _make_shell(cold_app, tmp_path)
    qtbot.addWidget(shell)

    band = shell.shell_presenter.band_view_model
    assert band.state == "cold"
    assert band.actionLabel == "Attach…"


def test_attach_action_opens_the_connect_flow_cold(qtbot, cold_app, tmp_path):
    shell = _make_shell(cold_app, tmp_path)
    qtbot.addWidget(shell)

    shell.shell_presenter.band_view_model.requestAction()

    assert shell._body_content.currentWidget() is shell._connect_flow  # noqa: SLF001
    assert shell.shell_presenter.connect_flow_view_model.changingTarget is False


def test_submitting_an_address_connects_closes_the_overlay_and_records_it(
    qtbot, cold_app, tmp_path, server_app
):
    """The connect flow's own `requestConnect()` Slot end to end: a real
    `connect_to()` call, the overlay closing once `ConsoleConnecting`
    actually fires, and the address landing in `RecentAddressesStore`."""
    uri = f"ws://{server_app.host}:{server_app._server.port}"  # noqa: SLF001
    shell = _make_shell(cold_app, tmp_path)
    qtbot.addWidget(shell)

    shell.shell_presenter.band_view_model.requestAction()  # opens, cold
    shell.shell_presenter.connect_flow_view_model.requestConnect(uri)

    band = shell.shell_presenter.band_view_model
    qtbot.waitUntil(lambda: band.state == "reading", timeout=3000)

    assert shell._body_content.currentWidget() is shell._stack  # noqa: SLF001
    assert shell.shell_presenter._recent_addresses.list() == [uri]  # noqa: SLF001


def test_change_target_link_opens_an_overlay_that_cancel_closes_without_disconnecting(
    qtbot, reachable_app, tmp_path
):
    shell = _make_shell(reachable_app, tmp_path)
    qtbot.addWidget(shell)

    band = shell.shell_presenter.band_view_model
    qtbot.waitUntil(lambda: band.state == "reading", timeout=3000)
    target = band.targetText

    band.requestChangeTarget()

    flow_vm = shell.shell_presenter.connect_flow_view_model
    assert shell._body_content.currentWidget() is shell._connect_flow  # noqa: SLF001
    assert flow_vm.changingTarget is True
    assert flow_vm.currentTarget == target

    flow_vm.requestCancel()

    assert shell._body_content.currentWidget() is shell._stack  # noqa: SLF001
    # Cancel never touched the connection -- still reading the same target.
    assert band.state == "reading"
    assert band.targetText == target


def test_recent_addresses_persist_across_shells_via_the_injected_store(
    qtbot, cold_app, tmp_path
):
    settings = QSettings(str(tmp_path / "recents.ini"), QSettings.Format.IniFormat)
    store = RecentAddressesStore(settings)
    store.record("ws://127.0.0.1:9001")

    shell = ConsoleShellView(cold_app.container, recent_addresses=store)
    qtbot.addWidget(shell)
    cold_app.boot()

    shell.shell_presenter.band_view_model.requestAction()

    recents = shell.shell_presenter.connect_flow_view_model.recents
    assert [r["address"] for r in recents] == ["ws://127.0.0.1:9001"]
