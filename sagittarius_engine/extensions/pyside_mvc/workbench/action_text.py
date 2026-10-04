"""What a command's text must say about itself (`EPIC-008C`).

Two Windows conventions a reader of a menu relies on without noticing
(Microsoft Windows UX guidelines, `cmd-menus`):

* **One access key per item.** `&` marks it; `&&` is a literal ampersand.
  An item with none cannot be reached from the keyboard, and one with two
  is a typo Qt silently resolves to the first.
* **"…" means "asks for more before it acts".** U+2026, never three dots,
  and only then: "Options" opens a window and takes none, "Save as…" asks
  where and takes one.

Pure functions over `str`, so the registry and a consumer's own guard
answer the same question the same way.
"""

from __future__ import annotations

ELLIPSIS = "\u2026"
THREE_DOTS = "..."
_MARKER = "&"


def access_keys(text: str) -> tuple[str, ...]:
    """Every access key `text` marks, lower-cased, in order.

    Read left to right the way Qt reads it: `&&` is one literal ampersand,
    and `&` before any other character marks that character, so
    `"Save &&&As"` is "Save &As" with the access key A.
    """
    keys: list[str] = []
    index = 0
    while index < len(text) - 1:
        if text[index] != _MARKER:
            index += 1
            continue
        following = text[index + 1]
        if following != _MARKER:
            keys.append(following.lower())
        index += 2
    return tuple(keys)


def plain_text(text: str) -> str:
    """`text` as the user reads it: access-key markers gone, `&&` as `&`."""
    sentinel = "\0"
    return text.replace("&&", sentinel).replace("&", "").replace(sentinel, "&")


def text_problems(text: str, *, needs_input: bool) -> tuple[str, ...]:
    """What is wrong with a command's text, empty when nothing is."""
    problems: list[str] = []
    keys = access_keys(text)
    if len(keys) != 1:
        problems.append(
            f"{text!r} marks {len(keys)} access keys; mark exactly one with "
            "'&' and write a literal ampersand as '&&'"
        )
    elif not keys[0].isalnum():
        problems.append(f"{text!r} marks {keys[0]!r}, which is not a letter or digit")
    if THREE_DOTS in text:
        problems.append(f"{text!r} uses '...'; the ellipsis is '{ELLIPSIS}' (U+2026)")
    ends_with_ellipsis = text.endswith(ELLIPSIS)
    if needs_input and not ends_with_ellipsis:
        problems.append(f"{text!r} asks for more input, so it ends with '{ELLIPSIS}'")
    if ends_with_ellipsis and not needs_input:
        problems.append(
            f"{text!r} ends with '{ELLIPSIS}' but acts at once; the ellipsis "
            "promises a further question"
        )
    return tuple(problems)
