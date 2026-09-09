# EPIC-008: Runtime State Console — UI Redesign

- **Status**: 🟡 In Progress (1/6 subtasks done)
- **Created**: 2026-09-09
- **Priority**: P2
- **Category**: UI Engine (`pyside_mvc`) / Tooling
- **Builds on**: `EPIC-007` (Runtime State Console — shipped, `main`). This epic does not
  change what the console shows or how it collects data; it changes how it looks and adds the
  interaction affordances (connect flow, sortable tables, cross-section jump links, rail
  signal-count badges) that `EPIC-007E`'s minimal shell never grew.
- **Reference**: [`reference/handoff.md`](reference/handoff.md) — a design handoff produced by
  an external design AI from `EPIC-007`'s own functional feature set (see that file's own
  header for provenance and for what is/isn't actually attached to this repository).

---

## 1. What this builds

`EPIC-007` shipped a working console: a real WebSocket transport, five real screens, real data
all the way from `ResilientEventBus`/`BaseStateMachine`/`ITaskManager` to the wire. What it
never got was a real shell — `ConsoleShellView` (`tools/state_console/presentation/shell/`) is
a plain `QWidget`/`QPushButton` sidebar with no connection-status chrome, no way to attach to a
backend without a CLI flag at launch, no rail badges, and no sortable tables. `reference/
handoff.md` specifies that shell, a six-state connection model (vs. the shipped three), and a
new visual language ("Industry": steel-blue, Barlow Condensed, hairline borders, blueprint
grid) for the five existing screens.

**This is a redesign and feature-extension of a working tool, not a rebuild.** The transport,
the collectors, and the wire contract (`StateSnapshot` in `extensions/audit/contracts.py`) are
correct as shipped and are out of scope here — see §4.

## 2. Architectural decisions this epic is bound by

`ui-architecture.md` governs this work, not just style — a redesign of a `pyside_mvc` consumer
is exactly the case that document's ownership boundary (§1) exists for. Two decisions, made
before any screen work starts, so subtask A doesn't reinvent them mid-flight:

### 2.1 New colours are derived, not duplicated

The handoff's `fault`/`fault-fill`/`on-fault`/`fault-text` read, functionally, as shade/role
variants of one semantic idea the engine already names: `danger`
(`tokens/vocabulary.py:53`). Adding a parallel `fault` vocabulary would mean two names for one
concept — exactly the drift `ui-architecture.md` §2.1 exists to prevent, and it would still
need `accent-100…900`/`neutral-100…900` ramps on top, which as *nine independent literal
tokens per colour* is the token-count explosion §2.1 also warns about.

**Decision:** `EPIC-008A` adds a small tint/shade **derivation utility** (fed the four existing
required semantic colours — `accent`, `success`, `warning`, `danger` — computing fill/on-fill/
text variants and 100–900 ramps at bootstrap), not nine new literal tokens per colour. The
*existing* `danger` token is what the handoff calls `fault`; no new required colour token is
added for it. Only genuinely new concepts get new token names: `surface`, `chrome`, `divider`,
`hatch`, `gridLine`, and an `ink` RGB triplet (for alpha-composited text/border opacities, e.g.
`Qt.rgba(Theme.inkR, Theme.inkG, Theme.inkB, 0.45)`) — see `EPIC-008A` for the exact list and
whether each lands as required or default-backed (`tokens/vocabulary.py` vs `tokens/
defaults.py`).

### 2.2 Shared chrome is kit, not consumer

Per `ui-architecture.md` §1.2 ("a component owns what is the same on every use"), anything the
handoff describes once but that every screen needs is kit-level, not
`tools/state_console`-local: the six-state connection band, the heartbeat ribbon, rail
signal-count badges, sortable `AppDataTable` columns, and an expandable table row. The
connect-flow's *domain* knowledge (what a socket address means, the three failure-kind
copy blocks) stays in `tools/state_console` — that is tier-2/3 knowledge specific to this one
consumer, per the same rule's worked examples. Each new kit component needs a gallery entry
(§6.2) and, if it renders untrusted text, `Text.PlainText` (§5).

## 3. Milestones

Same shape as `EPIC-007`: **every subtask ends in a command a reader can run and a screenshot
of what it produces** — this is a visual product; a passing test suite proves it parses, not
that it looks right.

| ID | Scope | Runs as | Done when |
| :--- | :--- | :--- | :--- |
| **[A](completed/EPIC-008A_design_tokens_and_shared_shell.md)** ✅ | Token derivation utility + new token names (§2.1); `LiveConnectionBand`, `AppRail` (badges), `AppDataTable` row expansion — all in `pyside_mvc`, all in the gallery | `scripts/show-gallery.ps1` | ✅ **Done 2026-09-09** — 4/5 planned items shipped as kit work (40 new tests); the 5th (connect-flow input primitives) resolved to "no new kit component" per this repo's own `ActionCard/NOTES.md` two-consumer promotion rule and is composed in B instead — see A's own Outcome section |
| **[B](incomplete/EPIC-008B_shell_rebuilt_on_the_new_kit.md)** 🔄 | `tools/state_console` shell rebuilt on A: `ConsoleConnectionExtension` extended with `CONNECTING`/classified-`FAILED` events and live re-target (`EPIC-008A`'s gaps 1-2); the connect flow itself composed from existing primitives (`EPIC-008A`'s gap 3 resolution) — address entry, recents, `LiveConnectionBand` wired to the real connection; `AppRail` badges wired to real signal counts; Overview restyled | `.\scripts\run-console.ps1 -Demo` | Overview screen matches the reference visually; shell chrome (band, rail, badges) present on every screen; connecting to a different address works without restarting — §1 (`ConsoleConnectionExtension`) and §2 (shell chrome: `ShellPresenter`, `AppRail`/`LiveConnectionBand` wired in, real signal-count badges) done; §3-4 (connect flow, Overview restyle) not yet started |
| **C** | Events & wiring restyled: sortable columns, undeclared-event banner | `.\scripts\run-console.ps1 -Demo` | Sort persists across a snapshot refresh; undeclared rows visually unmissable |
| **D** | Container restyled: registrations/never-built tables, open-scope leak emphasis | `.\scripts\run-console.ps1 -Demo` | Leak threshold styling verified against a live seeded-fault demo |
| **E** | Tasks & threads restyled: expandable failed-task rows, limits panels | `.\scripts\run-console.ps1 -Demo` | A failed task's stack is readable after a click, one at a time |
| **F** | Signals restyled: dead-letter cards, watched-machine transition log, UI-thread health cards | `.\scripts\run-console.ps1 -Demo` | Same real dead-letter/rejected-transition demo `EPIC-007F` used, now rendered in the new visual language |

**Order: A → B → C → D → E → F**, same reasoning as `EPIC-007`: A is shared infrastructure
every other subtask depends on (the status band and rail exist on every screen); B doubles as
A's proving ground before touching the other four screens in any order convenient.

## 4. What is deliberately not in this epic

- **Any change to the wire contract or the server-side collectors.** `StateSnapshot`,
  `TraceServer`, `StateConsoleExtension` (the extension attached to the *observed* app) are
  unchanged. `ConsoleConnectionExtension` — the *client*'s own connection wrapper, not part of
  the wire protocol — does change in `EPIC-008B` (new domain events, live re-target), which is
  the connect-flow UX gap named in `EPIC-007`'s own follow-up conversation, not new backend
  capability on the observed side.
- **A literal 1:1 port of the `.dc.html` prototypes' markup.** `reference/handoff.md` §2 says
  so directly: recreate the design in Qt/PySide's own idiom, not the web structure it happened
  to be prototyped in.
- **Enabling `Reprocess` or any other write action.** Unchanged from `EPIC-007` §6 — that is
  `ADR-003` territory, not a UI redesign.
- **A literal `FAILED`/`CONNECTING` two-step handshake if the current transport can't
  distinguish them cheaply.** `EPIC-008A` records this as an open question rather than
  assuming the six-state model is a free upgrade over the shipped three-state one — see its
  own "Gaps to resolve" section.
