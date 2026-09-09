"""`tools/state_console/domain/events.py` — `EPIC-008B`'s `ConsoleFailed`/
`ConsoleFailureKind`. Pure Python, no server, no Qt: the `code` defaulting
logic is a unit worth testing directly rather than only indirectly through
`test_console_connection_extension.py`'s real-server integration tests."""

from __future__ import annotations

import pytest

from tools.state_console.domain.events import ConsoleFailed, ConsoleFailureKind


@pytest.mark.parametrize(
    ("kind", "expected_code"),
    [
        (ConsoleFailureKind.MALFORMED, "EINVAL"),
        (ConsoleFailureKind.REFUSED, "ECONNREFUSED"),
        (ConsoleFailureKind.REJECTED, "HTTP 401"),
    ],
)
def test_code_defaults_from_kind_when_omitted(kind, expected_code):
    event = ConsoleFailed(kind=kind, detail="boom", uri="ws://x")

    assert event.code == expected_code


def test_an_explicit_code_overrides_the_default():
    event = ConsoleFailed(
        kind=ConsoleFailureKind.REFUSED, code="ECUSTOM", detail="boom", uri="ws://x"
    )

    assert event.code == "ECUSTOM"


def test_unknown_kind_has_no_default_and_requires_an_explicit_code():
    """The one kind that genuinely covers more than one real cause
    (`ConsoleFailureKind.UNKNOWN`'s own docstring) must never silently fall
    back to a made-up default — a caller that forgets `code=` should fail
    loudly, not ship a wrong label."""
    with pytest.raises(ValueError, match="has no default code"):
        ConsoleFailed(kind=ConsoleFailureKind.UNKNOWN, detail="boom", uri="ws://x")


def test_unknown_kind_with_an_explicit_code_works():
    event = ConsoleFailed(
        kind=ConsoleFailureKind.UNKNOWN,
        code="PROTOCOL_MISMATCH",
        detail="boom",
        uri="ws://x",
    )

    assert event.code == "PROTOCOL_MISMATCH"
