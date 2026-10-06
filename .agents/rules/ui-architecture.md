---
name: UI Engine Architecture
description: The pyside_mvc contract. QtWidgets consumers get a desktop workbench of stock controls in the platform style (§9, sourced from Microsoft, KDE, Apple, GNOME and Qt guidance); QML consumers get the token and kit boundary (§2-§3). The component-boundary law (§1.2) governs both. Load for any UI work.
trigger: model_decision
---

# 🎛️ UI Engine Architecture — PySide6: a QtWidgets workbench, and the QML kit

This document governs `sagittarius_engine.extensions.pyside_mvc`. It serves two kinds of
consumer, and says which clauses bind which:

| Consumer | Its contract | Sections |
| :--- | :--- | :--- |
| **QtWidgets** (the default; the reference consumer since its ADR D20-D22) | A Windows desktop workbench of **stock Qt controls in the platform style**: menus, toolbars of actions, docks, dialogs, item views configured by kind. No tokens, no kit, no style sheets. | §1, §1.2, §4-§9 |
| **QML** | Engine-owned design tokens and the QML widget kit | §1-§8 (§2, §3 and §1.1 bind only QML) |

History: a QtWidgets/QFrame/QSS doctrine was retired for QML on 2026-08-22
([`EPIC-001A`](../../Tasks/epics/EPIC-001_ui_engine_foundation/completed/EPIC-001A_architecture_rule_rewrite.md));
the reference consumer then left QML for stock QtWidgets, and `EPIC-008` / `ADR-003` made
that the engine's default contract. Stock controls are not the QSS doctrine coming back: that
one styled every widget by hand, this one styles none.

**Scope discipline:** this file describes what the **engine** provides and requires of any
consumer. It must never name a specific consuming application, screen, or domain concept —
that content belongs in the consumer's own rules (e.g. `Sagittarius_Elite_Warrior`'s
`ui-presentation-rule.md`, whose desktop clauses §9 carries over as the engine's contract;
the consumer's earlier `qml-rule.md`, which §2-§8 once mirrored, was deleted with its last
`.qml`).

---

## 1. 🏛️ Ownership Boundary — the core contract

**For a QtWidgets consumer** the three owners are: the **platform** owns the look (its style,
its font, its metrics, its colours, its button order); the **engine** owns the mechanism that
is the same on every use (the workbench host, commands as actions, saved layouts, item-view
configuration by kind — §4, §9); the **consumer** owns its vocabulary and composition (which
modes, which commands, which columns). The test: switch the operating system's theme, or its
high-contrast mode, and count the consumer files that must change. The answer must be zero.

**For a QML consumer** the UI Engine holds three monopolies. A consuming application holds domain vocabulary and
composition, and nothing else. This is not a style preference — it is the mechanism that
keeps a multi-screen application visually consistent without relying on every contributor
remembering a convention.

| Layer | Engine owns | Consumer may |
| :--- | :--- | :--- |
| **Tokens** | Every visual value: colour, spacing, radius, typography, motion | Supply its own palette **dict** once, at bootstrap, filling the engine's fixed semantic vocabulary (§2). Never a literal at point of use. |
| **Widget Kit** | The QML components (`Sagittarius/UI/`) that render those tokens | Compose them into screens. Never author a raw visual primitive (`Rectangle`, bare `Button`, etc.) except through the escape hatch (§1.1). |
| **Runtime** | Shell, regions, navigation, screen lifecycle (`mount`/`unmount`/`ui_mode`) | Declare what a screen contributes and how it reacts to lifecycle/state. Never hand-build layout geometry that belongs to a region. |

**The test for whether a consumer is honouring this boundary:** change one token — accent
colour, corner radius, spacing scale — and count how many consumer files must change to
stay visually correct. The answer must be zero. Any number above zero means the consumer is
still deciding a visual value itself, which this boundary exists to prevent.

### 1.1 Escape hatch — permitted, never free of tokens (QML consumers)

A consumer will occasionally need something the kit does not yet provide. This is
permitted, through exactly one mechanism:

- **Single-level inheritance from the matching engine base primitive** (e.g. `BaseCard`) —
  never authoring a bare `Rectangle`/`Item` from scratch. The base's visual behaviour
  (background, border, spacing, disabled/active tinting) is already token-driven and is
  inherited unchanged; a derived component overrides only the behaviour hooks it genuinely
  needs (`BaseCard`'s `setActive()`/`setDisabled()` no-op hooks are the existing example of
  this shape).
- Each use must be **named and justified at the call site** — a one-line comment stating why
  no kit component fits. Silent escapes are indistinguishable from drift and defeat the
  purpose of having a boundary at all.
- A **repeated** escape for the same need is a signal to promote it into the kit proper, not
  to keep re-deriving it ad hoc. If the same escape appears in more than one consumer
  screen, it belongs in the kit — a new component directory under
  `Sagittarius/UI/`, registered in its `qmldir` (§8.1).

What this does **not** permit: deriving from `Rectangle`/`Item` directly, hardcoding a
visual value inside a derived component, or building a component that does not go through
any engine base primitive at all. The escape hatch frees behaviour, never pixels.

### 1.2 Component boundary — what may live inside a single component

§1 draws the boundary between *layers*. This draws the same boundary one scale down, between
*a component and its consumer*, and is the rule that settles every "where does this belong?"
argument about an individual widget.

**The law:**

> **A component owns what is the same on every use.**
> **The consumer owns what differs between uses.**

Three tiers follow from it, and the third is the one most often missed:

| Tier | Kind of knowledge | Where it lives |
| :---: | :--- | :--- |
| **1** | True for *every* use of the component | **Inside** the component |
| **2** | Varies *per use* | A **parameter** passed in |
| **3** | Belongs to a different world entirely | **Never enters** — not even as a parameter |

Tier 3 exists because "pass it in" is not always a sufficient defence. A numeric bound is
tier 2 and may be a property. A reference to the consuming application's engine, dispatcher,
or domain services is **tier 3**: any component requiring one forces every context that uses
it — including the gallery, a unit test, and a standalone preview — to construct one. Stated
generally:

> **Dependency direction runs from specific to general, never the reverse.**

**The operational test.** For any piece of knowledge, ask:

> *When this fact changes, how many files should have to change?*
> The answer must be **1**. Put the knowledge in that one file.

If the answer is greater than 1, the knowledge is currently in the wrong place. Worked
examples, deliberately spanning different component types to show the law generalizes rather
than being fitted to one case:

| Question | Resolution |
| :--- | :--- |
| Should a field know how to display invalidity? | **Yes** — identical across every field in the app (tier 1) |
| Should a field know its own min/max? | **No** — differs per field (tier 2, a property) |
| Should a field enforce that bound? | **No** — UI validation is a courtesy, never the guarantee; the real invariant lives in the consumer's domain and must hold with the UI absent entirely |
| Should a table know how to sort? | The **mechanism** yes (tier 1); *which column, which comparator* is tier 2 |
| Should a modal know whether closing needs confirmation? | **No** — policy, differs per modal (tier 2) |
| Should a button know a background task is running? | It knows **`busy`** (tier 1). It does not know what a "task" is (tier 3) |
| Should a card decide its own width? | **No** — the region decides; the card expresses intent only |
| Should a log panel know `error`/`warn`/`info`? | **Yes** — universal vocabulary (tier 1). *Which events are errors* is the consumer's (tier 2) |
| Should a table know a price column aligns right? | **Yes** — the column's kind decides it on every table (tier 1, `ColumnKind`). *Which* columns, and a price's precision, are the consumer's (tier 2: `ColumnSpec`, `IValueFormatter`) |
| Should a command know it needs a confirmation? | **Yes**, as data on its `ActionDescriptor` (tier 2), so the registry asks before every run (tier 1). The handler never asks itself |

**Why this is the shape:** a design system's product is **consistency, not capability**. A
field component promises *"whatever is invalid will look invalid, the same way, everywhere."*
It does not promise *"I know what is invalid."* Knowledge that produces sameness across the
application belongs inside; knowledge that expresses one case's meaning stays outside.

**Corollary — no per-component runtime object.** It follows directly that a component must
not be paired with its own per-instance Python controller holding application wiring. Such an
object adds capability while weakening the promise: the component then requires assembly
before it renders, can exist in a half-constructed state, and behaves differently between
instances — which is the same violation as hardcoding a bound, merely at a different level.
Python belongs on the other side of the boundary when, and only when, the work genuinely
requires something QML cannot do — I/O, threads, or domain services. A comparison, a derived
boolean, or a state-to-style mapping is not that, and is expressed better as a declarative
binding. When a check *does* require I/O or domain services, that is the signal it was never
component logic in the first place: it belongs to the screen's presenter, which passes the
resulting state in (tier 2).

---

## 2. 🎨 Design Tokens (QML consumers)

Nothing in this section binds a QtWidgets consumer: its colours, spacing and fonts are the
platform's (§9.2), and a token layer in front of them would be a second look.

### 2.1 Fixed semantic vocabulary, consumer-supplied values

The engine defines token **names**; the consumer supplies **values**. This is the reverse
of treating the palette as an open dict with no engine-side opinion on keys — that shape
cannot validate that a consumer supplied everything the kit depends on.

- Token names are semantic (`accent`, `danger`, `spaceMd`, `radiusMd`), never literal
  (`gold`, `twelvePixels`). A semantic name survives a value change; a literal name lies the
  moment the value changes.
- At bootstrap, the engine validates the consumer's palette against its required
  vocabulary. A missing token fails loudly and specifically, naming the missing key — never
  silently falling back to an undefined or default value in a shipping build.
- `state_tokens.with_state_token_defaults()`'s transitional-default behaviour remains for
  vocabulary the engine adds ahead of a consumer adopting it — that is a distinct case
  ("not migrated yet") from a consumer omitting a token it should supply ("wrong"). Do not
  collapse the two.
- Token categories are not limited to colour: spacing, radius, typography and motion are
  tokens with exactly the same discipline. A value that recurs across more than one QML file
  is a token candidate, not a coincidence to re-type.

### 2.2 No literal visual values outside the token layer

QML consuming the kit binds to `Theme.<name>` exclusively. A literal colour, spacing, radius
or duration value appearing in consumer QML — outside the sanctioned compatibility
fallbacks inside the kit's own primitives — is a defect, not a style nit: it is precisely
the failure mode measured across an unmigrated consumer (hundreds of colour literals against
a handful of official tokens, including near-duplicate values that drifted from the real
token by one hex digit because nobody was re-typing from a single source).

A static test enforcing this (no literal outside the token layer) is a required deliverable
of the token layer, not optional follow-up — see the token-layer epic subtask.

---

## 3. 🧩 Widget Kit — Composition, Not Deep Inheritance (QML consumers)

The QtWidgets consumer's kit is Qt's own widget set (§9.2); the engine adds mechanism, not
widgets.

QML is composition-first. Deep inheritance chains produce fragile base classes and property
name collisions; the kit's shape is therefore shallow — one level of inheritance for a base
primitive (`BaseCard`, `BaseField`, …) plus escape-hatch derivations (§1.1), composition for
everything above that.

- **A shared base holds only what is universal**: identity, `enabled`, `active`, a layout
  hint. It must not grow a property per new component type — a base that accumulates
  `columns`, `series`, `placeholder`, … because each new component needed one thing has
  become a union type, not an abstraction. Component-specific shape belongs to the
  component, not the base.
- **No fixed pixel geometry in a component's own contract.** A component expresses sizing
  *intent* (a resize/layout hint); the region or container that hosts it resolves the actual
  number. A component that hardcodes its own width/height cannot be placed correctly by a
  runtime region (§4) that is supposed to own that decision.
- **Data tables are schema-driven, not per-instance markup.** Column definitions (id, title,
  width weight, alignment, formatter, sortable) are declarative data, bound identically by
  header and row delegates, so alignment is structural rather than a promise two delegates
  happen to keep in sync by hand.
- **300 lines is a review threshold, not a hard failure.** Split a component when it mixes
  separate responsibilities or repeats a pattern; do not fragment cohesive, single-purpose
  markup merely to hit a line count.
- **Every kit component must be exercisable in the gallery** (§6.2) — a component that only
  renders inside a specific consumer screen has not actually been proven reusable.

---

## 4. 🧱 Runtime — Shell, Regions, Lifecycle

The runtime layer owns window chrome, navigation, the overlay host, and named regions that
consumer screens contribute into: `ContributionRegistry`, `RegionHost` and `RegionKind`
(`runtime/`, `TASK-043`), extended by `EPIC-008` with toolbars of actions, View-menu toggles
and remembered perspectives (`RegionHost.place_action`, `dock_toggle_actions`,
`PerspectiveStore`).

- **A screen contributes; it does not build layout.** What region a piece of UI belongs in
  (toolbar, primary content, sidebar, status) is a declaration from the screen; how that
  region resolves size, placement and splitter behaviour is the runtime's decision, not the
  screen's.
- **Screen lifecycle is a behavioural contract, not a shape contract.** A screen must
  support `mount()`/`unmount()`, react to `ui_mode`, and `shutdown()` cleanly while
  background work may be in flight — it is not required to contain any particular widget or
  look a particular way. `BasePresenter`/`BaseView`'s existing `apply_ui_mode()`/duck-typed
  FSM binding is the precedent this generalizes from.
- **Thread safety is non-negotiable.** UI mutation from a background thread is a defect
  class this extension already guards against (`thread_affinity`, `safe_ui_action`,
  `UIWatchdog`) — the runtime layer must not introduce a path that bypasses those guards for
  the sake of a convenient API.
- **The runtime must not know the consuming application.** A registered contribution is fed
  by the consumer's own presenter/view-model layer; the runtime never reaches toward
  application domain state to decide what to render.
- **An embedded QML scene is opaque, and its background is a token.** `create_quick_widget()`
  clears every `QQuickWidget` to an opaque colour resolved from a theme token
  (`runtime/quick_background.py`, default `"bg"`; a widget embedded in a card passes that
  surface's own token). `setClearColor(Qt::transparent)` is never the way to "let the parent
  show through": on the texture rendering path of every real desktop session Qt punches a hole
  in the widget backing store under the scene and composites the texture over a black (or, on
  Wayland, see-through) clear — the parent's background is not there to show. Only the
  software path (`offscreen`, `widget.grab()`, i.e. every headless test) behaves the way that
  comment assumes, which is how the reference consumer shipped ten black/see-through QML
  bodies behind a green suite (`Sagittarius_Elite_Warrior` `BUG-102`/`BUG-115`, `TASK-042`).

---

## 5. 🔒 Security & Quality Baseline

- **Plain text for outside data, QtWidgets too:** a `QLabel` showing a value that
  originates outside the code (a log line, an exchange's error message) sets
  `Qt.TextFormat.PlainText`; `ReadoutForm` and `EmptyStateStack` do.
- **Enforce `textFormat: Text.PlainText`** on any `Text` item rendering data that
  originates outside the QML file itself (log lines, error messages, any value that could
  contain markup), to prevent HTML/RichText injection through display text.
- **`ListView`/`TableView`/repeated delegates backed by data that can exceed roughly 20 rows,
  update incrementally, or require virtualization** must be backed by a Python
  `QAbstractListModel`/`QAbstractTableModel`, not a QML-side array transform. A small static
  or one-shot list may stay QML-only when QML is not transforming domain data.

---

## 6. 🧪 Testing & Verification

### 6.1 Kit-level

- Every kit component constructs cleanly under `QT_QPA_PLATFORM=offscreen` with zero QML
  warnings and zero unbound-property errors.
- The anti-literal test (§2.2) and the anti-raw-primitive test (§1, no visual primitive
  authored outside the kit or a valid escape) are both required, automated, and run in CI —
  not a documentation-only rule a reviewer is trusted to catch by eye. This repository has
  direct precedent for exactly this failure mode: a rule that says "must" with nothing
  automated behind it gets silently violated at scale.

### 6.2 Gallery — required, not optional documentation

Every kit component must be reachable from a single runnable gallery covering every
documented state (idle/hover/active/disabled, populated/empty, etc.). A design system with
no way to see everything it offers in one place is not verifiable — and is precisely how a
consumer ends up re-implementing something that already existed, because there was no way to
check first.

**Registering a component in `qmldir` without adding it to the gallery is incomplete work.**
Enforced by `kit/gallery_coverage_guard.find_types_missing_from_gallery()`, which fails when
a registered type is never declared in the gallery. It is a *presence* check by design — it
cannot judge whether a component is demonstrated well, only that whoever added it had to look
at it. The expensive failure is a component nobody ever sees, not one whose demo is thin.
This caught a real gap on its first run: `DateTimePicker` had been registered since before
the gallery existed and had never appeared in it.

Exemptions live in `DEFAULT_EXEMPT_TYPES` and require a structural reason, not convenience —
today only `BaseCard`, which has no standalone appearance and is shown through every card
deriving from it. A component that is genuinely internal should not be in `qmldir` at all;
that is the correct fix, not an exemption.

**The gallery must be runnable interactively, not only as a snapshot.** `scripts/show-gallery.ps1`
opens a real window by default and takes `-Snapshot` for a headless PNG. Hover, press, focus
and modal open/close states do not exist in a still image — roughly half of what
`StatefulButton` and the input controls actually do is invisible to the PNG path alone, so a
snapshot is evidence the kit *parses and lays out*, not that it *behaves*.

### 6.3 Runtime conformance suite

Once the runtime layer exists (`EPIC-001D`), one conformance test suite applies to **every**
registered screen, including screens not yet written: repeated mount/unmount without
leaking, clean shutdown with background work in flight, correct response to every `ui_mode`,
complete self-declared metadata. A screen that violates the lifecycle contract fails this
suite; it is not something each consumer screen re-proves for itself.

---

## 7. 🏷️ Naming Conventions

- **Properties**: `camelCase` (`isActive`, `layoutHint`, `resizeBehavior`).
- **Signals**: `camelCase` verb phrases (`clicked`, `stateChanged`, `runRequested`).
- **Token names**: semantic, not literal (§2.1) — describe purpose, not value.
- **Every interactive kit element** declares both a QML `id` (readable bindings) and a
  stable `objectName` (the automation/test contract). Do not rely on a generated index as
  the only test identity for a repeated delegate.

---

## 8. 🔌 Consumption Model

- A consuming application depends on this extension as a package dependency (see
  `install-rule.md`), never by copying kit source into its own tree. A copied component is
  already a fork the moment it is copied — it stops receiving token/behaviour fixes and
  becomes exactly the kind of drift this boundary exists to prevent.
- The engine ships with **no opinion on any specific application's domain** — no screen
  names, no business terminology, anywhere in `pyside_mvc`. If a rule, component, or token
  name references a concrete consuming application, it does not belong in this repository.

### 8.1 Only the top-level package is a supported import surface

A consuming application imports exclusively from
`sagittarius_engine.extensions.pyside_mvc` — never from a submodule path
(`...pyside_mvc.tokens.theme_bridge`, `...pyside_mvc.runtime.qml_host_view`, etc.), no
matter how stable that path looks today. `tokens/`, `kit/`, `runtime/`, `mvc/`, `safety/`,
and the per-component layout under `Sagittarius/UI/` are internal organization, free to
change without notice; the top-level `__init__.py` re-export list is the only contract this
extension keeps.

This is not a style preference: `EPIC-001C`'s directory-per-component reorg found the
reference consumer already had 2 real imports reaching past the re-export surface directly
into `...pyside_mvc.base_view` and `...pyside_mvc.QmlShared.log_list_model` — discovered only
by grepping the consumer's source before moving those files, not by anything in this repo
catching it in advance. A facade nobody is required to use is optional discipline, not a
guarantee.

`import_boundary.find_deep_imports()` is the enforcement mechanism, importable by a
consuming app's own test suite the same way the two QML guards are (§1.2/§3). It exempts a
short, explicit, reviewed allowlist (`SANCTIONED_DEEP_IMPORTS`) for pre-existing consumers
that predate this rule — not an escape hatch for new code, and not the same mechanism as
§1.1's component escape hatch (that one frees behaviour inside a component; this one draws
the outer edge of the whole extension). A sanctioned entry shrinks when the referencing
consumer is updated, never grows because a deep import happened to be convenient.

---

## 9. 🪟 The QtWidgets Workbench Contract

### 9.1 Sources, and which one wins

Every clause below names its source (read 2026-10-04, `ADR-003`): **MS** = Microsoft Windows
User Experience Interaction Guidelines (`learn.microsoft.com/en-us/windows/win32/uxguide/<page>`;
Microsoft says they still apply in principle); **Fluent** = Microsoft's Windows app design
guidance; **KDE** = KDE Human Interface Guidelines (`develop.kde.org/hig`); **Apple** = Apple
HIG; **GNOME** = GNOME HIG; **Qt** = `doc.qt.io/qt-6`. Where they disagree, the Windows
desktop choice wins, and Qt's platform-aware API settles the detail, so the same code is
right on every platform: button order through `QDialogButtonBox`, metrics through
`QStyle.pixelMetric`, standard shortcuts through `QKeySequence.StandardKey`, Tools → Options
with `QKeySequence.Preferences` (empty on Windows by the platform's own definition), Windows
capitalisation.

### 9.2 Stock controls in the platform style

- Every control is a stock Qt class constructed with its defaults; one look per control kind,
  the platform's. MS `vis-fonts`: "always using the system font, sizes, and colors"; KDE:
  avoid custom styling; Qt `qtwidgets-styling-approaches`: style sheets are "not for the
  production look of an application".
- No per-widget style sheet, palette, font family or fixed/minimum/maximum size on a control:
  the style's metrics decide (MS `vis-layout`: a standard button is 75×23 px at 96 dpi
  because the style says so). Margins and spacing are the layout's defaults.
- Colour only where it carries meaning, from `QPalette` roles, never an RGB literal, never as
  the only signal (MS `vis-color`); usable in Windows High Contrast.
- No widget drawn over another (`move()` onto a canvas); controls live in toolbars, docks,
  dialogs or context menus. No scroll area inside a scroll area.
- No checkable push button: state is a check box, a radio button or a checkable action
  (MS `ctrl-command-buttons`, KDE).

### 9.3 Commands: one `QAction` each

- A command is an `ActionDescriptor` contributed to `ActionRegistry` (`workbench/`): one
  `QAction` shared by its menu entry, toolbar button and shortcut (Qt, "Actions";
  MS `cmd-menus`). Every command is in a menu (`menu_path` is mandatory), with one exception:
  a pane's local commands (`OutputPane`'s Copy and Clear) live in its own toolbar and context
  menu, as in Visual Studio's Output window, and take no window shortcut of their own; a toolbar holds
  actions only (`RegionHost.place_action` refuses a button widget) (MS `cmd-toolbars`); a consumer
  still migrating opts in to bare toolbar widgets with `legacy_toolbar_widgets=True`, visibly.
- Text: sentence case, exactly one access key per item (`&`, `&&` for a literal ampersand),
  unique among its siblings: the menu-bar titles, and the items and submenus of one menu; a
  menu is spelled one way in every mode. "…" (U+2026) exactly when the command asks for more
  before it acts (MS `cmd-menus`, KDE, Apple). `action_text.text_problems()` checks one text;
  `ActionRegistry.contribute()` checks siblings and spelling.
- Shortcuts: a standard command takes its `QKeySequence.StandardKey`; a new one takes Ctrl+J,
  Ctrl+L, Ctrl+digit, F7, F8, F9 or F12, never Ctrl+Alt: Microsoft's free set less the keys
  KDE, GNOME, XFCE or macOS reserve (Ctrl+G, K, M, Q, R, T; `RESERVED_ELSEWHERE` names each
  use), so the same set is free on every platform (MS `inter-keyboard`; `shortcut_policy.py`).
  The registry also refuses any key the running platform reserves.
- Inapplicable commands are disabled, never hidden (MS `cmd-menus`, Apple); an unbound command
  stays disabled and `report_unbound()` logs it.
- Confirm only risky or irreversible commands, as data (`ActionConfirmation`): the consequence
  in a sentence, specific verbs (never OK/Yes), the safe answer the default and the escape
  (MS `mess-confirm`; `build_confirmation_box()`).

### 9.4 Dialogs and options

- Commit buttons come from `QDialogButtonBox` with standard buttons, so the platform orders
  them; one default button, the safe one; Esc and the title-bar close act as Cancel
  (MS `win-dialog-box`, Qt `QDialogButtonBox`). A dialog's title names the command.
- Configuration is one dialog, Tools → Options (`OptionsDialog`, no ellipsis, shortcut
  `QKeySequence.Preferences`): sections on the left, pages on the right, OK / Cancel / Apply;
  Apply enabled only while a page is dirty; OK disabled, with the reason shown, while a page
  is invalid; Cancel, Esc and the title-bar close revert every page (MS `win-dialog-box`).
  Each module contributes an `IOptionsPage`; a page never saves on its own.
- Messages a user may want to read later go to the one Output pane (`OutputPane`, Visual
  Studio's Output window): a channel per source (`OutputChannel` over a `LogListModel`),
  read-only lines, Copy and Clear as the pane's own commands.

### 9.5 Modes, panels and perspectives

- One `QMainWindow` shell with a mode per job (`WorkbenchShell`); each mode a `RegionHost`:
  a central widget, docks, toolbars (Qt Creator's shape). The menu bar reads File, Edit, View,
  the application's menus, Tools, Window, Help (MS `cmd-menus`; `shell_menus.menu_order`),
  each filled when it opens with the showing mode's commands; a menu with nothing in it is
  disabled. Related commands sit together, one separator between adjacent groups
  (`ActionDescriptor.group`, `ActionRegistry.menu_action_groups`) and before the shell's own
  extras, never at either end of a menu and never two in a row. A vertical mode bar (icons only, Ctrl+1…9) switches modes through
  `NavigationService`, which asks the mode being left `can_leave(USER_INTENT | RESTORE)`.
  Only the showing mode's commands are live, so two modes may share a key. The window
  remembers its geometry and last mode (`WorkbenchShell` is an `IStateContributor`). A panel is a `QDockWidget` with a title, a close
  button and its content; every dock and toolbar has a stable object name and a toggle a View
  menu lists (`dock_toggle_actions`, `toolbar_toggle_actions`).
- The default layout is what contributions build (`capture_default_perspective`); Window →
  Reset layout restores it (`reset_perspective`). The user's layout is saved per mode and
  restored on start, keyed by mode and layout version; a version mismatch restores the
  default and logs once (`PerspectiveStore`).

### 9.6 Tables, lists and read-outs

- A display widget is configured by the kind of value it shows, never per view
  (`configure_item_view`, `ColumnKind`, `ColumnSpec`): whole-row selection, no in-place
  editing, sorting on the raw value (`SpecProxyModel.lessThan` orders numbers, `Decimal`,
  `datetime`, `timedelta` and text, unknown last ascending — `display_value_order`), numbers right-aligned and text and dates left
  (MS `ctrl-list-views`), movable columns remembered per view (`ItemViewStateStore`), the
  first click on a header sorting ascending. Values are written by one `IValueFormatter`
  through `KindDelegate` and `ReadoutForm`; the consumer supplies precision, the engine the
  place it is applied. A value's quantum (a price's tick, a quantity's step) reaches the
  formatter as `FormatContext.precision`, a `Precision` from the column
  (`ColumnSpec.precision`) or from the cell (a model answering `PRECISION_ROLE`), the cell's
  winning.
- The `ColumnSpec.stretch` column takes the width the others leave but never less than its
  content (`StretchColumnFiller`, not Qt's `Stretch` mode, which squeezes it to the minimum
  section size in a narrow dock); a view narrower than its columns scrolls horizontally with
  every column whole. A view's size hint follows its columns on first show
  (`AdjustToContentsOnFirstShow`), so a dock opens wide enough for them.
- A grouped tree — headings with rows under them — is a `QTreeWidget` configured the same
  way (`configure_item_view(tree, None, specs)`), its rows `SpecTreeItem`s holding raw values;
  sorting orders each heading's rows among themselves. `sortable=False` turns sorting off on
  any view whose order is its meaning.
- An empty view says what to do (`EmptyStateStack`; MS `ctrl-list-views`).
- `find_unconfigured_item_views()` is the guard a consumer's booted-app test calls.

### 9.7 Feedback

- Anything taking 2 s or more shows feedback; past about 5 s a determinate progress bar where
  possible; an operation with side effects stops with "Stop", not "Cancel"
  (MS `progress-bars`). The status bar carries useful, non-critical state in plain text, never
  an alarm alone (MS `ctrl-status-bars`). Errors name what failed and what to do
  (MS `mess-error`, KDE).
