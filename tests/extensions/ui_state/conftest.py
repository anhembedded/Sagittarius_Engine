"""Shared fixtures for the `ui_state` extension's tests.

@details `RepoStateStoreLocator` deliberately did **not** come across from the
application repo with the rest of this package: where the state file lives is
an application decision (that one resolves a path relative to a repo checkout,
which means nothing to a framework). The port is here; the policy is not.

So the tests bring their own trivial implementation, which doubles as a worked
example of how small the contract is.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from sagittarius_engine.extensions.ui_state.ports.i_state_store_locator import (
    IStateStoreLocator,
)


class TmpStateStoreLocator(IStateStoreLocator):
    """Points at a file inside pytest's `tmp_path`."""

    def __init__(self, directory: Path) -> None:
        self._path = directory / "ui_state.json"

    def state_file(self) -> Path:
        return self._path

    def reset(self) -> None:
        self._path.unlink(missing_ok=True)


@pytest.fixture
def locator(tmp_path) -> TmpStateStoreLocator:
    return TmpStateStoreLocator(tmp_path)
