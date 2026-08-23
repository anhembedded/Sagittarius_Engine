# EPIC-002D — Doc Rewrite & Staleness Guard

**Epic:** [EPIC-002 — Engine Sample App & Doc Rewrite](../README.md)
**Status:** 🔵 Backlog
**Category:** Documentation / Developer Experience
**Priority:** P1
**Depends on:** EPIC-002C (rewrites from the audit, not from memory)

---

## 🎯 Summary & Objectives

Rewrite `.agents/context/` using `AUDIT_REPORT.md` as the source of truth, and add a
mechanism so it cannot silently rot the way it just did (one commit, 2026-08-02, wrong by
2026-08-23 with nobody noticing for three weeks).

1. **Restructure or fully delete-and-rewrite `.agents/context/` — your call, decided per
   file, not a fixed policy.** User's explicit instruction: *"co the tai cau truc lai doc,
   hoac xoa het viet lai"* (can restructure, or delete everything and rewrite). A file that's
   mostly right (e.g. `testing.md`, unaudited so far — verify) may only need a factual patch;
   a file `AUDIT_REPORT.md` shows is structurally wrong (`repository.md`'s wrong repo name,
   `modules.md`'s `IModule`-as-the-model framing) should be deleted and rewritten from zero
   rather than patched into something that still carries its original, wrong shape.
2. **Separate what rots from what doesn't**, per the pattern already validated by this
   session's audit of `architecture.md`:
   - Facts fully derivable from code (directory trees, class lists, method signatures) —
     minimize hand-written duplication; where a list must exist, keep it exhaustive and
     dated, not illustrative.
   - Decisions and their reasons (why `IExtension` replaced `IModule`, why tokens are
     engine-owned) — these don't go stale the same way; keep them, and keep them adjacent to
     the evidence that grounds them.
   - Traps (lifecycle override/call split, `QT_QPA_PLATFORM` offscreen default,
     `QQuickWidget.errors()` blindness) — highest value per byte; pull these from
     `AUDIT_REPORT.md` and `design-discipline.md`/`surprising-findings.md` almost verbatim.
3. **Point every context doc at the sample app** where it illustrates a real pattern — the
   sample is the reference now (see epic README's framing), and a doc describing "how a
   consumer wires an extension" should cite the sample's actual file rather than an invented
   snippet, per this repo's own `design-discipline.md` root-cause standard.
4. **Fix the 4 dangling references** to the deleted old `examples/student_management/`:
   `readme.md:131`, `.agents/context/examples.md`, `.agents/context/modules.md`,
   `.agents/skills/module_discover.md` — point them at the new sample.
5. **Add a staleness-detection test.** One test, scanning `.agents/` for backtick-quoted
   `ClassName`/`module.path`/`dir/path` tokens and asserting each resolves against the real
   tree (via `ast`/`importlib`/`pathlib`, whichever is cheapest to keep correct). This is what
   would have caught `AppRunner`, `Sagittarius_ForkBoy`, and `extensions/sqlalchemy` on day
   one instead of three weeks later. False positives (prose that happens to look like a path)
   are an acceptable cost — an explicit ignore-list is fine, an unchecked doc is not.
6. Register this epic's outcome in `Tasks/README.md`'s epic table and `Tasks/epics/README.md`
   per the standing convention (this epic itself, once EPIC-002A starts, should already be
   listed — verify it still is by the time this subtask runs).

## 📐 Design Constraints

- Do not soften a doc's claim to make it "not wrong anymore" without checking whether the
  underlying rule/behavior itself needs a decision (`design-discipline.md`'s 3-step: cause →
  check against written rules → then write). A doc rewrite is still a design-discipline
  situation, not a free pass to reword around a real problem.
- Keep `ui-architecture.md` and `design-discipline.md` as the reference for *how* a rule file
  earns trust (dense, example-grounded, dated evidence) — this subtask's output should read
  at the same level, not regress to the old `context/` style.

## 🧪 Verification & Test Coverage

- The staleness-detection test exists, passes against the rewritten docs, and is proven to
  actually catch drift (write it against the *old*, since-deleted `repository.md` content
  first — from git history — confirm it would have failed, then confirm it passes clean).
- Every claim in the rewritten `.agents/context/*.md` traces to either the sample app, the
  audit report, or a direct code citation — no claim restored from the old files without
  re-verification.
- `.agents/ONBOARDING.md`'s context/rule routing tables still resolve every listed file
  (`PLAYBOOK.md`/`manifest.yml` were retired 2026-08-23 in favor of this file — see its own
  §5 "known duplication" note, which this subtask resolves).
