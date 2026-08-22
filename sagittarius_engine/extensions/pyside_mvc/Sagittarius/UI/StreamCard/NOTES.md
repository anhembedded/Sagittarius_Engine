# `StreamCard` — candidate `BaseCard` sub-base, NOT a real type yet

**Status: 1/2 candidates, weaker claim than `FormCard`.** No `.qml` file here. Not in
`qmldir`. Invisible to all three kit guards on purpose — this directory exists only so the
*intent* is visible to the next person (or AI session) browsing `Sagittarius/UI/`, not to
register a type.

## Hypothesis

A card that displays a live/streaming feed. `setDisabled(true)` means "pause receiving
updates" — a behavioural pause, not (only) a visual dim. This is literally one of the three
example behaviours `BaseCard.qml`'s own docstring names ("pause a live update").

## The one plausible candidate — unconfirmed, not yet coded

`LogPanel.qml` is architecturally the obvious fit (it renders a live-appended log feed), but
**it does not currently override `setDisabled` at all** — it still uses `BaseCard`'s no-op.
Weaker evidence than `FormCard`'s: this is "the shape BaseCard's docstring anticipated,"
not "a behaviour someone already needed and shipped."

## Promotion rule

Do not implement this speculatively just because it's plausible. Needs a real, shipped need
— either `LogPanel` itself gaining a real pause-on-disable requirement, or a second
stream-like card appearing — before this becomes `Sagittarius/UI/StreamCard/StreamCard.qml`.
Being "the example in a docstring" is not the same as "a confirmed instance."
