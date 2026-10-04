"""A mode change is a request the current mode may refuse (`EPIC-008D`;
`TASK-043` E3)."""

from __future__ import annotations

import pytest

from sagittarius_engine.extensions.pyside_mvc import NavigationService, NavigationSource


def test_the_first_mode_is_current(qapp) -> None:
    service = NavigationService()
    service.register("market")
    service.register("trade")

    assert service.current == "market"
    assert service.modes() == ("market", "trade")


def test_navigate_changes_the_mode_and_says_so(qtbot) -> None:
    service = NavigationService()
    service.register("market")
    service.register("trade")

    with qtbot.waitSignal(service.mode_changed) as changed:
        assert service.navigate("trade", NavigationSource.USER_INTENT)

    assert changed.args == ["trade"]
    assert service.current == "trade"


def test_the_mode_being_left_can_refuse_and_learns_why(qtbot) -> None:
    asked: list[NavigationSource] = []

    def unsaved_edits(source: NavigationSource) -> bool:
        asked.append(source)
        return False

    service = NavigationService()
    service.register("bots", can_leave=unsaved_edits)
    service.register("market")

    with qtbot.waitSignal(service.navigation_refused) as refused:
        assert not service.navigate("market", NavigationSource.USER_INTENT)

    assert refused.args == ["bots", "market"]
    assert service.current == "bots"
    assert asked == [NavigationSource.USER_INTENT]


def test_an_unknown_mode_is_refused(qapp) -> None:
    service = NavigationService()
    service.register("market")
    with pytest.raises(ValueError, match="no mode 'trade'"):
        service.navigate("trade", NavigationSource.USER_INTENT)


def test_a_mode_registered_twice_is_refused(qapp) -> None:
    service = NavigationService()
    service.register("market")
    with pytest.raises(ValueError, match="already registered"):
        service.register("market")
