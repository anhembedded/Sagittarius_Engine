# `ActionCard` — candidate `BaseCard` sub-base, NOT a real type yet

**Status: 0/2 candidates.** No `.qml` file here. Not in `qmldir`. Invisible to
`kit/raw_primitive_guard.py`, `tokens/qml_literal_guard.py`, and
`kit/rectangle_card_guard.py` on purpose — this directory exists only so the *intent* is
visible to the next person (or AI session) browsing `Sagittarius/UI/`, not to register a type.

## Hypothesis

A card whose primary interactive control (a button, typically) should track the card's own
`active`/`inactive` state automatically — i.e. `setDisabled(true)` on the card should disable
its internal action button too, not just dim the card visually.

## Why it doesn't exist yet

Raised during design discussion (2026-08-23) as a proposed category, not derived from a real
widget that needed it. Checked against the 3 real `BaseCard` descendants that exist today
(`LogPanel`, `TimeRangeCard`, `AppDataTable`) — none of them wire an internal button's
`enabled` to the card's own `setActive`/`setDisabled` hooks. `LogPanel`'s Copy/Clear buttons,
for example, bind to the *screen's* `viewModel.controlsEnabled`, not to anything on the card
itself.

## Promotion rule

Per `ui-architecture.md` §1.2's operational test and the "only abstract with ≥2 real
instances" discipline used throughout `EPIC-001C`: this becomes a real `Sagittarius/UI/ActionCard/ActionCard.qml`
(`BaseCard { ... }`, registered in `qmldir`) once **two** real cards in a consuming screen
need this exact contract — a card's own active/inactive state directly gating an internal
action's enabled state. One real case is not enough; it could still be a one-off, and a wrong
shape here is expensive to walk back once other cards start depending on it.
