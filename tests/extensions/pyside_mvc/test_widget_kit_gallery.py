"""Sanity coverage for the Widget Kit (EPIC-001C): the Gallery loads clean,
AppDataTable wires columns/model end to end, and the kit's own QML source
carries zero literal colour values — dogfooding the guard EPIC-001B shipped
on the exact surface ui-architecture.md §2.2 targets."""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QMetaObject, QObject, QtMsgType, QUrl, qInstallMessageHandler
from PySide6.QtGui import QColor, QIcon, QPixmap

from sagittarius_engine.extensions.pyside_mvc.runtime import (
    configure_app_qml,
    create_quick_widget,
)
from sagittarius_engine.extensions.pyside_mvc.tokens import (
    REQUIRED_COLOUR_TOKEN_NAMES,
    find_literal_colors,
)

_PYSIDE_MVC_DIR = (
    Path(__file__).resolve().parents[3]
    / "sagittarius_engine"
    / "extensions"
    / "pyside_mvc"
)
#: The widget kit's real QML home — one directory per component — after the
#: EPIC-001C directory-per-component reorg (2026-08-23).
_QML_KIT_DIR = _PYSIDE_MVC_DIR / "Sagittarius" / "UI"
#: The kit's QML surface spans two directories: the widget kit proper
#: (`Sagittarius/UI/`) and the runtime's own `OverlayHost.qml` (`runtime/`,
#: paired with `overlay_host.py` since it's bootstrap plumbing, not a
#: reusable kit component). Scanning the whole extension root — not just
#: the kit directory — keeps the anti-literal-colour guard covering both
#: without hardcoding a second path here. Computed independently of
#: `_QML_KIT_DIR` (not via `.parent`) since the kit now nests two levels
#: deep (`Sagittarius/UI/`) rather than one.
_FIXTURES_DIR = Path(__file__).parent / "fixtures"
_PLACEHOLDER_PALETTE = dict.fromkeys(REQUIRED_COLOUR_TOKEN_NAMES, "#000000")


class _TestIconLoader:
    """Returns a real (if blank) pixmap, not a bare `QIcon()`.

    An empty QIcon makes IconImageProvider hand QML a null pixmap, and Qt
    logs "Failed to get image from provider" for every icon on screen —
    noise that would drown the genuine binding errors
    `test_gallery_emits_no_qml_runtime_warnings` exists to catch.
    """

    def get_icon(self, name: str, color: str, size: int) -> QIcon:
        pixmap = QPixmap(max(size, 1), max(size, 1))
        pixmap.fill(
            QColor(color) if QColor.isValidColorName(color) else QColor("black")
        )
        return QIcon(pixmap)


@pytest.fixture(scope="module", autouse=True)
def configure_qml() -> None:
    configure_app_qml(_PLACEHOLDER_PALETTE, _TestIconLoader(), {})


def _is_qml_attributable(context, message: str) -> bool:
    """Is this Qt message attributable to QML — the only thing this test is for?

    @details Qt hands the handler a `QMessageLogContext`; a QML warning carries
    its `.qml` source in `context.file`, and Qt also prefixes the text with
    `file://…/Foo.qml:87:`. Either identifies it, and the text check matters
    because `context.file` is empty for messages Qt emits outside a logging
    category.

    @par Why this narrowing is legitimate (`BUG-006` requirement 1)
    That requirement forbids fixing this by ignoring "warnings we don't like",
    and demands the narrowing be justified by what the test is *for*. It is:
    the test is named *no **QML** runtime warnings* and exists because
    `QQuickWidget.errors()` misses bindings that throw at runtime. The message
    that made it fail —

        QFontDatabase: Cannot find font directory …/PySide6/lib/fonts.
        Note that Qt no longer ships fonts.

    — is a platform warning about the machine's font deployment. It is not a
    QML binding, cannot be the defect this guards against, and Qt emits it
    **once per process**, so it landed on whichever of the two
    `no_qml_runtime_warnings` tests happened to hold the handler at that
    moment. That is decided by collection order, not by any QML under test.

    @par What this does not fix
    `BUG-006` stays open. Its Linux half is 32 `TypeError`s from
    `RosterScreen.qml` at process teardown — those *are* `.qml`-attributable,
    so they still pass this predicate. Filtering by source addresses the
    platform-warning contaminant only; the teardown one needs either a
    session-scoped handler or a null-guard fix in that QML.
    """
    source = getattr(context, "file", None) or ""
    return source.endswith(".qml") or ".qml:" in message


def test_gallery_emits_no_qml_runtime_warnings(qtbot):
    """`QQuickWidget.errors()` reports *parse* errors only — a binding that
    throws while evaluating still leaves `errors()` empty and the component
    "loaded". That gap let a real defect through: every card's compact badge
    was silently blank because its bindings hit a not-yet-constructed
    CardModel, threw `TypeError: Cannot read property 'showIcon' of null`,
    and never re-evaluated. Four tests passed the whole time; the only thing
    that caught it was reading stderr from a real window.

    This closes that gap by capturing Qt's message stream instead of
    trusting `errors()`."""
    messages: list[str] = []

    def handler(mode, context, message):
        if mode in (
            QtMsgType.QtWarningMsg,
            QtMsgType.QtCriticalMsg,
            QtMsgType.QtFatalMsg,
        ) and _is_qml_attributable(context, message):
            messages.append(message)

    previous = qInstallMessageHandler(handler)
    try:
        widget = create_quick_widget()
        qtbot.addWidget(widget)
        widget.setSource(
            QUrl.fromLocalFile(str(_QML_KIT_DIR / "Gallery" / "Gallery.qml"))
        )
        widget.show()
        for _ in range(15):
            qtbot.wait(1)
    finally:
        qInstallMessageHandler(previous)

    assert messages == [], "QML runtime warnings:\n" + "\n".join(messages)


class _Context:
    """Stands in for `QMessageLogContext`, which cannot be constructed from
    Python — only handed to a handler by Qt."""

    def __init__(self, file: str = "") -> None:
        self.file = file


def test_the_platform_font_warning_is_not_treated_as_a_qml_warning():
    """`BUG-006`, verbatim: this exact message is what turned
    `windows-latest` red, on whichever test happened to be holding the
    handler when Qt emitted it once per process."""
    font_warning = (
        "QFontDatabase: Cannot find font directory "
        "C:/x/.venv/Lib/site-packages/PySide6/lib/fonts. Note that Qt no "
        "longer ships fonts. Deploy some (from https://dejavu-fonts.github.io/ "
        "for example) or switch to fontconfig."
    )

    assert not _is_qml_attributable(_Context(), font_warning)
    assert not _is_qml_attributable(_Context(file="qfontdatabase.cpp"), font_warning)


def test_a_real_qml_binding_warning_is_still_caught():
    """The other half, and the one that matters: narrowing must not blind the
    guard to the defect it was written for — a binding that throws at runtime
    while `QQuickWidget.errors()` stays empty."""
    binding_error = (
        "file:///x/Gallery/Card.qml:42: TypeError: Cannot read property "
        "'showIcon' of null"
    )

    assert _is_qml_attributable(_Context(), binding_error)
    assert _is_qml_attributable(_Context(file="/x/Gallery/Card.qml"), binding_error)


def test_gallery_loads_with_no_qml_errors(qtbot):
    widget = create_quick_widget()
    qtbot.addWidget(widget)

    widget.setSource(QUrl.fromLocalFile(str(_QML_KIT_DIR / "Gallery" / "Gallery.qml")))

    assert widget.errors() == []
    assert widget.rootObject() is not None


def test_app_data_table_renders_every_row_from_its_model(qtbot):
    widget = create_quick_widget()
    qtbot.addWidget(widget)

    widget.setSource(
        QUrl.fromLocalFile(str(_FIXTURES_DIR / "app_data_table_probe.qml"))
    )

    assert widget.errors() == []
    root = widget.rootObject()
    assert root is not None

    rows_view = root.findChild(QObject, "appDataTableRows")
    assert rows_view is not None
    assert rows_view.property("count") == 2


def test_app_data_table_sorts_by_clicked_column_ascending_then_descending(qtbot):
    """Click-to-sort (found missing 2026-08-23, added to the base component
    rather than any one screen since every table needs it) must sort the
    RAW model values, not the formatted display text, and must toggle
    ascending/descending on a second click of the same column."""
    widget = create_quick_widget()
    qtbot.addWidget(widget)

    widget.setSource(
        QUrl.fromLocalFile(str(_FIXTURES_DIR / "app_data_table_probe.qml"))
    )
    assert widget.errors() == []
    root = widget.rootObject()
    assert root is not None

    # Fixture data is already ascending by "a" ([1,4]) -- sort descending
    # first so this test would fail if sorting were a no-op.
    root.setProperty("sortKey", "a")
    root.setProperty("sortAscending", False)

    rows_view = root.findChild(QObject, "appDataTableRows")
    sorted_model = rows_view.property("model")
    assert [row["a"] for row in sorted_model] == [4, 1]

    root.setProperty("sortAscending", True)
    sorted_model = rows_view.property("model")
    assert [row["a"] for row in sorted_model] == [1, 4]


def test_app_data_table_current_index_defaults_unselected_and_is_settable(qtbot):
    """Row selection (found missing alongside sorting, 2026-08-23) mirrors
    the ListView's own currentIndex so a consumer can read/drive it without
    reaching into the component's internals."""
    widget = create_quick_widget()
    qtbot.addWidget(widget)

    widget.setSource(
        QUrl.fromLocalFile(str(_FIXTURES_DIR / "app_data_table_probe.qml"))
    )
    assert widget.errors() == []
    root = widget.rootObject()
    assert root is not None

    assert root.property("currentIndex") == -1

    root.setProperty("currentIndex", 1)
    assert root.property("currentIndex") == 1


def test_app_data_table_current_index_survives_empty_to_populated_model(qtbot):
    """Regression (found 2026-08-23): ListView resets currentIndex to 0 on
    its own whenever `model` transitions from empty to non-empty, not just
    once at load. app_data_table_probe.qml's model is set once at
    construction and never exercises that transition, which is exactly why
    this needs its own fixture -- a real screen's ViewModel starts empty and
    populates moments after boot, the same shape as
    app_data_table_dynamic_model_probe.qml here."""
    widget = create_quick_widget()
    qtbot.addWidget(widget)

    widget.setSource(
        QUrl.fromLocalFile(
            str(_FIXTURES_DIR / "app_data_table_dynamic_model_probe.qml")
        )
    )
    assert widget.errors() == []
    root = widget.rootObject()
    assert root is not None

    table = root.findChild(QObject, "table")
    assert table is not None
    assert table.property("currentIndex") == -1

    root.setProperty("tableModel", [{"a": 1, "b": 2}, {"a": 3, "b": 4}])
    assert table.property("currentIndex") == -1


def test_app_data_table_zoom_factor_scales_row_height(qtbot):
    """Ctrl+wheel zoom (TASK-036) scales row height along with font size;
    verified here via the rendered delegate's actual height rather than the
    wheel gesture itself (no precedent for simulated wheel/mouse input in
    this suite)."""
    widget = create_quick_widget()
    qtbot.addWidget(widget)

    widget.setSource(
        QUrl.fromLocalFile(str(_FIXTURES_DIR / "app_data_table_probe.qml"))
    )
    assert widget.errors() == []
    widget.resize(600, 200)
    widget.show()
    for _ in range(5):
        qtbot.wait(1)
    root = widget.rootObject()
    assert root is not None

    rows_view = root.findChild(QObject, "appDataTableRows")
    assert rows_view is not None

    def first_delegate():
        content_item = rows_view.property("contentItem")
        items = content_item.childItems()
        return items[0] if items else None

    base_row = first_delegate()
    assert base_row is not None
    base_height = base_row.property("height")

    root.setProperty("zoomFactor", 2.0)
    for _ in range(5):
        qtbot.wait(1)
    zoomed_row = first_delegate()
    assert zoomed_row is not None
    assert zoomed_row.property("height") == pytest.approx(base_height * 2.0)


def test_app_data_table_resized_column_keeps_others_and_last_absorbs_rest(qtbot):
    """Drag-to-resize (TASK-036): resizing one column keeps every other
    column at its own explicit width; the LAST column absorbs whatever
    space remains rather than needing a horizontal scrollbar. Drives the
    same `_userResized`/`_columnWidths` state a real drag would produce
    (via DragHandler) rather than the drag gesture itself -- verified by
    the DragHandler's own wiring in code review, no precedent for
    simulated pointer-drag input in this suite."""
    widget = create_quick_widget()
    qtbot.addWidget(widget)

    widget.setSource(
        QUrl.fromLocalFile(str(_FIXTURES_DIR / "app_data_table_probe.qml"))
    )
    assert widget.errors() == []
    widget.resize(600, 200)
    widget.show()
    for _ in range(5):
        qtbot.wait(1)
    root = widget.rootObject()
    assert root is not None

    rows_view = root.findChild(QObject, "appDataTableRows")
    header_row = rows_view.parentItem().childItems()[0].childItems()[-1]
    header_cells = [c for c in header_row.childItems() if c.property("width")][:3]
    assert len(header_cells) == 3
    assert [c.property("width") for c in header_cells] == pytest.approx(
        [192.0, 192.0, 192.0]
    )

    root.setProperty("_userResized", True)
    root.setProperty("_columnWidths", [200.0, 150.0, 0.0])
    for _ in range(5):
        qtbot.wait(1)

    widths = [c.property("width") for c in header_cells]
    assert widths[0] == pytest.approx(200.0)
    assert widths[1] == pytest.approx(150.0)
    # Last column absorbs the rest of headerRow's usable width (576 = 600 - 2*12 margins).
    assert widths[2] == pytest.approx(576.0 - 200.0 - 150.0)


def test_time_range_card_clear_resets_toggle_and_both_dates(qtbot):
    """Clear (TASK-036, found missing 2026-08-23) resets the whole range in
    one click instead of requiring the toggle and both fields cleared by
    hand."""
    widget = create_quick_widget()
    qtbot.addWidget(widget)

    widget.setSource(
        QUrl.fromLocalFile(str(_FIXTURES_DIR / "time_range_card_probe.qml"))
    )
    assert widget.errors() == []
    root = widget.rootObject()
    assert root is not None

    clear_button = root.findChild(QObject, "btnClearTimeRange")
    assert clear_button is not None

    QMetaObject.invokeMethod(clear_button, "clicked")

    assert root.property("useCustomTime") is False
    assert root.property("fromDateTime") == ""
    assert root.property("toDateTime") == ""


def test_date_time_picker_today_and_clear(qtbot):
    """Today (TASK-036) navigates the calendar to the current date without
    committing (matches clicking a day cell); Clear commits an empty value
    immediately."""
    widget = create_quick_widget()
    qtbot.addWidget(widget)

    widget.setSource(
        QUrl.fromLocalFile(str(_FIXTURES_DIR / "date_time_picker_probe.qml"))
    )
    assert widget.errors() == []
    root = widget.rootObject()
    assert root is not None

    popup = root.findChild(QObject, "calendarPopup")
    assert popup is not None
    QMetaObject.invokeMethod(popup, "open")

    today_button = root.findChild(QObject, "btnDateTimePickerToday")
    assert today_button is not None
    QMetaObject.invokeMethod(today_button, "clicked")

    # "Today" navigates the calendar but does not commit -- text unchanged,
    # matching what clicking a day cell does (Apply is the one commit
    # action).
    assert root.property("text") == "2020-01-01 00:00"

    clear_button = root.findChild(QObject, "btnDateTimePickerClear")
    assert clear_button is not None
    QMetaObject.invokeMethod(clear_button, "clicked")

    assert root.property("text") == ""


def test_app_modal_opens_dynamically_sized_with_its_action_buttons(qtbot):
    widget = create_quick_widget()
    qtbot.addWidget(widget)

    widget.setSource(QUrl.fromLocalFile(str(_FIXTURES_DIR / "app_modal_probe.qml")))

    assert widget.errors() == []
    root = widget.rootObject()
    assert root is not None

    modal = root.findChild(QObject, "probeModal")
    assert modal is not None
    assert modal.property("opened") is True
    assert modal.property("title") == "Probe Modal"
    # Dynamic sizing (qml-rule.md §2.2): width must never exceed the
    # component's own declared cap, never a bare fixed number asserted here.
    assert modal.property("width") <= modal.property("maxWidth")

    assert root.findChild(QObject, "btnCancel") is not None
    assert root.findChild(QObject, "btnConfirm") is not None


def test_widget_kit_source_has_zero_literal_colours():
    """The permanent regression test: this exact check already caught 8
    real pre-existing violations in QmlShared when first run (2026-08-22) —
    two legitimate Theme-unavailable fallbacks (now marked token-exempt),
    three with no matching semantic token yet (marked token-exempt with a
    reason), and three genuine drift bugs (fixed to use the matching
    existing token). This test is what keeps the kit at zero going
    forward."""
    findings = find_literal_colors(_PYSIDE_MVC_DIR)

    assert findings == []
