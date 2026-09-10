# TASK-042: `create_quick_widget()` clears every `QQuickWidget` to an opaque, token-driven background

- **Status**: ✅ Completed
- **Completed Date**: 2026-09-10
- **Category**: UI Engine / Runtime (`pyside_mvc`)
- **Priority**: P2
- **Started Date**: 2026-09-10

---

## 🎯 Summary & Objectives

`create_quick_widget()` is the framework's single `QQuickWidget` factory ("factored out so every
path configures identically instead of hand-rolling a partial copy" — its own docstring). It
pinned the style, installed `Theme`, the icon provider and the import path, and left one thing to
Qt's default: the **clear colour**, which is opaque white. No themed app wants a white rectangle
where a QML scene paints nothing, so the reference consumer (`Sagittarius_Elite_Warrior`) bypassed
the factory in ten hosts and wrote `setClearColor(Qt::transparent)` with the comment *"so the
parent SURFACE shows through"*.

That comment is only true on the **software** rendering path (`offscreen`, `QT_QUICK_BACKEND=
software`, every `QWidget.grab()`), where the scene is painted with `QPainter` over the parent's
already-painted backing store. On the **texture** path — every real desktop session —
`QWidgetPrivate::drawWidget` punches a hole in the backing store under the widget
(`qwidget.cpp`, "punch a hole in the backingstore, so the texture will be visible") and
`QBackingStoreDefaultCompositor::flush` draws the texture *without blending* over a target
cleared to `Qt::black` (transparent only when the top-level has `WA_TranslucentBackground`).
A transparent region therefore renders **black** on X11 and **see-through** on Wayland. Ten QML
bodies shipped that way behind a fully green headless suite (`Sagittarius_Elite_Warrior`
`BUG-102`, `BUG-115` — Xvfb + xcb pixel evidence lives in that repo's `BUG-115_assets/`).

The engine's own `QmlHostView`/`OverlayHost` carry the latent form of the same defect (white,
not black — no consumer had a full QML route to notice). This task makes the rule a mechanism of
the factory, so no consumer has to know it:

> **An embedded QML scene is opaque, and its background is a design token.**

## 📐 Implementation Plan / Overview

- `runtime/quick_background.py` (new, one abstraction): `DEFAULT_BACKGROUND = "bg"` and
  `resolve_opaque_background(token) -> QColor` — reads the shared theme bridge, raises `KeyError`
  for an unknown token and `ValueError` for a non-colour or non-opaque value. Refusing a
  translucent token at construction is deliberate: it is exactly the value that re-creates the
  defect, and construction is where the caller is.
- `runtime/qml_host_view.py`: `create_quick_widget(background=DEFAULT_BACKGROUND)`
  ends with `setClearColor(resolve_opaque_background(background))`. Default keeps every
  existing caller (`QmlHostView`, `OverlayHost`, `tools/state_console`, `examples/`) source-
  compatible; they change from clearing to white to clearing to the app's `bg` token. A consumer
  embedding a widget inside a card passes that surface's token (`"bgCard"`) — the consumer owns
  *which* token, the engine owns *that it is opaque*.
- Exported from `runtime/__init__.py` and the `pyside_mvc` barrel.
- Docs in the same change (`doc-code-sync.md`): `pyside_mvc/README.md` (class diagram + tree),
  `.agents/rules/ui-architecture.md` §4 (the rule, with the mechanism), `CHANGELOG.md`
  (`[Unreleased]`).

Deliberately **not** done here: a `StyleRole`-aware surface class. `StyleRole` is the
consumer's vocabulary (`Sagittarius_Elite_Warrior/src/presentation/ui/kit/style.py`); the
consumer builds its `QuickSurface(surface: StyleRole)` on top of this factory and maps role →
token on its side (`BUG-115` §4.3). The engine stays ignorant of roles, as `ui-architecture.md`
§4 requires ("the runtime must not know the consuming application").

## 🧪 Verification & Test Coverage

- `tests/extensions/pyside_mvc/test_quick_background.py` (new, 8 tests): default token is
  `"bg"` and required; a required token resolves to an opaque colour equal to the live bridge
  value; unknown token → `KeyError` naming it; translucent / non-colour token → `ValueError`;
  `create_quick_widget()` clears to the default token; to a requested token; refuses a
  translucent one. Assertions read the *live* bridge (first-caller-wins singleton) rather than a
  literal, so they hold in any collection order.
- Existing consumers re-run: `test_widget_kit_gallery.py`, `test_overlay_host.py`,
  `tools/state_console/test_overview_screen.py`.
- **Correction (2026-09-10), and the method that produced it.** This file first recorded
  `test_thread_bridge.py::test_logs_the_error_with_a_traceback_via_the_owners_logger` as a
  pre-existing failure, on the strength of a `git stash` A/B that showed it red both with and
  without this change. That conclusion was **wrong**, and the A/B was the reason: stashing swaps
  the working tree but leaves the *environment* identical, so it cannot see an environment cause.
  Re-checked against untouched `origin/main` in a separate `git worktree` — it passed there and
  failed here, which looked like a regression this task had introduced. It was neither.

  Real cause: this checkout was moved on disk mid-session, leaving 113 `__pycache__` directories
  whose compiled code still recorded the old path. The test asserts that a formatted traceback
  contains the line `raise TypeError`, and CPython cannot include a source line for a file whose
  recorded path no longer exists. Clearing the caches makes it pass; nothing in the engine was
  involved. Gate re-run on clean caches — see below.

  Kept in the record rather than quietly deleted, because the failure mode is instructive: a
  stash A/B *agreed* with the wrong answer, and only a checkout of the untouched base in a
  separate directory settled it.
- Gate: `pwsh ./scripts/ci-local.ps1` (2026-09-10, Linux, Python 3.12, PySide6 6.11.1): Ruff Lint ✅,
  Ruff Format ✅, Mypy ✅, Bandit ✅, Pip-Audit ✅, Architecture ✅, log scan ✅; Tests **1416 passed,
  11 skipped, 1 failed** — the one failure is
  `tests/test_agents_docs_resolve.py::test_staleness_check_actually_catches_the_original_bug`,
  which fails **identically with this change stashed** (A/B per the consumer's `ONBOARDING.md`
  §12.6, which already names this test as environment-dependent). Not this task's; not touched.
  Two findings the gate raised against the first draft and that shaped the final names: Bandit
  `B105` flagged `DEFAULT_BACKGROUND_TOKEN = "bg"` as a hardcoded password (its heuristic keys on
  `token` in the name), so the constant is `DEFAULT_BACKGROUND` and the parameter `background`;
  Ruff `I001` on the new import's order.
- The on-screen proof (texture path) cannot run headless; it is the consumer's Desktop-tier test
  and Xvfb pixel evidence under `BUG-115`.


## 📎 Consumer follow-through (2026-09-10, same day)

`Sagittarius_Elite_Warrior` `BOT-132` built its `QuickSurface(surface: StyleRole)` on this
factory and migrated all ten hosts plus eleven previews to it; a grep guard there now fails the
build on any `QQuickWidget()` or `setClearColor(` outside its one embedding package. Measured on a
real X11 session (Xvfb + xcb): the three sample points from that repo's `BUG-115` §1 went from
`#000000` to `#111318`, and the pixel diff between `QScreen.grabWindow` and `widget.grab()` on its
Data Management screen went from 24.12% to 0.00%. That is the on-screen evidence this task's own
tests structurally cannot produce.
