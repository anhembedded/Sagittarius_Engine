# `FormCard` — candidate `BaseCard` sub-base, NOT a real type yet

**Status: 1/2 candidates — strongest of the four.** No `.qml` file here. Not in `qmldir`.
Invisible to all three kit guards on purpose — this directory exists only so the *intent* is
visible to the next person (or AI session) browsing `Sagittarius/UI/`, not to register a type.

## Hypothesis

A card that holds editable input. `setDisabled(true)` means "lock editing" — dim the card
*and* force its inputs read-only — not just a visual opacity change.

## The one real candidate

`TimeRangeCard.qml` already implements exactly this, today:

```qml
function setDisabled(disabled) {
    opacity = disabled ? 0.6 : 1.0
    root.readOnly = disabled
}
```

Both halves of the hypothesis are already present in real, shipped code — this is the
candidate with the strongest evidence of the four in this directory.

## Promotion rule

Needs a **second** real card with the identical need (dim + force-read-only together) before
becoming a real `Sagittarius/UI/FormCard/FormCard.qml`. `TimeRangeCard` alone could still be a
one-off; the pattern isn't confirmed as *shared* until something else needs it too. When that
second case appears, promoting is: extract `TimeRangeCard`'s `setDisabled` body into
`FormCard.qml`, make `TimeRangeCard` extend `FormCard` instead of `BaseCard` directly, add the
new card the same way. No consumer-facing change — `qmldir` is the facade.
