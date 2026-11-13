from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QWidget, QPushButton,
    QGridLayout,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QGuiApplication, QFont
import styles


class _ScreenCard(QPushButton):
    def __init__(self, index, screen, parent=None):
        label = f"Display {index + 1}"
        geo = screen.geometry()
        sub = f"{geo.width()} x {geo.height()}"
        if screen == QGuiApplication.primaryScreen():
            sub += "   ·   Primary"
        super().__init__(f"{label}\n{sub}", parent)
        self.screen = screen
        self.setFixedSize(200, 110)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFont(QFont(styles.UI_FONT_FAMILY, 11))
        self.setStyleSheet(f"""
            QPushButton {{
                background: {styles.COLOR_BG_ELEVATED};
                color: {styles.COLOR_WHITE};
                border: 1px solid {styles.COLOR_BORDER_LIGHT};
                border-radius: 6px;
                font-family: '{styles.UI_FONT_FAMILY}';
                font-size: 13px;
                text-align: center;
            }}
            QPushButton:hover {{
                background: {styles.COLOR_BG_HOVER};
                border: 1px solid {styles.COLOR_ACCENT};
                color: {styles.COLOR_ACCENT};
            }}
        """)


class DisplayPickerDialog(QDialog):
    """Frameless, fixed, modal display-selection prompt shown before the
    main terminal window opens. No title bar and no drag handler are
    implemented, so it cannot be minimized or moved."""

    def __init__(self):
        super().__init__()
        self.selected_screen = None
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Dialog
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setModal(True)
        self.setStyleSheet(f"background: {styles.COLOR_BG}; color: {styles.COLOR_WHITE};")
        self._build_ui()
        self._center_on_primary()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 24, 28, 24)
        outer.setSpacing(16)

        top_row = QHBoxLayout()
        title = QLabel("Choose a display")
        title.setStyleSheet(
            f"color: {styles.COLOR_HIGHLIGHT}; font-size: 17px; font-weight: 600; "
            f"font-family: '{styles.UI_FONT_FAMILY}'; border: none;"
        )
        top_row.addWidget(title)
        top_row.addStretch()

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(24, 24)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {styles.COLOR_DIM};
                border: none; font-size: 13px; font-family: '{styles.UI_FONT_FAMILY}';
            }}
            QPushButton:hover {{ color: {styles.COLOR_NEGATIVE}; }}
        """)
        close_btn.clicked.connect(self._on_exit)
        top_row.addWidget(close_btn)
        outer.addLayout(top_row)

        sub = QLabel("AMB Terminal will open fullscreen on the monitor you pick.")
        sub.setStyleSheet(
            f"color: {styles.COLOR_DIM}; font-size: 11px; "
            f"font-family: '{styles.UI_FONT_FAMILY}'; border: none;"
        )
        outer.addWidget(sub)

        grid_holder = QWidget()
        grid = QGridLayout(grid_holder)
        grid.setSpacing(14)

        screens = QGuiApplication.screens()
        cols = 3 if len(screens) > 2 else len(screens)
        for i, screen in enumerate(screens):
            card = _ScreenCard(i, screen)
            card.clicked.connect(lambda checked=False, s=screen: self._on_pick(s))
            grid.addWidget(card, i // cols, i % cols)

        outer.addWidget(grid_holder)

    def _center_on_primary(self):
        self.adjustSize()
        primary = QGuiApplication.primaryScreen()
        geo = primary.geometry()
        self.move(
            geo.x() + (geo.width() - self.width()) // 2,
            geo.y() + (geo.height() - self.height()) // 2,
        )

    def _on_pick(self, screen):
        self.selected_screen = screen
        self.accept()

    def _on_exit(self):
        self.selected_screen = None
        self.reject()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            return
        super().keyPressEvent(event)
