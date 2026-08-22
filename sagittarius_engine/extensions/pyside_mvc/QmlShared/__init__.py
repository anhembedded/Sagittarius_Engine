"""
@brief Legacy location — the widget kit's real QML home is now
`Sagittarius/UI/` (one directory per component, module `Sagittarius.UI`;
see `EPIC-001C`'s directory-per-component reorg, 2026-08-23). This
directory carries no QML anymore.

This `__init__.py` exists for exactly one reason: `log_list_model.py`'s
compatibility shim (see that file) needs `QmlShared` to remain an
importable Python package, because the reference consumer has real code
importing `sagittarius_engine.extensions.pyside_mvc.QmlShared.log_list_model`
directly rather than through this extension's top-level re-exports. Do not
add new content here — new Python belongs in `tokens/`/`runtime/`/`kit/`/
`mvc/`/`safety/` per its actual concern, and QML belongs in
`Sagittarius/UI/`.
"""
