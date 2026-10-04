"""Which keys a new command may take (`EPIC-008C`).

Microsoft's keyboard guidance (`inter-keyboard`, `cmd-menus`): standard
shortcuts keep their meaning everywhere, so a command that *is* Copy, Save
or Find takes the platform's own binding through `QKeySequence.StandardKey`
and never a hand-typed one; a new command takes a key the platform leaves
free, and never `Ctrl+Alt`, which is `AltGr` on many keyboard layouts and
types a character instead.

The free set is the one those guidelines leave unassigned, less every key
another platform Qt supports reserves, so a command that boots on Windows
boots everywhere: `Ctrl` with J, K, L, M or R, `Ctrl` with a digit, and F7,
F8, F9 and F12. Microsoft also leaves Ctrl+G, Ctrl+Q and Ctrl+T free, but
`QKeySequence` binds them to FindNext, Quit and AddTab on KDE, GNOME and
macOS. Anything else a command needs is reached through its menu's access
keys.
"""

from __future__ import annotations

from PySide6.QtGui import QKeySequence

_PORTABLE = QKeySequence.SequenceFormat.PortableText
#: Every key a new command may take, in Qt's portable spelling.
_FREE_KEYS = frozenset(
    {f"Ctrl+{key}" for key in "JKLMR0123456789"} | {"F7", "F8", "F9", "F12"}
)

type Shortcut = QKeySequence.StandardKey | str


def key_sequence(shortcut: Shortcut) -> QKeySequence:
    """The sequence `shortcut` binds on this platform."""
    return QKeySequence(shortcut)


def shortcut_problem(shortcut: Shortcut | None) -> str | None:
    """Why `shortcut` may not be bound to a new command, or `None`."""
    if shortcut is None or isinstance(shortcut, QKeySequence.StandardKey):
        return None
    sequence = QKeySequence(shortcut)
    if sequence.count() != 1:
        return (
            f"{shortcut!r} is {sequence.count()} keystrokes; a command's "
            "shortcut is one"
        )
    if sequence.toString(_PORTABLE) in _FREE_KEYS:
        return None
    return (
        f"{shortcut!r} is not free for a new command: use a "
        "QKeySequence.StandardKey for a standard command, or one of Ctrl+J, "
        "K, L, M, R, Ctrl+digit, F7, F8, F9, F12 (never Ctrl+Alt)"
    )
