"""New commands take free keys; standard commands take the platform's
(`EPIC-008C`; Microsoft `inter-keyboard`)."""

from __future__ import annotations

import pytest
from PySide6.QtGui import QKeySequence

from sagittarius_engine.extensions.pyside_mvc.workbench import shortcut_problem


@pytest.mark.parametrize("key", ["Ctrl+R", "Ctrl+L", "Ctrl+3", "F8", "F9", "F12"])
def test_a_free_key_is_accepted(qapp, key: str) -> None:
    assert shortcut_problem(key) is None


@pytest.mark.parametrize(
    "key",
    # Ctrl+G, Q and T: Microsoft leaves them free, but KDE, GNOME or macOS
    # bind them (FindNext, Quit, AddTab), so they are not portable.
    [
        "Ctrl+Alt+R",
        "Ctrl+Shift+R",
        "Ctrl+B",
        "F5",
        "Alt+X",
        "Ctrl+G",
        "Ctrl+Q",
        "Ctrl+T",
    ],
)
def test_a_key_outside_the_free_set_is_refused(qapp, key: str) -> None:
    problem = shortcut_problem(key)
    assert problem is not None and "not free" in problem


def test_a_chord_is_refused(qapp) -> None:
    problem = shortcut_problem("Ctrl+K, Ctrl+R")
    assert problem is not None and "2 keystrokes" in problem


def test_a_standard_key_is_always_accepted(qapp) -> None:
    assert shortcut_problem(QKeySequence.StandardKey.Copy) is None
    assert shortcut_problem(None) is None
