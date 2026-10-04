"""A command is refused at declaration when its shape is wrong
(`EPIC-008C`)."""

from __future__ import annotations

import pytest

from sagittarius_engine.extensions.pyside_mvc.workbench import (
    ELLIPSIS,
    ActionConfirmation,
    ActionDeclarationError,
    ActionDescriptor,
)


def test_a_well_formed_command_is_accepted(qapp) -> None:
    descriptor = ActionDescriptor(
        action_id="trade.new_order",
        text=f"&New order{ELLIPSIS}",
        menu_path=("T&rade",),
        shortcut="F9",
        needs_input=True,
    )
    assert descriptor.plain_text == f"New order{ELLIPSIS}"


def test_a_command_in_no_menu_is_refused(qapp) -> None:
    with pytest.raises(ActionDeclarationError, match="is in no menu"):
        ActionDescriptor(action_id="x", text="&Start", menu_path=())


def test_a_menu_title_without_an_access_key_is_refused(qapp) -> None:
    with pytest.raises(ActionDeclarationError, match="0 access keys"):
        ActionDescriptor(action_id="x", text="&Start", menu_path=("Trade",))


def test_a_shortcut_outside_the_free_set_is_refused(qapp) -> None:
    with pytest.raises(ActionDeclarationError, match="not free"):
        ActionDescriptor(
            action_id="x", text="&Start", menu_path=("&Bots",), shortcut="Ctrl+Alt+S"
        )


@pytest.mark.parametrize("answer", ["OK", "Yes", "&Ok"])
def test_a_confirmation_answering_ok_or_yes_is_refused(answer: str) -> None:
    with pytest.raises(ActionDeclarationError, match="name the action"):
        ActionConfirmation(
            title="Stop bot",
            consequence="Its orders are cancelled.",
            accept_text=answer,
        )


def test_a_confirmation_with_no_consequence_is_refused() -> None:
    with pytest.raises(ActionDeclarationError, match="no consequence"):
        ActionConfirmation(title="Stop bot", consequence=" ", accept_text="Stop bot")
