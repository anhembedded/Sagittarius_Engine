"""Entry point for `sagittarius-doctor` — `EPIC-006E`.

`main.build_app()` takes arguments and this tool calls a zero-argument factory,
so the two are bridged here rather than by loosening the CLI's contract. A
factory that needs configuration is the normal case; every application will
write a shim like this one, and it is three lines.

An in-memory database on purpose: inspecting wiring must not touch whatever
database the real configuration points at.
"""

from examples.student_management.main import build_app
from sagittarius_engine.kernel import App


def build() -> App:
    """@brief A booted application for inspection."""
    return build_app(db_url="sqlite:///:memory:")
