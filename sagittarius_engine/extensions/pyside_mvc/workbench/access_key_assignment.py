"""Access keys for labels the user names, not the code (`EPIC-008D`).

A dock's toggle in View carries the dock's title, which a consumer writes as
plain words ("Open orders"); a menu item without an access key cannot be
reached from the keyboard (MS `cmd-menus`). The View menu gives each such
label the first letter of a word not taken yet, then any free letter, the
way Windows applications assign them by hand.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence


def _candidates(label: str) -> list[int]:
    word_starts = [
        index
        for index, char in enumerate(label)
        if char.isalnum() and (index == 0 or not label[index - 1].isalnum())
    ]
    others = [index for index, char in enumerate(label) if char.isalnum()]
    return word_starts + [index for index in others if index not in word_starts]


def assign_access_keys(labels: Sequence[str], taken: Iterable[str]) -> tuple[str, ...]:
    """Each plain label with an `&` before a letter no other label, nor
    `taken`, uses. A label whose letters are all taken is returned with its
    ampersands escaped and no key."""
    used = {key.lower() for key in taken}
    marked: list[str] = []
    for label in labels:
        escaped = label.replace("&", "&&")
        choice = next(
            (index for index in _candidates(label) if label[index].lower() not in used),
            None,
        )
        if choice is None:
            marked.append(escaped)
            continue
        used.add(label[choice].lower())
        prefix = label[:choice].replace("&", "&&")
        suffix = label[choice:].replace("&", "&&")
        marked.append(f"{prefix}&{suffix}")
    return tuple(marked)
