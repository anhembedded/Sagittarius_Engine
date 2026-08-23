from PySide6.QtCore import QObject, Qt, Signal, Slot
from PySide6.QtWidgets import (
    QLabel,
    QMainWindow,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class DashboardSignals(QObject):
    # Signal to update UI safely from another thread/callback if needed
    telemetry_received = Signal(dict)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Audit Dashboard")
        self.resize(800, 600)

        self.signals = DashboardSignals()
        self.signals.telemetry_received.connect(self.on_telemetry_received)

        # Central widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # UI Elements
        self.status_label = QLabel("Status: Waiting for data...")
        layout.addWidget(self.status_label)

        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        layout.addWidget(self.log_area)

        self.clear_btn = QPushButton("&Clear Logs")
        self.clear_btn.setToolTip("Clear all telemetry logs from the display (Alt+C)")
        self.clear_btn.setAccessibleName("Clear Logs")
        self.clear_btn.setAccessibleDescription(
            "Clears the telemetry log text area. Shortcut: Alt+C."
        )
        self.clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_btn.clicked.connect(self.log_area.clear)
        layout.addWidget(self.clear_btn)

    @Slot(dict)
    def on_telemetry_received(self, data: dict):
        """Handle telemetry data and update UI."""
        self.status_label.setText("Status: Data received")
        self.log_area.append(str(data))
