"""`RecentAddressesStore` — `EPIC-008B` §3. A real `QSettings` file (a
throwaway one under `tmp_path`, never the developer's real persisted
settings), not a mock -- the ordering/trimming/round-tripping behaviour is
exactly what would otherwise only be caught by hand-testing across
restarts."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QSettings  # noqa: E402

from tools.state_console.presentation.shell.recent_addresses_store import (  # noqa: E402
    RecentAddressesStore,
)


def _store(tmp_path) -> RecentAddressesStore:
    settings = QSettings(str(tmp_path / "recents.ini"), QSettings.Format.IniFormat)
    return RecentAddressesStore(settings)


def test_starts_empty(tmp_path):
    assert _store(tmp_path).list() == []


def test_record_puts_the_address_first(tmp_path):
    store = _store(tmp_path)
    store.record("ws://a")
    store.record("ws://b")

    assert store.list() == ["ws://b", "ws://a"]


def test_re_recording_an_existing_address_moves_it_to_the_front_without_duplicating(
    tmp_path,
):
    store = _store(tmp_path)
    store.record("ws://a")
    store.record("ws://b")
    store.record("ws://a")

    assert store.list() == ["ws://a", "ws://b"]


def test_the_list_is_trimmed_to_five(tmp_path):
    store = _store(tmp_path)
    for i in range(7):
        store.record(f"ws://{i}")

    assert store.list() == ["ws://6", "ws://5", "ws://4", "ws://3", "ws://2"]


def test_a_single_remaining_entry_still_comes_back_as_a_list(tmp_path):
    """`QSettings`' own stringlist quirk: a length-1 list can round-trip as
    a bare `str` -- this must still come back as `["ws://a"]`, not `"ws://a"`."""
    store = _store(tmp_path)
    store.record("ws://a")

    assert store.list() == ["ws://a"]


def test_persists_across_separate_store_instances_on_the_same_settings_file(tmp_path):
    settings_path = str(tmp_path / "recents.ini")
    RecentAddressesStore(QSettings(settings_path, QSettings.Format.IniFormat)).record(
        "ws://a"
    )

    reopened = RecentAddressesStore(
        QSettings(settings_path, QSettings.Format.IniFormat)
    )
    assert reopened.list() == ["ws://a"]
