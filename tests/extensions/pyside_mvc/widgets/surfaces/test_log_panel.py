"""Tests for `widgets.surfaces.log_panel.LogPanel`."""

from __future__ import annotations

from PySide6.QtCore import QAbstractListModel, QModelIndex, Signal

from sagittarius_engine.extensions.pyside_mvc.widgets import Card, LogPanel


class _FakeLogModel(QAbstractListModel):
    """Stands in for `runtime.log_list_model.LogListModel` — the same three
    things `LogPanel` asks of a model, and counters so a test can see how
    often each was called."""

    countChanged = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.entries: list[str] = []
        self.clear_calls = 0
        self.copy_calls = 0

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self.entries)

    def data(self, index, role=0):  # pragma: no cover — view-driven
        return self.entries[index.row()]

    def append(self, message: str) -> None:
        self.beginInsertRows(QModelIndex(), len(self.entries), len(self.entries))
        self.entries.append(message)
        self.endInsertRows()
        self.countChanged.emit()

    def clear(self) -> None:
        self.clear_calls += 1

    def copyAllToClipboard(self) -> None:
        self.copy_calls += 1


def test_is_a_card(qtbot):
    panel = LogPanel("SYSTEM MONITOR")
    qtbot.addWidget(panel)

    assert isinstance(panel, Card)
    assert panel.title == "SYSTEM MONITOR"


def test_badge_reads_zero_before_a_model_is_bound(qtbot):
    panel = LogPanel("LOG")
    qtbot.addWidget(panel)

    assert panel.count_text == "0"


def test_badge_tracks_the_model(qtbot):
    panel = LogPanel("LOG")
    qtbot.addWidget(panel)
    model = _FakeLogModel()
    panel.set_log_model(model)

    model.append("first")
    model.append("second")

    assert panel.count_text == "2"


def test_copy_and_clear_call_through_to_the_model(qtbot):
    panel = LogPanel("LOG")
    qtbot.addWidget(panel)
    model = _FakeLogModel()
    panel.set_log_model(model)

    panel.copy_button.click()
    panel.clear_button.click()

    assert model.copy_calls == 1
    assert model.clear_calls == 1


def test_copy_and_clear_are_harmless_without_a_model(qtbot):
    panel = LogPanel("LOG")
    qtbot.addWidget(panel)

    panel.copy_button.click()
    panel.clear_button.click()

    assert panel.count_text == "0"


def test_rebinding_disconnects_the_previous_model(qtbot):
    """The consumer's version connects `countChanged` on every call and
    never disconnects, so a rebound panel counts the same line twice. Bound
    here because a base class gets rebound by people who did not write it."""
    panel = LogPanel("LOG")
    qtbot.addWidget(panel)
    first = _FakeLogModel()
    second = _FakeLogModel()
    panel.set_log_model(first)
    panel.set_log_model(second)

    first.append("into the old model")

    # Still reporting the new model's count, not the stale one's.
    assert panel.count_text == "0"

    second.append("into the new model")
    assert panel.count_text == "1"


def test_disabling_stops_the_badge_tracking_a_live_model(qtbot):
    """Qt's cascade greys the child widgets but cannot stop a signal, and
    the consumer's backtest panel keeps a hidden log appending behind it."""
    panel = LogPanel("LOG")
    qtbot.addWidget(panel)
    model = _FakeLogModel()
    panel.set_log_model(model)
    model.append("one")

    panel.setEnabled(False)
    model.append("two")

    assert panel.count_text == "1"

    panel.setEnabled(True)
    assert panel.count_text == "2"


def test_action_labels_come_from_the_caller(qtbot):
    panel = LogPanel("NHẬT KÝ", copy_text="Sao chép", clear_text="Xoá")
    qtbot.addWidget(panel)

    assert panel.copy_button.text() == "Sao chép"
    assert panel.clear_button.text() == "Xoá"
