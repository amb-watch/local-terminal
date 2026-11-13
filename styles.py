FONT_UI = "'Segoe UI', 'Inter', 'Helvetica Neue', sans-serif"
FONT_DATA = "'Consolas', 'JetBrains Mono', 'Courier New', monospace"

# Plain single-family names for QFont(...) construction in Python code
# (QFont can't parse the quoted CSS font-stack strings above).
UI_FONT_FAMILY = "Segoe UI"
DATA_FONT_FAMILY = "Consolas"

COLOR_POSITIVE = "#2ECC71"
COLOR_NEGATIVE = "#FF4B4B"
COLOR_NEUTRAL = "#C76B52"
COLOR_HIGHLIGHT = "#FFFFFF"
COLOR_DIM = "#8791A3"
COLOR_WHITE = "#D7DCE5"
COLOR_BG = "#0A0D12"
COLOR_BG_PANEL = "#12161D"
COLOR_BG_HEADER = "#151A24"
COLOR_BG_ELEVATED = "#171C25"
COLOR_BORDER = "#242A36"
COLOR_BORDER_LIGHT = "#2E3542"
COLOR_DIVIDER = "#1A1F29"
COLOR_DIVIDER_SOFT = "#1F2530"
COLOR_ACCENT = "#C76B52"
COLOR_ACCENT_HOVER = "#F2B39A"
COLOR_BG_HOVER = "#1B212C"

TERMINAL_STYLE = f"""
QMainWindow, QWidget {{
    background-color: {COLOR_BG};
    color: {COLOR_WHITE};
    font-family: {FONT_UI};
    font-size: 12px;
}}

QLabel {{
    color: {COLOR_WHITE};
    font-family: {FONT_UI};
}}

QTableWidget {{
    background-color: {COLOR_BG};
    color: {COLOR_WHITE};
    gridline-color: {COLOR_DIVIDER};
    border: 1px solid {COLOR_BORDER};
    font-family: {FONT_DATA};
    font-size: 11px;
    selection-background-color: {COLOR_BG_ELEVATED};
    selection-color: {COLOR_ACCENT};
}}

QTableWidget::item {{
    padding: 2px 6px;
    border: none;
}}

QTableWidget::item:selected {{
    background-color: {COLOR_BG_ELEVATED};
    color: {COLOR_HIGHLIGHT};
}}

QHeaderView::section {{
    background-color: {COLOR_BG_HEADER};
    color: {COLOR_ACCENT};
    font-weight: 600;
    font-family: {FONT_UI};
    font-size: 11px;
    padding: 4px;
    border: 1px solid {COLOR_BORDER};
}}

QLineEdit {{
    background-color: {COLOR_BG_ELEVATED};
    color: {COLOR_HIGHLIGHT};
    border: 1px solid {COLOR_BORDER_LIGHT};
    font-family: {FONT_DATA};
    font-size: 13px;
    padding: 4px 8px;
    selection-background-color: {COLOR_ACCENT};
    selection-color: {COLOR_BG};
}}

QScrollBar:vertical {{
    background-color: {COLOR_BG_ELEVATED};
    width: 8px;
    border: none;
}}

QScrollBar::handle:vertical {{
    background-color: {COLOR_BORDER_LIGHT};
    min-height: 20px;
    border-radius: 4px;
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}

QScrollBar:horizontal {{
    background-color: {COLOR_BG_ELEVATED};
    height: 8px;
    border: none;
}}

QScrollBar::handle:horizontal {{
    background-color: {COLOR_BORDER_LIGHT};
    min-width: 20px;
    border-radius: 4px;
}}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0px;
}}

QSplitter::handle {{
    background-color: {COLOR_BORDER};
    width: 2px;
    height: 2px;
}}

QMenu {{
    background-color: {COLOR_BG_ELEVATED};
    color: {COLOR_WHITE};
    border: 1px solid {COLOR_BORDER_LIGHT};
    font-family: {FONT_UI};
}}

QMenu::item:selected {{
    background-color: {COLOR_BG_HEADER};
    color: {COLOR_ACCENT};
}}

QMenuBar {{
    background-color: {COLOR_BG_ELEVATED};
    color: {COLOR_WHITE};
}}

QTabWidget::pane {{
    border: 1px solid {COLOR_BORDER};
    background-color: {COLOR_BG};
}}

QTabBar::tab {{
    background-color: {COLOR_BG_ELEVATED};
    color: {COLOR_DIM};
    padding: 4px 12px;
    border: 1px solid {COLOR_BORDER};
    font-family: {FONT_UI};
    font-size: 11px;
}}

QTabBar::tab:selected {{
    background-color: {COLOR_BG_HEADER};
    color: {COLOR_ACCENT};
    border-bottom: 2px solid {COLOR_ACCENT};
}}

QTextEdit, QPlainTextEdit {{
    background-color: {COLOR_BG};
    color: {COLOR_WHITE};
    border: 1px solid {COLOR_BORDER};
    font-family: {FONT_DATA};
    font-size: 11px;
}}

QComboBox {{
    background-color: {COLOR_BG_ELEVATED};
    color: {COLOR_WHITE};
    border: 1px solid {COLOR_BORDER_LIGHT};
    padding: 2px 6px;
    font-family: {FONT_UI};
}}

QComboBox::drop-down {{
    border: none;
}}

QComboBox QAbstractItemView {{
    background-color: {COLOR_BG_ELEVATED};
    color: {COLOR_WHITE};
    selection-background-color: {COLOR_BG_HEADER};
}}

QPushButton {{
    background-color: {COLOR_BG_ELEVATED};
    color: {COLOR_WHITE};
    border: 1px solid {COLOR_BORDER_LIGHT};
    padding: 3px 10px;
    font-family: {FONT_UI};
    font-size: 11px;
}}

QPushButton:hover {{
    background-color: {COLOR_BG_HEADER};
    border: 1px solid {COLOR_ACCENT};
    color: {COLOR_ACCENT};
}}

QPushButton:pressed {{
    background-color: {COLOR_BORDER};
}}

QToolTip {{
    background-color: {COLOR_BG_ELEVATED};
    color: {COLOR_WHITE};
    border: 1px solid {COLOR_BORDER_LIGHT};
    font-family: {FONT_UI};
}}
"""
