# BUG-009 — `StatCard.set_badge()`'s tone stopped rendering once `BUG-008` scoped the role QSS

**Reported date:** 2026-08-25
**Severity:** Medium (a stat card's badge silently renders in the wrong colour; no crash, no failing test)
**Status:** ✅ Fixed 2026-08-25 — root-caused, reproduced by rendering, regression test strengthened and confirmed red before / green after
**Found by:** reading `StatCard` while starting `EPIC-007F`'s Backtest screen in the consuming app — **not** by any test

---

## Symptom

`StatCard.set_badge("Rủi ro", tone=Tone.NEGATIVE)` left the badge rendering
in the role's default muted colour instead of `danger`. Grabbing the badge
and enumerating its pixels found no `#ff4d4f` anywhere in it.

Qt says so out loud, once you look for it — the test run prints:

```text
Could not parse stylesheet of object QLabel(0xa520c20)
```

## Root cause

`BUG-008` changed `apply_role()` to wrap unscoped role QSS in a type
selector. `BADGE` therefore went from a bare property list to:

```text
Badge { background-color: ...;border: ...;color: #8b8f9a;padding: 0 4px; }
```

`StatCard.set_badge()` was appending its tone override by string
concatenation onto whatever `styleSheet()` held:

```python
self._badge_label.setStyleSheet(
    f"{self._badge_label.styleSheet()}color: {tone_colour(tone)};"
)
```

which now produces a bare property **after a closing brace**:

```text
Badge { ...color: #8b8f9a;padding: 0 4px; }color: #ff4d4f;
```

Qt cannot parse that trailing fragment, discards it, and the badge keeps
the role's colour.

**This was predicted in the code and still shipped.** The method's own
comment read: *"This would silently stop working if `BADGE` ever grew a
`QLabel { ... }` selector — a test pins the tone actually reaching the
rendered QSS."* `BUG-008` is precisely that change. The identical pattern
in `Badge.set_tone()` was spotted and fixed while `BUG-008` was being
written; this second copy in `StatCard` was missed.

## Why the test did not catch it

`test_badge_tone_survives_the_role_being_reapplied` existed for exactly
this scenario and **passed throughout**. It asserted:

```python
assert qss.rstrip().endswith("<danger>;")
```

The broken output *does* end in `<danger>;` — the dangling property is
still the last thing in the string. The test checked the tail of a string
where the defect is structural, so the one assertion written to guard this
was blind to it.

That is the more useful finding than the bug: a test can name the right
risk in its docstring and still assert the wrong property.

## Fix

`set_badge()` now delegates to `Badge.set_tone()`, which already emits a
correctly scoped override (`Badge { color: ...; }`) after the `BUG-008`
fix. `StatCard._badge_label` has always been a `Badge`, so the hand-rolled
append was duplicating an API the widget already exposes.

## Regression test

Same test, rewritten to assert on **structure rather than the tail**: the
token must appear, the sheet must end in `}`, and nothing may dangle after
the last `}`. Confirmed red against the unfixed `stat_card.py` (with the
new test in place) and green after.

Verified by rendering as well as by string: `StatCard`'s badge now contains
`(255, 77, 79)` pixels for `Tone.NEGATIVE`, and `Badge.set_tone()`'s own
path contains `(34, 197, 94)` for `Tone.POSITIVE`.

## Related

- `BUG-008` — the change that exposed this, and where the sibling copy in
  `Badge.set_tone()` was fixed.
- Swept the package for the same shape afterwards: `Badge.set_tone()` is
  now the only place that appends to an existing stylesheet, and it does so
  with a selector.
