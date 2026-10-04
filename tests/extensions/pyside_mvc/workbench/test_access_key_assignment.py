"""Labels a consumer names in plain words get free access keys (`EPIC-008D`)."""

from __future__ import annotations

from sagittarius_engine.extensions.pyside_mvc import assign_access_keys


def test_word_starts_first_then_any_free_letter() -> None:
    assert assign_access_keys(["Positions", "Open orders"], taken=[]) == (
        "&Positions",
        "&Open orders",
    )
    # "o" taken: no word of "Open orders" starts free, so the first free letter.
    assert assign_access_keys(["Open orders", "Order book"], taken=["o"]) == (
        "O&pen orders",
        "Order &book",
    )


def test_a_literal_ampersand_is_escaped() -> None:
    assert assign_access_keys(["Fills & fees"], taken=[]) == ("&Fills && fees",)


def test_a_label_with_every_letter_taken_gets_no_key() -> None:
    assert assign_access_keys(["Ab"], taken=["a", "b"]) == ("Ab",)
