"""A command's text says how to reach it and whether it asks for more
(`EPIC-008C`; Microsoft `cmd-menus`)."""

from __future__ import annotations

from sagittarius_engine.extensions.pyside_mvc.workbench import (
    ELLIPSIS,
    access_keys,
    plain_text,
    text_problems,
)


def test_one_access_key_and_a_literal_ampersand() -> None:
    assert access_keys("Save && &close") == ("c",)
    assert plain_text("Save && &close") == "Save & close"


def test_a_command_with_no_access_key_is_refused() -> None:
    (problem,) = text_problems("Start", needs_input=False)
    assert "0 access keys" in problem


def test_a_command_with_two_access_keys_is_refused() -> None:
    (problem,) = text_problems("&Start &now", needs_input=False)
    assert "2 access keys" in problem


def test_three_dots_are_not_an_ellipsis() -> None:
    problems = text_problems("&Options...", needs_input=False)
    assert any("U+2026" in problem for problem in problems)


def test_a_command_that_asks_for_more_ends_with_the_ellipsis() -> None:
    assert text_problems(f"&New order{ELLIPSIS}", needs_input=True) == ()
    (problem,) = text_problems("&New order", needs_input=True)
    assert "asks for more input" in problem


def test_a_command_that_acts_at_once_takes_no_ellipsis() -> None:
    (problem,) = text_problems(f"&Options{ELLIPSIS}", needs_input=False)
    assert "acts at once" in problem


def test_an_escaped_ampersand_before_the_marker_is_read_as_qt_reads_it() -> None:
    assert access_keys("Save &&&As") == ("a",)
    assert plain_text("Save &&&As") == "Save &As"
