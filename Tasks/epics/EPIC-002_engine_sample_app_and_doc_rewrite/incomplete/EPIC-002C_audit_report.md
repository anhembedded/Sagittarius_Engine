# EPIC-002C — Audit Report

**Epic:** [EPIC-002 — Engine Sample App & Doc Rewrite](../README.md)
**Status:** 🔵 Backlog
**Category:** Documentation / Developer Experience
**Priority:** P1
**Depends on:** EPIC-002A, EPIC-002B (needs the build experience to report on)

---

## 🎯 Summary & Objectives

Turn everything hit while building EPIC-002A/B into `AUDIT_REPORT.md` — a durable, evidence-
based record that EPIC-002D rewrites the docs from. This subtask is pure writing; it adds no
code.

1. One `AUDIT_REPORT.md` (location: this epic's own directory), covering, at minimum:
   - Every implicit assumption the engine makes that isn't written down anywhere (token
     requirements, `IExtension` ordering constraints, DI resolution quirks, event bus
     semantics — whatever actually came up).
   - Every place the old `.agents/context/*.md` claims were tested against the sample and
     found to hold, versus found wrong — don't just carry forward EPIC-002's own README
     evidence table; verify it still applies after EPIC-002A/B's changes.
   - Every engine module that was skipped in EPIC-002A, with the justification already
     recorded there, restated here so the audit is self-contained.
   - Any point where "the reasonable thing to do" and "what the engine actually required"
     diverged — these are exactly the findings `.agents/rules/surprising-findings.md` exists
     to capture, so they should already be visible in this session's replies; consolidate
     them here rather than re-deriving.
2. Each finding gets a clear disposition: **doc fix** (feeds an EPIC-002D task), **engine gap**
   (named, out of scope for this epic, flagged to the user), or **working as intended,
   surprising anyway** (recorded so the next person doesn't re-discover it the hard way).
3. No finding without evidence — a file/line, a command output, or a reproduction. This
   mirrors the standard `design-discipline.md` sets for code fixes: "it seemed off" is not a
   finding, it's a lead.

## 📐 Design Constraints

- This subtask does not fix anything it finds — including in the sample app itself, if a
  cleaner approach becomes obvious in hindsight. Record it; EPIC-002A/B's code is what it is
  by the time this subtask runs.

## 🧪 Verification & Test Coverage

Not applicable in the usual sense — the deliverable is the document. Verification is: every
claim in `AUDIT_REPORT.md` traces to something checkable (a path, a command, a line number),
and every item in EPIC-002A/B's own "written account" sections is represented somewhere in it.
