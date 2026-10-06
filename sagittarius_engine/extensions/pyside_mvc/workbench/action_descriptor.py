"""One command, declared once (`EPIC-008C`).

A command is what a user can do: Place order, Sync history, Reset layout. On
a Windows desktop it is one `QAction` that its menu entry, its toolbar button
and its shortcut all share, so its text, icon, enabled and checked state
cannot drift between them (Qt, "Actions"; Microsoft, `cmd-menus`). An
extension declares it here, as data; `ActionRegistry` validates it and builds
the action, the way `ContributionRegistry` treats a contributed widget.

`menu_path` is mandatory: every command is in a menu, because a command
reachable only from a toolbar or a shortcut cannot be found (`cmd-toolbars`).
`surface_id`, `toolbar` and `group` are the consumer's opaque identities, as
in `ContributionDescriptor`.
"""

from __future__ import annotations

from dataclasses import dataclass

from sagittarius_engine.extensions.pyside_mvc.workbench.action_text import (
    plain_text,
    text_problems,
)
from sagittarius_engine.extensions.pyside_mvc.workbench.shortcut_policy import (
    Shortcut,
    shortcut_problem,
)

#: Answers a confirmation must not offer: they name no consequence
#: (Microsoft, `mess-confirm`: "use specific responses").
_VAGUE_ANSWERS = frozenset({"ok", "yes", "no"})


class ActionDeclarationError(ValueError):
    """A command was declared in a shape the workbench refuses."""


@dataclass(frozen=True, slots=True)
class ActionConfirmation:
    """The question a risky command asks before it runs.

    `consequence` is a sentence that names what will happen ("Every open
    order on Binance Futures is cancelled and live trading turns off.").
    `accept_text` is the specific verb ("Stop everything"), never OK or Yes;
    the reject answer is the default button, so Enter and Esc are both safe.
    """

    title: str
    consequence: str
    accept_text: str
    reject_text: str = "Cancel"

    def __post_init__(self) -> None:
        for answer in (self.accept_text, self.reject_text):
            if plain_text(answer).strip().lower() in _VAGUE_ANSWERS:
                raise ActionDeclarationError(
                    f"confirmation {self.title!r} answers {answer!r}; name "
                    "the action instead ('Stop bot', 'Delete data')"
                )
        if not self.consequence.strip():
            raise ActionDeclarationError(
                f"confirmation {self.title!r} names no consequence"
            )


@dataclass(frozen=True, slots=True)
class ActionDescriptor:
    """A command one extension offers."""

    #: Unique across the application. Opaque to the workbench.
    action_id: str
    #: Menu text: sentence case, one `&` access key, "…" iff `needs_input`.
    text: str
    #: The menus it sits in, outermost first, each with its own access key:
    #: `("&Trade",)`, `("&View", "&Toolbars")`.
    menu_path: tuple[str, ...]
    #: A toolbar place of its surface, or `None` for menu only.
    toolbar: str | None = None
    shortcut: Shortcut | None = None
    #: A name the consumer's icon loader resolves; `None` shows text.
    icon_name: str | None = None
    checkable: bool = False
    #: The command asks for more before it acts (a dialog, a file picker).
    needs_input: bool = False
    confirm: ActionConfirmation | None = None
    #: The mode it belongs to, or `None` for one present in every mode.
    surface_id: str | None = None
    #: The group of related commands it belongs to in its menu. A menu shows
    #: each group together, in the order its first command was contributed,
    #: with one separator between adjacent groups (MS `cmd-menus`). `None` is
    #: a group too: the commands that name none.
    group: str | None = None

    def __post_init__(self) -> None:
        problems = list(text_problems(self.text, needs_input=self.needs_input))
        if not self.menu_path:
            problems.append(
                f"{self.action_id!r} is in no menu; every command is in a menu"
            )
        for title in self.menu_path:
            problems.extend(text_problems(title, needs_input=False))
        shortcut_issue = shortcut_problem(self.shortcut)
        if shortcut_issue is not None:
            problems.append(shortcut_issue)
        if problems:
            raise ActionDeclarationError(
                f"action {self.action_id!r}: " + "; ".join(problems)
            )

    @property
    def plain_text(self) -> str:
        """The text as the user reads it, without access-key markers."""
        return plain_text(self.text)
