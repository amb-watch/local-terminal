from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel
from PyQt6.QtCore import QTimer
from datetime import datetime
import styles


class StatusBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(22)
        self.setStyleSheet(f"background-color: #050500; border-top: 1px solid {styles.COLOR_BORDER};")
        self._build_ui()

        self._timer = QTimer()
        self._timer.timeout.connect(self._update_time)
        self._timer.start(1000)
        self._update_time()

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 8, 0)
        layout.setSpacing(16)

        self.time_label = QLabel()
        self.time_label.setStyleSheet(f"color: {styles.COLOR_ACCENT}; font-size: 10px; border: none;")
        layout.addWidget(self.time_label)

        self.session_label = QLabel("SESSION: ACTIVE")
        self.session_label.setStyleSheet(f"color: {styles.COLOR_DIM}; font-size: 10px; border: none;")
        layout.addWidget(self.session_label)

        layout.addStretch()

        self.message_label = QLabel("Ready  ·  Double-click watchlist to chart  ·  Press any key to focus CMD")
        self.message_label.setStyleSheet(f"color: {styles.COLOR_DIM}; font-size: 10px; border: none;")
        layout.addWidget(self.message_label)

        layout.addStretch()

        self.data_label = QLabel("DATA: Yahoo Finance  ·  ~15min delayed")
        self.data_label.setStyleSheet(f"color: {styles.COLOR_DIM}; font-size: 10px; border: none;")
        layout.addWidget(self.data_label)

        self.version_label = QLabel("v2.0  ·  AMB Terminal")
        self.version_label.setStyleSheet(f"color: {styles.COLOR_DIM}; font-size: 10px; border: none;")
        layout.addWidget(self.version_label)

    def _update_time(self):
        now = datetime.now()
        self.time_label.setText(
            f"LOC: {now.strftime('%H:%M:%S')}  "
            f"NY: {now.strftime('%H:%M')}  "
            f"{now.strftime('%a %d %b %Y')}"
        )

    def set_message(self, msg, color=None):
        self.message_label.setText(msg)
        c = color or styles.COLOR_DIM
        self.message_label.setStyleSheet(f"color: {c}; font-size: 10px; border: none;")

    def set_data_status(self, msg):
        self.data_label.setText(msg)
