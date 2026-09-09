# EPIC-008A: Design tokens and shared shell primitives

- **Status**: ✅ Completed
- **Category**: UI Engine (`pyside_mvc`)
- **Started Date**: 2026-09-09
- **Completed Date**: 2026-09-09

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

### 2. `LiveConnectionBand` — new kit component — ✅ done

The status band (`reference/handoff.md` §4): stripe + pulsing state dot + label/note + a
heartbeat ribbon + an age block + a target/`change…` slot + a primary action button. Landed as
`Sagittarius/UI/LiveConnectionBand/LiveConnectionBand.qml`, built directly on `Rectangle`/
`RowLayout` (the kit's own components, like `StatefulButton`, are built directly on Qt Quick
primitives — `ui-architecture.md` §1.1's escape-hatch restriction governs a *consumer* reaching
past the kit, not the kit's own composition). Tiered per §1.2 as planned:

- **Tier 1 (inside the component):** `state` (one of `reading`/`idle`/`connecting`/`failed`/
  `stale`/`cold`) → colour mapping (`accent` in reading; `accent700` in idle/connecting;
  `danger` in failed/stale/cold — matching `reference/handoff.md` §4's own table exactly, which
  is a satisfying confirmation that the ramp-token naming chosen in item 1 above lines up with
  the design's own vocabulary) and → pulse-duration mapping (1000/1600/700ms; none for the
  other three); the heartbeat ribbon's tick-render/fade mechanism (a generic "rolling activity
  strip" — the component knows nothing about snapshots, only numbers in `[0, 1]`, newest last).
  An unrecognized `state` string falls back to `Theme.muted` rather than raising, so a
  consumer's typo reads as "obviously wrong grey" instead of a crash.
- **Tier 2 (parameters):** `stateLabel`/`stateNote`/`ageLabel`/`ageValue`/`targetText`/
  `actionLabel`/`heartbeatTicks` — every piece of text and the tick data itself, since a
  different `pyside_mvc` consumer attaching this band to a different kind of live connection
  needs different copy.
- **Tier 3 (never enters):** confirmed — no reference to "backend", "snapshot", or "socket"
  anywhere in the component; it renders exactly the `state` enum plus whatever strings/numbers
  it is handed.

Heartbeat ribbon shipped as an internal implementation detail (not a separately registered kit
type) — nothing else in this epic plausibly needs a bare activity ribbon without the rest of
the band, and it is cheap to extract later if that changes.

Reused `StatefulButton` for the primary action rather than inventing a second button type.
`font.family: "monospace"` for the target address is a named, bounded literal — the engine's
typography vocabulary has size tiers only, no family token yet; promotable if a second consumer
needs one.

Demonstrated in the gallery across three states (reading/connecting/stale). 8 new tests in
`tests/extensions/pyside_mvc/test_live_connection_band.py`, against a **standalone** `QQmlEngine`
with its own directly-injected `Theme` (not the shared `get_theme_bridge()` singleton every
other kit test uses) — that singleton is first-call-wins for the whole pytest process and every
existing fixture locks it to an all-`#000000` placeholder palette, which cannot distinguish
`accent`/`accent700`/`danger`/`muted` from one another and so cannot actually prove the colour
mapping is correct, only that it's internally consistent. One click-path gap named honestly
rather than faked: `MouseArea.clicked(mouse)` (the "change…" link) cannot be invoked from
Python the way `Button.clicked()` (zero-arg, used for the action button) can — no `QQuickMouseEvent`
constructor is available from Python — so that one binding is verified by code review, the same
class of gap `AppDataTable`'s own drag-to-resize test already discloses.

### 3. Rail navigation with signal-count badges — new kit component — ✅ done

Today's `ConsoleShellView` sidebar (`tools/state_console/presentation/shell/
console_shell_view.py`) is deliberately raw `QWidget`/`QPushButton` because nothing needed
theming yet (see that file's own docstring). The handoff's rail — indexed rows, active-state
border treatment, a per-row fault badge, hover states, a footer block — is themed enough that
it belongs in the kit; landed as `Sagittarius/UI/AppRail/AppRail.qml`, built directly on
`Rectangle`/`ColumnLayout` (same reasoning as `LiveConnectionBand`: the kit's own components are
built on Qt Quick primitives directly, `BaseCard`'s icon/title card chrome doesn't fit a nav
row's shape and forcing it in would be the wrong abstraction, not a shortcut avoided).

- **Tier 1:** sequential numbering (`01`, `02`, … computed from list position, not supplied),
  active/hover/badge rendering, and a `_selectRow(id)` function that both the row's own
  `MouseArea` calls and a test can invoke directly with a `QVariant` argument (the same
  workaround `LiveConnectionBand`'s tests needed for anything gated behind a real
  `MouseArea.clicked(mouse)`).
- **Tier 2:** `sections` — a plain schema-driven array (`{ id, label, badgeCount }`), the same
  shape `AppDataTable.columns` already uses, generalized from "table columns" to "nav rows".
  `badgeCount <= 0` means no badge at all, not a badge showing `0` — `reference/handoff.md`'s
  own "zero rows are muted, not hidden" principle, applied here as *no badge* rather than a
  zeroed one.
- **Tier 3:** a generic `footer` slot (any `Item`, reparented in via `Binding`) rather than a
  hardcoded target/process info-block or an appearance toggle — this component has no opinion
  on what a "target" or "process" is; `console_shell_view.py` (`EPIC-008B`) supplies that.

**A real, reusable finding surfaced while writing this component's own tests:** a plain
`Repeater` (not just a `ListView` delegate, as `AppDataTable`'s expansion `Loader` already
showed) breaks `QObject.findChild()` the same way, AND repeatedly searching
(`find_visual_child()`, a fresh `childItems()` walk each call) over a tree containing one
reproduced a second, sharper failure: "Internal C++ object already deleted" on the *second*
independent search — a `Repeater`-managed item's Python wrapper, once dropped, appears to take
the underlying live, still-parented C++ item down with it. Fixed by adding
`collect_all_items()` to the shared test helper (`tests/extensions/pyside_mvc/
_standalone_qml_theme.py`, factored out of `test_live_connection_band.py` in the process so both
files share one `standalone_theme_engine()`/`load_qml_fixture()` implementation): collect the
whole subtree ONCE into a list the test keeps alive, never re-walk it. This is now the
documented, load-bearing pattern for any future kit test touching a `Repeater`/`Loader`.

7 new tests in `tests/extensions/pyside_mvc/test_app_rail.py`. Demonstrated in the gallery with
three badge states (none/2/10) and a footer.

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

### 5. Connect-flow input primitives — resolved: no new kit component

**Correction to this file's own original plan.** The text below (kept for the record) proposed
building a themed text field and a themed "row with trailing action" as new kit types. Re-read
against `Sagittarius/UI/ActionCard/NOTES.md` — a real, already-written promotion rule in this
codebase — that was wrong: *"this becomes a real [kit type] once **two** real cards in a
consuming screen need this exact contract... one real case is not enough; it could still be a
one-off, and a wrong shape here is expensive to walk back once other cards start depending on
it."* `tools/state_console` is the only consumer with this need today. Building a new
`Sagittarius/UI/` type for it now would be exactly the premature abstraction that rule exists to
block — this file would have been the second time in one epic to reach for "promote it to the
kit" as a default, right after `EPIC-008A` item 2 already used the *opposite* reasoning
correctly (reusing `StatefulButton` instead of inventing a second button type, because a second
type already existed and fit).

**Resolution:** the connect flow is composed in `tools/state_console`'s own shell layer, from
primitives that already exist — `TextField` + `FieldBackground` (already the established
pattern; see the gallery's own `FIELDS` section) for the address entry, `StatefulButton` for
actions, plain `Rectangle`/`RowLayout` for each recent-address row. Nothing here is kit work,
so it does not belong in this subtask — `EPIC-008B` builds it as part of rebuilding the shell,
where the connect flow actually lives. If a second `pyside_mvc` consumer later needs the same
"type something, submit it, see recent submissions" shape, promote it then, following the exact
rule `ActionCard/NOTES.md` already states — not preemptively.

<details>
<summary>Original plan text (superseded by the resolution above)</summary>

No kit-level text field or "list with a trailing action button" component exists yet
(`Sagittarius/UI/` currently has no `TextField`/`ComboBox`-shaped entry). The connect flow
(§5 of the handoff) needs an address entry field + submit action + a short list of recent
targets each with a trailing button. Build the generic pieces as kit primitives (a themed text
field, a themed row-with-trailing-action list item) so a future consumer needing "type
something, submit it, see recent submissions" doesn't re-invent it — but the address-specific
validation regex, the three failure-kind copy blocks, and what counts as a "recent target" are
`tools/state_console` domain knowledge (tier 3) and stay there, in the connect-flow's
presenter/view-model, not in the kit component.

</details>

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

## ✅ Outcome

4 of the 5 originally-planned items shipped as kit work; the 5th resolved to "no kit component
needed" (§5, above) rather than being forced into existence — a correction, not a completion
gap, per `design-discipline.md`'s "leave something undone and named over done and wrong."

| # | Item | Result |
| :-: | :--- | :--- |
| 1 | Token derivation (`tokens/derived.py`) | ✅ Shipped — 21 tests |
| 2 | `LiveConnectionBand` | ✅ Shipped — 8 tests |
| 3 | `AppRail` | ✅ Shipped — 7 tests |
| 4 | `AppDataTable` row expansion (sort already existed) | ✅ Shipped — 4 tests |
| 5 | Connect-flow input primitives | ➖ No new kit component — composed from existing primitives in `EPIC-008B` instead |

Every local CI gate run genuinely green (read from the log, not the summary line) before each
push, per `commit-rule.md`. The one recurring flake (`tests/infrastructure/event_bus/
test_ipc_queue_event_bus.py`'s `os.fork()` colliding with Qt-initialized threads,
pre-existing and unrelated to this work) surfaced twice across this subtask's several CI runs
and cleared on a single retry both times, consistent with `EPIC-007`'s own prior diagnosis of
it as an environmental race, not a regression.

**Two real, reusable findings that outlast this subtask:**
1. `QObject.findChild()` cannot see a `Loader`- or `Repeater`-created item — confirmed for a
   `ListView` delegate (`AppDataTable`'s row expansion) AND a plain `Repeater` outside any
   `ListView` (`AppRail`'s section rows). Worse than "doesn't find it": *repeatedly* searching
   such a tree can crash with "Internal C++ object already deleted" on the second search.
   `tests/extensions/pyside_mvc/_standalone_qml_theme.py::collect_all_items()` is now the
   documented, load-bearing fix for any future kit test in this position.
2. The `ActionCard/NOTES.md` "two real consumers before promoting a kit type" rule caught this
   file's own draft plan reaching for a new kit component with only one real consumer —
   corrected before writing the throwaway code, not after.

**Handed to `EPIC-008B`:** the two `ConsoleConnectionExtension` gaps (no `CONNECTING`/classified-
`FAILED` events, no live re-target) and the connect-flow's actual composition, since both
belong to rebuilding the shell, not to the kit.
