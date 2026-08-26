# BUG-012 — A `TabBar` tab sizes itself from text it does not have, so every label is clipped

**Reported date:** 2026-08-25
**Severity:** Medium (every tab in every `TabBar` renders with its label cut to about two characters)
**Status:** ✅ Fixed 2026-08-25 — root-caused by measurement, regression test confirmed red before / green after
**Found by:** `Sagittarius_Elite_Warrior`'s `EPIC-007F`, the first real consumer to put a `TabBar` on a screen

---

## Symptom

Migrating the app's trade-logs tab row onto `TabBar` rendered
`DANH SÁCH LỆNH` as `DA` and `NHẬT KÝ BACKTEST` as `NH`, each tab
collapsed to a small pill barely wider than its badge. The screenshot
diff against the previous hand-rolled bar is unmistakable.

## Root cause

`_TabButton` is a `QPushButton` that carries **no text and no icon of its
own**. Its content is a `QLabel` and a `Badge` inside a child
`QHBoxLayout`:

```python
row = QHBoxLayout(self)
self._label = QLabel(tab.label)
row.addWidget(self._label)
self._badge = Badge(tab.badge)
row.addWidget(self._badge)
```

`QPushButton` overrides `sizeHint()`/`minimumSizeHint()` to compute a
button's size from **its own** text, icon and style margins. It does not
consult a child layout, because a normal button has no children. So the
button reported a size for an empty button while its actual content was
three times wider.

Measured directly rather than inferred:

```text
button sizeHint      : QSize(59, 24)
its layout sizeHint  : QSize(195, 34)
label sizeHint       : QSize(109, 14)
```

The layout still *arranges* the children correctly — it is only the size
the button negotiates with its parent that is wrong, which is why the
content ends up clipped rather than mispositioned.

## Why nobody saw it

`TabBar` had no real consumer. The widget showcase builds one with the
labels `"First"` and `"Second"` — short enough that the wrong size hint
still left them readable, so the demo looked fine.

That is the same shape as `BUG-008` (unscoped QSS) and `StatCard`'s
missing value size: a widget shipped without a consumer, and the defect
waited for the first screen to use it.

## Fix

`_TabButton` overrides both size hints to defer to its layout:

```python
def sizeHint(self) -> QSize:
    return self.layout().sizeHint()

def minimumSizeHint(self) -> QSize:
    return self.layout().minimumSize()
```

## Regression test

`test_tab_bar.py::test_a_tab_is_wide_enough_for_its_own_label` — asserts
the button's `sizeHint()` is at least its layout's, in both dimensions.

Asserted against the layout rather than a fixed pixel count, so the check
keeps meaning something when the font, the padding or the badge text
changes. Confirmed red against the unfixed source and green after.
