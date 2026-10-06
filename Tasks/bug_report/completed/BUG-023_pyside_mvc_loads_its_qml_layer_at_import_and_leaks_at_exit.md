# BUG-023 — Importing `pyside_mvc` loads two `Property` classes and every process exits with uncollectable objects

**Reported date:** 2026-10-06
**Severity:** Low. No behaviour is wrong, but any process that imports `pyside_mvc` ends with `gc: N uncollectable objects at shutdown` (a `ResourceWarning`), which fails a consumer's sanity run.
**Status:** ✅ Fixed (2026-10-06)
**Found by:** the reference consumer (`Sagittarius_Elite_Warrior`, filed there as its `BUG-152`): its sanity run ended with `gc: 5 uncollectable objects at shutdown` after it removed every `Property` of its own.

---

## What is wrong

PySide6 6.9–6.11 leaks one uncollectable object per `QObject` class that defines a `QtCore.Property` and is alive at interpreter exit (`class A(QObject): p = Property(int, lambda s: 1, constant=True)` reproduces it; a class without a `Property` does not).

Two engine classes define `Property`s: `kit/card_model.py` `CardModel` (5) and `runtime/base_view_model.py` `BaseQmlViewModel`. Both were loaded by **any** import under `sagittarius_engine.extensions.pyside_mvc`, because:

- `pyside_mvc/__init__.py` imported `.kit` and `.runtime` eagerly;
- `kit/__init__.py` imported `.card_model` at the top (for its `@QmlElement` side effect);
- `runtime/__init__.py` imported `.base_view_model`, `.qml_host_view`, `.overlay_host`, `.icon_image_provider`, `.qml_style` at the top, and a package `__init__` runs for every submodule import, so `runtime.region_host` (which the workbench needs) loaded them too.

Importing only `...pyside_mvc.kit.card_model` in a bare interpreter already printed 7 uncollectable objects; the workbench package printed 5.

## Fix

The QML layer loads only when used. Module-level `__getattr__` (PEP 562), so every public name stays importable from the same path:

- `pyside_mvc/__init__.py`: `BaseQmlViewModel`, `QmlHostView`, `AppQmlConfig`, `configure_app_qml`, `create_quick_widget`, `OverlayHost`, `IconImageProvider`, `IIconLoader`, `ICON_PROVIDER_ID`, `ensure_qml_style` resolve lazily from `runtime`. `__all__` is unchanged.
- `runtime/__init__.py`: the same names resolve lazily from their modules.
- `kit/__init__.py`: `CardModel`, `FALLBACK_BADGE_TEXT` resolve lazily.
- `CardModel`'s QML registration used to be guaranteed by the eager import. `runtime/qml_host_view.py` — the one place QML is loaded — now imports `kit.card_model` itself, so the type is registered before any QML runs.

## Regression tests

`tests/extensions/pyside_mvc/test_qml_layer_loads_lazily.py` (each in a subprocess):
- `test_importing_the_package_and_workbench_does_not_load_the_qml_layer`: neither `kit.card_model` nor `runtime.base_view_model` is in `sys.modules`. **Before** red, **after** green.
- `test_the_interpreter_exits_without_an_uncollectable_line_after_importing_the_workbench`: **Before** red (`gc: 7 uncollectable objects at shutdown`), **after** green.
- `test_the_lazy_names_stay_importable_from_every_level`: green before and after; it pins that no caller breaks (`from … import`, `import *`, every `__all__` name resolves).

## Consequence for consumers

A class that subclasses `BaseQmlViewModel` still defines `Property`s and still leaks at exit once it is imported; only a process that does not use it is clean. Moving such a class off `Property` (plain `Signal`/`Slot` plus `setContextProperty` values) is the consumer's fix for its own classes.
