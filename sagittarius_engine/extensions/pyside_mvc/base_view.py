"""
@brief Backward-compatibility shim — `BaseView`'s real implementation
moved to `mvc/base_view.py` during the EPIC-001C directory reorg
(2026-08-22), grouped with `BasePresenter`/`PresenterManager`.

@details
This exact module path (`...pyside_mvc.base_view`) has a real, direct
import site in the reference consumer (`Sagittarius_Elite_Warrior`,
`backtest_presenter.py`) reaching past this extension's top-level
re-exports for `DEV_MODE_CONFIG_KEY` — a genuine external dependency on
this location, not a hypothetical one. Kept so that import keeps resolving
without requiring a coordinated app-side change; new code (inside or
outside this repo) should import from `sagittarius_engine.extensions.pyside_mvc`
(top-level) or `...pyside_mvc.mvc.base_view` directly instead.
"""

import warnings

from .mvc.base_view import DEV_MODE_CONFIG_KEY, BaseView

warnings.warn(
    "sagittarius_engine.extensions.pyside_mvc.base_view is a deprecated "
    "compat shim (EPIC-001C reorg). Import from "
    "sagittarius_engine.extensions.pyside_mvc (top-level) or "
    "...pyside_mvc.mvc.base_view instead — this shim exists only for a "
    "real pre-existing consumer and may be removed once that import site "
    "is updated.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["DEV_MODE_CONFIG_KEY", "BaseView"]
