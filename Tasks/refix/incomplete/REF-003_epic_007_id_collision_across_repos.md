# REF-003: `EPIC-007A..F` cited in 8 documents meaning Elite Warrior's epic vs. this repo's own `EPIC-007`

- **Status**: 🟠 Open
- **Category**: Documentation / Naming
- **Found while**: numbering this repository's `EPIC-007_runtime_state_console` (2026-08-27)

---

## 1. The disagreement

`Tasks/epics/README.md`'s numbering rule: *"the next epic takes the highest existing number
in `Tasks/epics/` + 1."* This repository's `Tasks/epics/` topped out at `EPIC-006`, so the
runtime state console correctly took `EPIC-007`.

But eight documents **already in this repository** use `EPIC-007A`…`EPIC-007F` to mean
`Sagittarius_Elite_Warrior`'s `EPIC-007_chuan_hoa_card_dung_chung` — a different repository's
epic, referenced here because it caused defects in shared code:

```
sagittarius_engine/extensions/pyside_mvc/tokens/defaults.py:46
sagittarius_engine/extensions/pyside_mvc/tokens/vocabulary.py:57
Tasks/bug_report/completed/BUG-004_overlay_names_nonexistent_subclasses.md
Tasks/bug_report/completed/BUG-004_overlay_names_nonexistent_subclasses.md (second reference)
Tasks/bug_report/completed/BUG-009_statcard_badge_tone_stopped_rendering_after_bug008.md
Tasks/bug_report/completed/BUG-012_tab_button_ignores_its_own_content_when_sizing.md
Tasks/bug_report/completed/BUG-008_apply_role_qss_cascades_into_every_child.md (two references)
```

So `EPIC-007A` is now genuinely ambiguous inside this repository: it means Elite's epic in
eight places written before 2026-08-27, and this repository's own `EPIC-007A` (the snapshot
contract, done) from that date forward.

## 2. Why the number was taken anyway

`design-discipline.md`: *"If the correct fix contradicts a rule, then either the rule is
wrong or the design is — resolve that, in the rule file, as its own change. Never route
around a rule silently."* Skipping to `EPIC-008` to dodge the collision would be exactly that
routing-around: it would hide the fact that `Tasks/epics/README.md`'s numbering rule has no
provision for a number already meaning something else in prose, even though it has never
been used as a directory here.

So `EPIC-007_runtime_state_console/README.md` was given a named warning banner at the top
(quoting all eight prior references) and a citation convention: `EPIC-007x` inside this
repository, `Elite EPIC-007x` when referring to the other one. That is the interim state
this refix exists to close out properly.

## 3. Proposed reconciliation (not yet applied)

Two independent moves, either of which resolves the ambiguity; doing both is redundant but
not harmful:

1. **Qualify the eight existing references.** `defaults.py:46` and `vocabulary.py:57` become
   `Elite EPIC-007F` / `Elite EPIC-007B` in their comments; the four `BUG-XXX` files under
   `Tasks/bug_report/completed/` get the same qualification at each citation. Low-risk,
   comment-only changes, but eight files across two directories — its own reviewable diff.
2. **Retitle this repository's epic directory** to something collision-proof
   (`Tasks/epics/EPIC-007_runtime_state_console/` already carries a descriptive slug; the
   risk is only in the bare `EPIC-007` short form). Rejected as the primary fix: it would
   make *this* repository's epic accommodate a naming collision that originated in a
   different repository's history, which inverts which side should yield.

**Recommendation: do (1).** The eight references are historical citations of settled,
completed work (`BUG-004`, `BUG-008`, `BUG-009`, `BUG-012` are all ✅ done); qualifying them
costs nothing going forward, whereas leaving this repository's active epic under an
awkward name to avoid a collision with finished work in another codebase costs something
every time `EPIC-007` is mentioned here from now on.

## 4. Why left open rather than fixed here

The banner in `EPIC-007_runtime_state_console/README.md` already makes the collision
unambiguous to any reader who opens that file, which was the load-bearing fix needed before
`EPIC-007` could safely be used at all. Qualifying eight files across `pyside_mvc/tokens/`
and `Tasks/bug_report/completed/` is unrelated to the epic's own content and — per
`design-discipline.md`'s standing guidance on scope — belongs in its own change, not folded
into commits about the state console.
