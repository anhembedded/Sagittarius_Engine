"""The QtWidgets workbench (`EPIC-008`): commands as actions, remembered
layouts, and display widgets configured by the kind of value they show.
Re-exported from `sagittarius_engine.extensions.pyside_mvc`, the only
supported import surface (`ui-architecture.md` §8.1)."""

from .action_confirmation import (
    IActionConfirmer,
    MessageBoxConfirmer,
    build_confirmation_box,
)
from .action_descriptor import (
    ActionConfirmation,
    ActionDeclarationError,
    ActionDescriptor,
)
from .action_registry import ActionRegistry
from .action_text import ELLIPSIS, access_keys, plain_text, text_problems
from .column_kind import ColumnKind
from .column_spec import ColumnSpec, Selection, spec_problems
from .configure_item_view import KindDelegate, SpecProxyModel, configure_item_view
from .empty_state import EmptyStateStack
from .i_value_formatter import (
    DisplayValue,
    FormatContext,
    IValueFormatter,
    PlainValueFormatter,
)
from .item_view_guard import UnconfiguredItemView, find_unconfigured_item_views
from .item_view_state_store import ITEM_VIEW_SCOPE_KEY, ItemViewStateStore
from .perspective_store import PERSPECTIVE_SCOPE_KEY, PerspectiveStore, perspective_key
from .readout_form import ReadoutForm
from .shortcut_policy import shortcut_problem

__all__ = [
    "ELLIPSIS",
    "ITEM_VIEW_SCOPE_KEY",
    "PERSPECTIVE_SCOPE_KEY",
    "ActionConfirmation",
    "ActionDeclarationError",
    "ActionDescriptor",
    "ActionRegistry",
    "ColumnKind",
    "ColumnSpec",
    "DisplayValue",
    "EmptyStateStack",
    "FormatContext",
    "IActionConfirmer",
    "IValueFormatter",
    "ItemViewStateStore",
    "KindDelegate",
    "MessageBoxConfirmer",
    "PerspectiveStore",
    "PlainValueFormatter",
    "ReadoutForm",
    "Selection",
    "SpecProxyModel",
    "UnconfiguredItemView",
    "access_keys",
    "build_confirmation_box",
    "configure_item_view",
    "find_unconfigured_item_views",
    "perspective_key",
    "plain_text",
    "shortcut_problem",
    "spec_problems",
    "text_problems",
]
