import os
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QLabel, QPushButton, QMenu, QDialog,
    QVBoxLayout, QFormLayout, QSpinBox, QCheckBox, QDialogButtonBox,
    QLineEdit, QComboBox,
)
from PyQt6.QtCore import Qt, QPoint, pyqtSignal
from PyQt6.QtGui import QFont, QCursor, QPixmap
import styles

LOGO_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "amb-logo.png")


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("SETTINGS")
        self.setModal(True)
        self.setMinimumWidth(400)
        self.setStyleSheet(styles.TERMINAL_STYLE)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        title = QLabel("TERMINAL SETTINGS")
        title.setStyleSheet(f"color: {styles.COLOR_HIGHLIGHT}; font-size: 14px; font-weight: bold;")
        layout.addWidget(title)

        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.refresh_spin = QSpinBox()
        self.refresh_spin.setRange(10, 300)
        self.refresh_spin.setValue(30)
        self.refresh_spin.setSuffix(" s")
        self.refresh_spin.setStyleSheet("color: #FFFFFF; background: #171C25; border: 1px solid #2E3542;")
        form.addRow("Refresh interval:", self.refresh_spin)

        self.font_combo = QComboBox()
        self.font_combo.addItems(["12", "13", "14", "11", "10"])
        form.addRow("Font size:", self.font_combo)

        self.show_portfolio_chk = QCheckBox("Show portfolio P&L")
        self.show_portfolio_chk.setChecked(True)
        self.show_portfolio_chk.setStyleSheet("color: #C76B52;")
        form.addRow("", self.show_portfolio_chk)

        self.news_auto_chk = QCheckBox("Auto-scroll news")
        self.news_auto_chk.setChecked(True)
        self.news_auto_chk.setStyleSheet("color: #C76B52;")
        form.addRow("", self.news_auto_chk)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        buttons.setStyleSheet("""
            QPushButton {
                background: #171C25; color: #C76B52;
                border: 1px solid #2E3542; padding: 4px 16px;
            }
            QPushButton:hover { background: #1B212C; border-color: #C76B52; }
        """)
        layout.addWidget(buttons)


class TitleBar(QWidget):
    close_requested = pyqtSignal()
    settings_changed = pyqtSignal(dict)
    analysis_toggled = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(36)
        self._build_ui()

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 8, 0)
        layout.setSpacing(0)

        self.setStyleSheet(f"""
            QWidget {{
                background-color: #151A24;
                border-bottom: 2px solid {styles.COLOR_ACCENT};
            }}
        """)

        if os.path.exists(LOGO_PATH):
            logo_pixmap = QPixmap(LOGO_PATH)
            if not logo_pixmap.isNull():
                scaled = logo_pixmap.scaledToHeight(24, Qt.TransformationMode.SmoothTransformation)
                logo_icon = QLabel()
                logo_icon.setPixmap(scaled)
                logo_icon.setStyleSheet("border: none;")
                layout.addWidget(logo_icon)
                layout.addSpacing(8)

        logo_label = QLabel("TERMINAL")
        logo_label.setStyleSheet(
            f"color: {styles.COLOR_HIGHLIGHT}; font-size: 14px; font-weight: 600; border: none;"
        )
        logo_label.setFont(QFont(styles.UI_FONT_FAMILY, 12, QFont.Weight.DemiBold))
        layout.addWidget(logo_label)

        layout.addStretch()

        self.time_label = QLabel()
        self.time_label.setStyleSheet(f"color: {styles.COLOR_DIM}; font-size: 11px; border: none; margin-right: 12px;")
        layout.addWidget(self.time_label)

        self.market_status = QLabel("● MARKET")
        self.market_status.setStyleSheet("color: #2ECC71; font-size: 11px; border: none; margin-right: 16px;")
        layout.addWidget(self.market_status)

        self.analysis_btn = QPushButton("▤ ANALYSIS")
        self.analysis_btn.setStyleSheet("""
            QPushButton {
                background: #151A24; color: #C76B52; border: 1px solid #2E3542;
                padding: 4px 12px; font-size: 11px; font-family: 'Segoe UI'; margin-right: 8px;
            }
            QPushButton:hover { background: #1B212C; border-color: #C76B52; color: #F2B39A; }
        """)
        self.analysis_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.analysis_btn.clicked.connect(self.analysis_toggled)
        layout.addWidget(self.analysis_btn)

        settings_btn = QPushButton("⚙ SETTINGS ▼")
        settings_btn.setStyleSheet("""
            QPushButton {
                background: #151A24; color: #C76B52; border: 1px solid #2E3542;
                padding: 4px 12px; font-size: 11px; font-family: 'Segoe UI';
            }
            QPushButton:hover { background: #1B212C; border-color: #C76B52; color: #F2B39A; }
        """)
        settings_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        settings_btn.clicked.connect(self._show_settings_menu)
        layout.addWidget(settings_btn)

    def _show_settings_menu(self):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #151A24; color: #C76B52;
                border: 1px solid #C76B52; font-family: 'Segoe UI'; font-size: 12px;
            }
            QMenu::item { padding: 6px 20px; }
            QMenu::item:selected { background-color: #1B212C; color: #F2B39A; }
            QMenu::separator { height: 1px; background: #242A36; margin: 2px 0; }
        """)

        menu.addAction("⚙  Preferences", self._open_settings)
        menu.addSeparator()
        menu.addAction("↺  Refresh Data", lambda: self.settings_changed.emit({"action": "refresh"}))
        menu.addAction("⊞  Reset Layout", lambda: self.settings_changed.emit({"action": "reset_layout"}))
        menu.addSeparator()
        menu.addAction("?  About", lambda: self.settings_changed.emit({"action": "about"}))
        menu.addSeparator()
        menu.addAction("✕  Close Terminal", self.close_requested)

        btn = self.sender()
        pos = btn.mapToGlobal(QPoint(0, btn.height()))
        menu.exec(pos)

    def _open_settings(self):
        dlg = SettingsDialog(self)
        if dlg.exec():
            self.settings_changed.emit({
                "action": "settings",
                "refresh_interval": dlg.refresh_spin.value(),
                "font_size": int(dlg.font_combo.currentText()),
            })

    def set_analysis_mode(self, active):
        self.analysis_btn.setText("← TERMINAL" if active else "▤ ANALYSIS")

    def update_time(self, time_str):
        self.time_label.setText(time_str)

    def set_market_status(self, is_open):
        if is_open:
            self.market_status.setText("● MARKET OPEN")
            self.market_status.setStyleSheet("color: #2ECC71; font-size: 11px; border: none; margin-right: 16px;")
        else:
            self.market_status.setText("○ MARKET CLOSED")
            self.market_status.setStyleSheet("color: #8791A3; font-size: 11px; border: none; margin-right: 16px;")
