# Epic EPIC-001 — UI Engine Foundation

> **New to this epic? Read [`ONBOARDING.md`](ONBOARDING.md) first.** It is the entry point
> for any AI session picking up work here — reading order, decisions already settled and not
> to be relitigated, current state, and the cross-repo trap that catches new sessions most
> often.

**Status:** 🟡 In Progress — 3/4 subtasks fully done (2026-08-23: `A`, `B`, and now `C` — data
table, gallery, anti-raw-primitive test, anti-Rectangle-as-card test, AppModal, a real
screenshot). `D`'s dependency on `B`+`C` is now satisfied, but `D` itself has not been
started — see `EPIC-001D`'s own file before picking it up.
**Source:** Direct user decision (2026-08-22) — `Sagittarius_Elite_Warrior`'s presentation
layer has no unified design philosophy across its 4 screens; each was built independently
with its own hosting, styling and component choices. Decision: build a proper **UI Engine**
as an extension of `Sagittarius_Engine`, then migrate the app onto it screen by screen.

---

## 1. Context

An architecture review of the app repo (`Sagittarius_Elite_Warrior`) found the underlying
mechanism, not isolated one-screen bugs:

| Measured (2026-08-22) | |
| :--- | ---: |
| Hardcoded colour literals in app QML | **342**, 97 distinct values, 25/27 files |
| Official palette tokens | 14 |
| Shared `StatefulButton` component actually used | 2/27 files |
| Raw `Button {}` still hand-rolled | 56 |
| Hand-rolled `ListView` tables, no shared component | 5 |
| QML files over the project's own 300-line review threshold | 8 |

The clearest evidence: the most common colour literal in QML is **not** the official accent
(`#F3BA2F`) but a near-duplicate nobody intended to create (`#f0b90b`, 29 uses) — proof the
palette and the QML have drifted apart, not that anyone made an error on purpose.

**Why this belongs in the engine, not the app:** a convention living in the app's own
`components/` directory is optional — it already was, and it drifted. A convention the app
literally cannot import around (because the only widgets available come from the engine) is
structural, not disciplinary. This is also why `.agents/rules/ui-architecture.md` had to be
rewritten first (`EPIC-001A`) — the existing rule describes a QtWidgets/QFrame/QSS world
that no longer matches what ships, and doctrine that contradicts reality gets ignored.

## 2. Shape of the solution — three layers, sequenced by risk, not by interest

```
Tokens        → sinks all visual values (colour, spacing, radius, type, motion)
Widget Kit    → QML components that render tokens; nothing else may
Runtime       → shell, regions, navigation, screen lifecycle; built LAST
```

The ordering is deliberate and inverted from what feels natural: the runtime (shell, slot
registry, navigation) is the most visible and interesting part of the idea, but it is also
the most speculative — it requires knowing which widgets exist and which surfaces are
genuinely dynamic, which isn't reliably known until the layers under it are real and have
been used. Tokens first because they are cheap, lock in nothing, and pay off immediately.

**The single test for whether this succeeded:** change one token — accent colour, corner
radius, spacing — and count how many app files must change. The target is zero. Any number
above zero at any point means the app is still deciding visual values itself, which is the
condition this epic exists to end.

## 3. Decisions already settled (do not re-litigate — see `EPIC-001A`)

- **Grows `pyside_mvc` in place** — no parallel UI extension. A second UI home would split
  the theme bridge and `OverlayHost` across two places and reproduce the drift this epic
  exists to end.
- **Escape hatch:** permitted, but only via single-level inheritance from the matching
  engine base primitive (e.g. `BaseCard`) — never a bare `Rectangle`/`Item`. This keeps
  every visual value token-driven even when a screen needs bespoke behaviour; only
  behaviour is free, never pixels. Each use must be named and justified at the call site.
- **Token vocabulary:** fixed and owned by the engine (`accent`, `danger`, `spaceMd`, …);
  the app fills values, it does not invent names. This is what makes engine-side
  "did the app supply every required token" validation possible.

## 4. Subtasks

| ID | Name | Risk | Status |
| :--- | :--- | :---: | :---: |
| **[EPIC-001A](completed/EPIC-001A_architecture_rule_rewrite.md)** | Architecture Rule Rewrite & Ownership Boundary | 🟢 | ✅ Done (22/08) — no code, governance only |
| **[EPIC-001B](completed/EPIC-001B_design_token_layer.md)** | Design Token Layer — fixed colour vocabulary, bootstrap validation, anti-literal-colour test | 🟢 | ✅ Done (22/08) — 19 new tests, 481 passed total, 0 new mypy errors |
| **[EPIC-001C](completed/EPIC-001C_widget_kit_expansion.md)** | Widget Kit Expansion — data table first, gallery, anti-raw-primitive test | 🟢 | ✅ Done (23/08) — table+gallery+both guards+AppModal delivered |
| **[EPIC-001D](incomplete/EPIC-001D_runtime_slot_registry.md)** | Runtime, Regions & Slot Registry — shell, contribution model, lifecycle conformance suite | 🟡 | 🟡 Unblocked (`B`+`C` done) — not yet started |

**Dependency order:** strictly `A → B → C → D`. `A` is governance-only and unblocks
everything; `B` and `C` are the cheapest, lowest-risk, highest-payoff work and should absorb
most of the near-term effort; `D` is deliberately last because it is the most speculative
layer — building it early means designing its abstractions with the least information
available.

## 5. Out of scope for this epic

- Migrating any `Sagittarius_Elite_Warrior` screen onto the finished engine — tracked on
  that repo's own board as `EPIC-005`, once it exists there. The two boards are independent
  by convention (`Sagittarius_Elite_Warrior/.agents/ONBOARDING.md` §9) and must not mix.
- Unifying `Sagittarius_Elite_Warrior`'s screen-hosting model (`QmlHostView` vs. hand-built
  `QSplitter` per screen) — a real, related problem, but one that belongs to the app repo's
  migration epic, not to building the engine itself.
