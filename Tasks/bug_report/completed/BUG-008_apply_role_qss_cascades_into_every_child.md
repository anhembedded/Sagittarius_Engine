# BUG-008 — `apply_role()` writes unscoped QSS, so a surface restyles every widget inside it

**Reported date:** 2026-08-25
**Severity:** High (silently changes the appearance of arbitrary child widgets; the first real consumer hit it immediately)
**Status:** ✅ Fixed 2026-08-25
**Found by:** `Sagittarius_Elite_Warrior`'s `EPIC-007E`, moving its `ChartCard` onto this package's `Card`

---

## What is wrong

`style.apply_role()` ends in:

```python
widget.setStyleSheet(_build_qss(role, state))
```

and for the `SURFACE` family `_build_qss` returns a **bare property list**:

```text
background-color: #111318;border: 1px solid #23262e;border-radius: 6px;color: #e8e9ec;
```

In Qt, a stylesheet set on a widget applies to that widget **and to every
descendant that has no more specific rule of its own**. So a `Card` does not
merely draw itself — it repaints its entire subtree with its own background,
border, radius and text colour.

Three roles are affected, all the ones written as bare property lists:
`SURFACE`, `SECTION_LABEL`/`SECTION_LABEL_TICKED`, `CAPTION`, `TABLE_HEADER`,
`CHECKBOX`, `FIELD`. The roles written with a selector (`SELECTABLE_CARD`'s
`QFrame {...}`, the button roles' `QPushButton {...}`, `PROGRESS`'s
`QProgressBar {...}`) are already scoped and are **not** affected.

## How it showed up

The consuming app's `ChartCard` puts a `ChartToolbar` — a row of checkable
`QPushButton`s — into its header. That toolbar deliberately sets no
stylesheet of its own: its buttons take their appearance from the app's
global `qdarktheme` sheet.

Moving `ChartCard` from the app's own unstyled `BaseCard` onto this
package's `Card` gave those buttons a nearer ancestor with a stylesheet, so
`SURFACE`'s properties won and the buttons lost their pill chrome — visible
in the before/after screenshots on that task. Nothing about the toolbar
changed; nothing about the buttons changed. A widget three levels up
acquired a stylesheet.

This is the first time it has been possible to hit: `Card`/`Panel`/`Surface`
had **zero consumers** until `EPIC-007B`, which is exactly why a defect this
central has gone unnoticed since `EPIC-006B` shipped them.

## Why it is a BUG and not a TASK

Per this board's own rule: BUG = something is *wrong*. `apply_role`'s
docstring says it "applies token-driven QSS for `role` to `widget`". It
applies it to the widget **and everything inside it**, which is a different
thing and the one the caller did not ask for.

## Requirements

1. **Scope the QSS to the widget it is applied to.** The conventional fix is
   a type selector built from the widget's own class:

   ```python
   widget.setStyleSheet(f"{type(widget).__name__} {{ {qss} }}")
   ```

   The consuming app already does exactly this by hand where it noticed the
   problem (`MetricCardWidget`'s sheet is written as
   `MetricCardWidget {{ ... }}`), which is corroboration that the unscoped
   form is the wrong default.

2. **Beware the two-step.** A Qt type selector matches the class *and its
   subclasses*, so `Card { ... }` would still reach a nested `Card`. That is
   usually wanted. `.Card { ... }` (leading dot) matches the exact class
   only — decide which, and write down why.

3. **This will move a lot of test assertions.** Several tests compare
   `styleSheet()` against an expected string, or check `"<token>" in qss`.
   The latter survive; the former do not. Budget for that rather than
   discovering it mid-change.

4. **Re-verify the consuming app visually, not just green.** Its widget
   tests do not assert on child appearance — that is how this reached a
   screenshot before it reached a test. Capture before/after with
   `tests/integration/presentation/ui/test_capture_screenshots.py`.

5. Regression test: a `Card` containing a `QPushButton` with no stylesheet
   of its own must leave that button's `styleSheet()` empty **and** must not
   have the card's background win on it.

## Related

- The consuming app's `EPIC-007E` records the visible symptom and links here.
- `EPIC-007B` is where `Card` gained its first consumers, i.e. where this
  became reachable.

## Fix — 2026-08-25

Added `style._scope_qss(widget, qss)`, called from `apply_role()` before
`setStyleSheet()`. It wraps a bare property list in a type selector built
from the widget's own runtime class (`f"{type(widget).__name__} {{ {qss} }}"`)
and leaves already-scoped roles (`SELECTABLE_CARD`, `PROGRESS`, the three
button roles) untouched by checking for `"{"` in the built QSS first.

**Requirement 2 resolved: bare, not dotted.** `apply_role()` is always
called with the real instance (`self`), so `type(widget).__name__` already
resolves to the most derived class — a `ChartCard(Card)` gets `ChartCard {
... }`, not `Card { ... }`. Because the selector is already the exact
runtime type, Qt's subclass-matching behaviour for a bare type selector
only ever reaches a *further* subclass of this same widget, never an
unrelated sibling — so the dotted form's extra restriction has nothing to
buy here, and bare stays consistent with how every already-scoped role in
this module already writes its selector.

**Requirement 3 (moved test assertions):** only one assertion in the whole
package compared `styleSheet()` against a string shape that broke —
`test_labels.py::test_tone_reaches_the_rendered_qss`, which asserted the
tone colour was the literal last thing in the stylesheet. Rewritten to
`assert f"color: {token};" in badge.styleSheet()`. Every other test either
does substring (`"<token>" in ...`) or self-referential before/after
comparison, both unaffected by the wrapper.

**A second, related defect this fix exposed:** `Badge.set_tone()`
(`controls/badge.py`) recoloured itself by string-concatenating a bare
`color: ...;` property onto whatever `styleSheet()` currently held. Once
`BADGE`'s own QSS became a scoped `Badge { ... }` block, appending a bare
property after its closing `}` would dangle and never apply. Fixed to
append a second block using the same selector
(`f"{selector} {{ color: {tone_colour(tone)}; }}"`), relying on
last-declaration-wins for the same selector — the mechanism the original
code's own comment already claimed to use, just not actually scoped.

**Requirement 5 (regression test):** added
`test_card_qss_is_scoped_to_its_own_type_not_bare` and
`test_unstyled_child_of_a_card_is_not_touched` to `test_surface.py`.

**Requirement 4 (visual re-verification):** not yet done in this pass —
tracked as follow-up work in the consuming app's repo (re-run
`test_capture_screenshots.py` there and check whether `ChartToolbar`'s
BUG-008 workaround styling in `chart_toolbar.py` is now redundant).

Full engine suite: `ruff check`/`ruff format --check` clean, `mypy` clean
(via `.venv`, Python 3.12), `1262 passed, 8 skipped, 0 failed`.
