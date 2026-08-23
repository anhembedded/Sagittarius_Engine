---
name: Documentation Follows Code
description: A code change that makes a doc claim false is not done until the doc is fixed in the same change. Documentation claims must be traceable to a real path, class, or test — not free-standing prose. Always applies.
trigger: always_on
---

# Rules: Documentation Follows Code

> Context: `.agents/context/` (16 files) was written once, in a single commit, and never
> touched again while 267 commits and +7028/-430 lines landed in `sagittarius_engine/`. It
> was discovered wrong three weeks later — a phantom class (`AppRunner`), the wrong repo name
> in its own first line, an extension that no longer exists, a module system (`IModule`)
> presented as canonical while the engine's own code calls it "legacy." Nothing forced the
> docs to move when the code did. This rule is that force.

---

## The rule

**A change to code that makes a doc claim false is not done until the doc is fixed too — in
the same change, not a follow-up task filed for later.**

Concretely, before finishing any change to `sagittarius_engine/` (rename, move, add, or
remove a class, module, path, interface, or documented behavior):

1. `grep` `.agents/` (context, rules, and this epic's own sample-app docs once
   [EPIC-002](../../Tasks/epics/EPIC-002_engine_sample_app_and_doc_rewrite/README.md) lands)
   for the old name/path.
2. If a doc names what just changed, update it in the same commit or session. Not a `TASK-XXX`
   filed for someday — the person best placed to update the doc correctly is whoever just
   changed the thing it describes, while the reason is still in their head.
3. If the doc update is genuinely too large for the current task's scope (e.g. it would
   require a structural rewrite), say so explicitly and flag it — per
   `surprising-findings.md` — rather than silently leaving the claim stale and moving on.

## Docs must be traceable, not just prose

A claim nobody can check against something real is a claim nobody will ever catch going
stale. In order of preference:

1. **Cite a real file/line/class name** over describing behavior in free prose.
2. **Point at a worked example in the actual codebase** (or the sample app, once it exists)
   over an invented snippet — an invented snippet can never be wrong, because nothing ever
   runs it.
3. **Prefer an enumerated, exhaustive list** (all packages, all lifecycle methods) **over an
   illustrative "e.g." list.** An illustrative list silently misses what's added later and
   looks no different whether it's current or three years stale. An exhaustive list is
   visibly incomplete the moment something new is added — see `architecture.md`'s "Engine
   Package Layout," rewritten 2026-08-23 to name all 11 top-level packages instead of 4.

This is why fixing `.agents/context/` is not "rewrite the prose more carefully" — that
produces a document exactly as failure-prone as the one it replaces. The fix is "ground every
claim in something checkable, and add a test that checks it" — see
[EPIC-002](../../Tasks/epics/EPIC-002_engine_sample_app_and_doc_rewrite/README.md).

## What failure looks like (real, found 2026-08-23)

| Doc claim | Reality | Why it went unnoticed for three weeks |
| :--- | :--- | :--- |
| `repository.md`: *"The `Sagittarius_ForkBoy` repository"* | Wrong repo name | Nothing reads this file except a human or an AI trusting it at face value |
| `repository.md` lists `extensions/sqlalchemy` | Renamed to `persistence` long ago | The rename didn't touch `.agents/` because nothing required it to |
| `modules.md` presents `IModule` as the module model | Engine code calls it *"a legacy `IModule`"* (`kernel/extension_manager.py:22`); `IExtension` is the real interface, unmentioned | `IExtension` was added without a corresponding doc update |
| `interfaces/i_engine_context.py:30` docstring names `AppRunner` | No such class exists; real orchestrator is `ApplicationRunner`, different constructor entirely | The class was renamed/replaced without a grep for its old name in docstrings |

Every row has the same root cause: a code change happened, and nothing asked "does a doc
claim this differently now?"

## Enforcement

A staleness-detection test ([EPIC-002D](../../Tasks/epics/EPIC-002_engine_sample_app_and_doc_rewrite/incomplete/EPIC-002D_doc_rewrite_and_staleness_guard.md))
is the mechanical backstop — it catches a path or class name that stops resolving. It cannot
catch stale *reasoning* (a rule whose premise quietly stopped being true, the way
`architecture.md`'s old `IEngineContext` constructor rule contradicted the engine's own
composition root). The test is necessary but not sufficient; this rule covers the rest.

## Don't over-mark `trigger: always_on`

`always_on` means "loaded on every single turn regardless of relevance" — it is a cost paid
unconditionally, not a way to signal "this is important." Reserve it for what is genuinely
universal (coding standards, this rule, findings/design discipline). A rule specific to one
area (UI, deployment, a single extension) belongs in `model_decision`, routed by task type in
`ONBOARDING.md` §5 — that is what the routing table is for. Checked for comparison
2026-08-23: the sibling app repo (`Sagittarius_Elite_Warrior`) marks 8 of its 9 rule files
`always_on` (~1420 lines loaded every turn, including a native-chart rule irrelevant to a pure
backend change). That is not a model to copy here — it defeats the purpose of having a routing
table at all. If a new rule feels like it should be `always_on`, that feeling is worth
questioning before the frontmatter is set, not after five more files have copied the habit.

## Applies equally to the rule files themselves

Before saving a change to any `.agents/rules/*.md` or `.agents/context/*.md` file that names a
class, method, or path, verify it resolves — `grep`, don't assume. This session's own audit
of `architecture.md` found its `AppRunner` reference and its `IEngineContext`-as-God-Object
constructor rule both wrong on first read. A rule file that names something which no longer
exists is worse than silence — it actively misleads with the authority of a written rule
behind it.
