# BUG-001 — `IEngineContext` docstring names a class that does not exist (`AppRunner`)

**Reported date:** 2026-08-23
**Severity:** Low (documentation-level; no runtime impact)
**Status:** 🔴 Open

---

## 1. Symptom

`sagittarius_engine/interfaces/i_engine_context.py:30`, inside the docstring that defines where
`IEngineContext` may legitimately be used:

```python
    ✅ VALID usage of IEngineContext:
    - Inside IExtension.register(), boot(), shutdown() methods.
    - Inside IHostedService.start() and stop() methods.
    - Inside the Kernel's Bootstrap and AppRunner orchestrators.
```

**There is no `AppRunner` class anywhere in this repository.** The real orchestrator is
`ApplicationRunner`, defined in `sagittarius_engine/kernel/app_runner.py:13`.

Verified:

```
$ grep -rn "class AppRunner" sagittarius_engine/
(no results)

$ grep -n "^class" sagittarius_engine/kernel/app_runner.py
13:class ApplicationRunner:
```

## 2. Why this matters more than a typo

The two are **not** the same class with a shorter name. `.agents/rules/architecture.md:48-51`
already spells out the difference:

> There is no `AppRunner` class. `kernel/app_runner.py` defines **`ApplicationRunner`**, and it
> takes `App` + `IInputPort` + `IOutputPort` — it never receives a context at all. Do not add
> one; the ports *are* its boundary.

So the docstring does not merely misname a class — it states that a context-free orchestrator
receives `IEngineContext`, which is the exact opposite of the architectural rule the same
docstring exists to communicate. An AI session or developer reading this interface's own
docstring is told to do the thing `architecture.md` forbids.

## 3. Why it's still open — the part worth noting

This is **already recorded as a known finding** in `.agents/rules/doc-code-sync.md:63`:

| `interfaces/i_engine_context.py:30` docstring names `AppRunner` | No such class exists; real orchestrator is `ApplicationRunner`, different constructor entirely | The class was renamed/replaced without a grep for its old name in docstrings |

It was catalogued as an example *in the rule file whose entire purpose is preventing docs from
drifting from code* — and then never actually fixed. Found still present on 2026-08-23 during
the engine audit, when `architecture.md`'s (correct) correction was cross-checked against the
source it describes.

The existing staleness guard (`tests/test_agents_docs_resolve.py`) does not catch it: that test
scans `.agents/context/**/*.md`, not Python docstrings.

## 4. Fix

1. `i_engine_context.py:30` → `ApplicationRunner`. Consider dropping the mention entirely
   instead: `ApplicationRunner` does **not** receive a context (`architecture.md` is explicit),
   so listing it under "VALID usage of IEngineContext" is wrong regardless of the spelling.
   Confirm against `kernel/app_runner.py`'s actual constructor before choosing.
2. `grep -rn "AppRunner" sagittarius_engine/` and confirm no other source docstring carries it.
3. Update `doc-code-sync.md:63`'s row to mark the finding closed, so the rule file stops citing
   an open example as if it were historical.
4. **Consider extending the guard**: `tests/test_agents_docs_resolve.py` currently checks
   backtick-quoted names in `.agents/context/`. The same class of rot lives in Python
   docstrings, uncovered. Whether that's worth automating is a judgement call — record the
   decision either way rather than leaving it implicit.

## 5. Category

Documentation / Interfaces
