# EPIC-008A: Design tokens and shared shell primitives

- **Status**: 🔄 In Progress
- **Category**: UI Engine (`pyside_mvc`)
- **Started Date**: 2026-09-09

---

## 🎯 Summary & Objectives

Everything the remaining five subtasks (B–F) depend on: the token vocabulary additions
`EPIC-008` §2.1 decided, and the kit-level components `EPIC-008` §2.2 decided are shared
chrome rather than `tools/state_console`-local. Nothing in this subtask touches a console
screen body — that starts at `EPIC-008B` (Overview).

Done when every item below renders in `scripts/show-gallery.ps1` (both themes) and the
kit-level guards (`kit/gallery_coverage_guard`, the anti-literal test, `import_boundary`) still
pass — per `ui-architecture.md` §6, a component that only renders inside one consumer screen
has not been proven reusable yet.

## 📐 Implementation Plan / Overview

### 1. Token derivation utility (`pyside_mvc/tokens/derived.py`) — ✅ done

Per `EPIC-008` §2.1: no new required colour tokens for the handoff's `fault*` family — it is
`danger` under another name, plus computed shade/role variants. Landed as
`tokens/derived.py`, two pure functions (no Qt import, tested without
`QT_QPA_PLATFORM=offscreen`):

```
derive_shade_tokens(base: Mapping[str, str]) -> dict[str, str]
derive_structural_tokens(base: Mapping[str, str]) -> dict[str, str | float]
```

`derive_shade_tokens` takes the app's four semantic colours already required (`accent`,
`success`, `warning`, `danger`). For each present in `base` it computes a 100–900 tint/shade
ramp plus `<name>Fill`/`on<Name>`/`<name>Text` role variants (camelCase, matching
`tokens/vocabulary.py`'s convention, not the handoff's hyphenated CSS-custom-property
spelling). `on<Name>` picks black/white by relative luminance; `<name>Text` was *not* simply
"always darker" — verified against the handoff's own two concrete light/dark `fault`/
`fault-text` pairs (§10) that the correct rule is "push further toward whichever extreme the
base colour already leans" (a light-theme colour needs darker prose, a dark-theme one needs
lighter prose), and both reference pairs now have regression tests
(`test_text_variant_darkens_a_light_theme_style_base_colour` /
`..._lightens_a_dark_theme_style_base_colour`) pinning that exact behaviour.

**Second finding made while implementing, not anticipated when this file was first written:**
`divider`/`hatch`/`gridLine` are not independent hues either — the handoff's own §10 token
table names each as an *existing* colour at one fixed alpha (`divider` = ink @ 16-22%, `hatch`
= fault(danger) @ 7-10%, `grid-line` = an accent tint). `derive_structural_tokens` bakes each
as an `"#rrggbbaa"` string (Qt/QML accepts 8-digit hex directly — no per-use-site `Qt.rgba()`
needed for a token that only ever needs one alpha). `surface`/`chrome` *are* new structural
tokens — nothing today distinguishes "the background" from "a slightly different background"
— computed by mixing `bg` toward `textPrimary` ("ink") by a small amount (5%/9%), which
self-adjusts for either theme (`ink` is dark-on-light in a light palette, light-on-dark in a
dark one) rather than needing a light/dark branch. `ink` itself is exposed as three numeric
channels (`inkR`/`inkG`/`inkB`, 0-255), not a packed value or a pre-baked hex — it is
recomposited in QML at a dozen different alphas per the handoff's own list, which
`"#rrggbbaa"` cannot serve.

**Required-vs-default-backed, resolved:** all of it is default-backed
(`tokens/defaults.py::with_token_defaults`), not added to `tokens/vocabulary.py`'s required
set. Making any of these required would have broken every existing consumer's palette
immediately (`examples/student_management`, `tools/state_console`'s own
`STATE_CONSOLE_PALETTE`) for tokens that are, in every case, computable from colours those
consumers already supply — there was no case here, unlike `warning`'s own precedent in
`vocabulary.py`, where a consumer would need to make a new colour *choice* the engine
shouldn't default on their behalf. An app can still override any individual derived key by
naming it directly in its own palette — `with_token_defaults()` applies `palette` last, so an
app value always wins over a computed one.

Wired into `with_token_defaults()` and exported from both `tokens/__init__.py` and the
top-level `pyside_mvc` package (the only supported import surface, `ui-architecture.md` §8.1).
21 new unit tests in `tests/extensions/pyside_mvc/test_derived_tokens.py`; full
`tests/extensions/pyside_mvc/` suite (179 tests) still green; `ruff`/`ruff format`/`mypy`
clean on the changed files.

### 2. `LiveConnectionBand` — new kit component

The status band (`reference/handoff.md` §4): stripe + pulsing state dot + label/note + a
heartbeat ribbon + an age block + a target/`change…` slot + a primary action button. Tiered
per `ui-architecture.md` §1.2:

- **Tier 1 (inside the component):** the rendering mechanics for a `state` enum → colour/pulse
  mapping, the heartbeat ribbon's tick-append/fade mechanism (generic: "a rolling activity
  strip", not "snapshot" specific), the stripe/dot/layout geometry.
- **Tier 2 (parameters):** which states exist and their colours are a fixed enum the component
  owns (tier 1) — but the *label/note/age text* and the *button label* the mock's own table
  specifies per-state are supplied by the consumer, not hardcoded, since a different `pyside_mvc`
  consumer attaching this band to a different kind of live connection would need different copy.
- **Tier 3 (never enters):** no knowledge of "backend", "snapshot", or WebSockets. The
  component knows `connected | connecting | idle | failed | stale | cold`-shaped states (or
  fewer — see Gap 1 below) and strings to show; it does not know what is on the other end of
  the connection.

Heartbeat ribbon may ship as this component's internal implementation detail rather than a
separately registered kit type — decide based on whether anything else plausibly reuses a
bare activity ribbon without the rest of the band; if unsure, keep it internal (cheaper to
extract later than to deprecate a public type early).

### 3. Rail navigation with signal-count badges — new kit component

Today's `ConsoleShellView` sidebar (`tools/state_console/presentation/shell/
console_shell_view.py`) is deliberately raw `QWidget`/`QPushButton` because nothing needed
theming yet (see that file's own docstring). The handoff's rail — indexed rows, active-state
border treatment, a per-row fault badge, hover states, a footer block — is themed enough that
it belongs in the kit as `AppRail` (or similar; naming TBD), composed from existing primitives
(`BaseCard`-family) rather than raw `Rectangle`/`Item`. `console_shell_view.py` becomes a thin
consumer wiring route names + labels + badge counts into it — the badge *counts themselves*
(derived from snapshot signal totals) stay `tools/state_console` domain logic (tier 3), fed in
as plain integers (tier 2).

### 4. `AppDataTable` — sortable columns + expandable row — ✅ done

Extends the existing component (`Sagittarius/UI/AppDataTable/AppDataTable.qml`) rather than a
new type:

- **Sort — already shipped, discovered on inspection, no new work needed.** Reading the
  component before touching it found `sortKey`/`sortAscending`, per-column `sortable` (default
  true), header click-to-toggle with a `▲`/`▼` indicator, and raw-value (not formatted-text)
  comparison already in place, added for `TASK-036` before this epic existed. `_sortedModel()`
  recomputes from `root.model` and the two sort properties on every dependency change, so
  sort state is inherently preserved across a live model replacement (a snapshot refresh) —
  it was never index-based to begin with. This file's original plan assumed sort needed
  building; it didn't, and no change was made here.
- **Expand — built.** A per-row expansion slot, tracked by **identity**
  (`rowData[rowIdKey]`), not list index — an index-based "row 3 is expanded" would silently
  point at a different row, or none, the instant a live snapshot refresh reorders or resizes
  the model array, which is exactly the failure mode `EPIC-007F`'s own signals data is prone
  to. New properties: `expandedDelegate` (a `Component`; its root item must declare
  `property var rowData`, kept live-bound via an internal `Binding` so content inside an open
  expansion keeps updating on later snapshot ticks, not frozen at the moment it opened),
  `expandPredicate` (optional `(rowData) => bool`; `null` means every row may expand),
  `rowIdKey` (default `"id"`), `expandedRowKey`. `expandPredicate` is enforced as a real
  invariant inside the component's own `_isExpanded` computation, not only gated in the row's
  click handler — setting `expandedRowKey` directly to a row the predicate disallows does not
  expand it either. Delegate restructured from a bare `Rectangle` to a `Column` (band +
  conditional `Loader`) so the row's height auto-adjusts; mechanism is tier 1, expansion
  content is tier 2 (supplied by the consumer), matching `ui-architecture.md` §1.2.
  4 new tests in `tests/extensions/pyside_mvc/test_widget_kit_gallery.py` plus a new fixture
  (`fixtures/app_data_table_expandable_probe.qml`); demonstrated in the gallery
  (`Gallery.qml`'s "expandable row" table, clicking the Failed task). One real finding along
  the way: `QObject.findChild()` cannot see a `Loader`-created item from the table's root —
  confirmed empirically (the item genuinely loads, with correct live-bound data, yet
  `findChild()` returns `None` even seconds later) — because a `ListView`'s `contentItem`
  breaks the `QObject` parent chain `findChild()` walks. Fixed by testing via `childItems()`
  (the visual tree) recursively instead, the same pattern
  `test_app_data_table_zoom_factor_scales_row_height` already used one level deep.

### 5. Connect-flow input primitives

No kit-level text field or "list with a trailing action button" component exists yet
(`Sagittarius/UI/` currently has no `TextField`/`ComboBox`-shaped entry). The connect flow
(§5 of the handoff) needs an address entry field + submit action + a short list of recent
targets each with a trailing button. Build the generic pieces as kit primitives (a themed text
field, a themed row-with-trailing-action list item) so a future consumer needing "type
something, submit it, see recent submissions" doesn't re-invent it — but the address-specific
validation regex, the three failure-kind copy blocks, and what counts as a "recent target" are
`tools/state_console` domain knowledge (tier 3) and stay there, in the connect-flow's
presenter/view-model, not in the kit component.

## 🧩 Gaps to resolve — real, not cosmetic

These affect subtask sequencing, not just this subtask's own scope, so they're recorded here
rather than discovered mid-B:

1. **`ConsoleConnectionExtension` cannot express `CONNECTING` or a classified `FAILED` today.**
   Read in full (`tools/state_console/infrastructure/console_connection_extension.py`): it
   emits exactly two domain events, `ConsoleAttached` and `ConsoleDetached(reason: str)`. Every
   connect failure — a bad URI, nothing listening, an auth rejection — currently collapses into
   the same `ConsoleDetached(reason="could not connect: <OSError message>")`. The handoff's
   six-state model (`COLD/CONNECTING/FAILED/IDLE/READING/STALE`) needs at minimum a distinct
   `ConsoleConnecting` event and a `ConsoleFailed(kind, code, detail)` event whose `kind` is
   derived from the underlying exception type (`OSError` subtype for `refused`, a URI-parse
   failure for `malformed`, an auth/handshake-status exception for `rejected`) — real behavior
   work in the extension, not something the presentation layer can fake convincingly. This is
   `EPIC-008B`'s problem to solve (it is the first subtask that wires the band to a real
   connection), named here so it is not assumed to be a free re-skin.
2. **`uri` is fixed at construction; there is no live re-target.** The extension is built once
   with one URI and has no `connect_to(new_uri)`/disconnect-and-reconnect entry point — the
   only way to change target today is restarting the process with a different CLI flag. The
   "connect from within the tool, without restarting" requirement (`EPIC-008`'s own earlier
   design-prompt correction) needs this extension (or its replacement) to support being
   re-pointed at runtime. Also `EPIC-008B`'s problem.
3. **Recent-address persistence** has no existing mechanism in this codebase to reuse. Plan:
   `QSettings`, owned by `tools/state_console` (tier 3 — "what counts as a recent target" is
   this consumer's concept, not a kit one), not a new kit-level persistence primitive.

## 🧪 Verification & Test Coverage

- `scripts/show-gallery.ps1 -Snapshot` — every new/changed component appears (enforced by
  `kit/gallery_coverage_guard.find_types_missing_from_gallery()`), in both light and dark
  palettes.
- Anti-literal test and `import_boundary.find_deep_imports()` still pass with zero new
  exemptions.
- `tests/extensions/pyside_mvc/` gets new unit tests for the token derivation function (pure
  Python, no Qt needed) and for each new component's construction under
  `QT_QPA_PLATFORM=offscreen` with zero QML warnings, per `ui-architecture.md` §6.1.
- `tools/state_console`'s existing palette (`STATE_CONSOLE_PALETTE`) still boots the console
  after any new required-token additions — a regression here would break the one real consumer
  this epic exists to improve.
