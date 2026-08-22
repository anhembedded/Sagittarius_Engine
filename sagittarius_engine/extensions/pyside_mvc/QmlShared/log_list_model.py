"""
@brief Backward-compatibility shim — `LogListModel`'s real implementation
moved to `runtime/log_list_model.py` during the EPIC-001C directory reorg
(2026-08-22), grouped with the rest of the QML-hosting bootstrap layer.

@details
This exact module path (`...pyside_mvc.QmlShared.log_list_model`) has 3
real, direct import sites in the reference consumer
(`Sagittarius_Elite_Warrior`) that reach past this extension's top-level
re-exports — a genuine external dependency on this location, not a
hypothetical one. Kept so those imports keep resolving without requiring a
coordinated app-side change; new code (inside or outside this repo) should
import `LogListModel` from `sagittarius_engine.extensions.pyside_mvc`
(top-level) or `...pyside_mvc.runtime.log_list_model` directly instead.
"""

import warnings

from ..runtime.log_list_model import LogListModel

warnings.warn(
    "sagittarius_engine.extensions.pyside_mvc.QmlShared.log_list_model is a "
    "deprecated compat shim (EPIC-001C reorg). Import LogListModel from "
    "sagittarius_engine.extensions.pyside_mvc (top-level) or "
    "...pyside_mvc.runtime.log_list_model instead — this shim exists only "
    "for real pre-existing consumers and may be removed once those import "
    "sites are updated.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["LogListModel"]
