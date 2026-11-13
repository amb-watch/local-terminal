from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QTableWidget, QTableWidgetItem, QTabWidget, QHeaderView,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont
import styles
from data_manager import MARKET_SYMBOLS


def _fmt_price(val, sym=""):
    if val is None:
        return "---"
    if "=" in sym or sym.endswith("-USD") or sym in ("BTC-USD", "ETH-USD"):
        return f"{val:,.4f}"
    if val > 10000:
        return f"{val:,.1f}"
    if val > 100:
        return f"{val:,.2f}"
    return f"{val:.4f}"


def _color_for(pct):
    if pct is None:
        return styles.COLOR_NEUTRAL
    if pct > 0:
        return styles.COLOR_POSITIVE
    if pct < 0:
        return styles.COLOR_NEGATIVE
    return styles.COLOR_NEUTRAL


class OverviewTable(QTableWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setColumnCount(4)
        self.setHorizontalHeaderLabels(["NAME", "PRICE", "CHG", "CHG %"])
        self.verticalHeader().setVisible(False)
        self.setShowGrid(True)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.setAlternatingRowColors(False)
        self.verticalHeader().setDefaultSectionSize(22)
        self.horizontalHeader().setFixedHeight(24)

    def populate(self, symbols, prices):
        self.setRowCount(len(symbols))
        for row, (name, sym) in enumerate(symbols):
            data = prices.get(sym)

            name_item = QTableWidgetItem(name)
            name_item.setForeground(QColor(styles.COLOR_NEUTRAL))
            name_item.setFont(QFont("Consolas", 10))
            self.setItem(row, 0, name_item)

            if data:
                price_str = _fmt_price(data["price"], sym)
                pct = data.get("pct")
                chg = data.get("change")
                color = _color_for(pct)

                price_item = QTableWidgetItem(price_str)
                price_item.setForeground(QColor(styles.COLOR_HIGHLIGHT))
                price_item.setFont(QFont("Consolas", 10, QFont.Weight.Bold))
                price_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.setItem(row, 1, price_item)

                sign = "+" if chg and chg > 0 else ""
                chg_str = f"{sign}{chg:.2f}" if chg is not None else "---"
                chg_item = QTableWidgetItem(chg_str)
                chg_item.setForeground(QColor(color))
                chg_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                chg_item.setFont(QFont("Consolas", 10))
                self.setItem(row, 2, chg_item)

                pct_str = f"{sign}{pct:.2f}%" if pct is not None else "---"
                pct_item = QTableWidgetItem(pct_str)
                pct_item.setForeground(QColor(color))
                pct_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                pct_item.setFont(QFont("Consolas", 10))
                self.setItem(row, 3, pct_item)
            else:
                for col, txt in enumerate(["---", "---", "---"]):
                    item = QTableWidgetItem(txt)
                    item.setForeground(QColor(styles.COLOR_DIM))
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                    self.setItem(row, col + 1, item)


class MarketOverviewWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background-color: {styles.COLOR_BG};")
        self._tables = {}
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QLabel("  MARKET OVERVIEW")
        header.setStyleSheet(
            f"background-color: {styles.COLOR_BG_HEADER}; color: {styles.COLOR_ACCENT}; "
            f"font-size: 11px; font-weight: 600; padding: 4px 6px; "
            f"border-bottom: 1px solid {styles.COLOR_BORDER};"
        )
        layout.addWidget(header)

        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane { border: none; background: #0A0D12; }
            QTabBar::tab {
                background: #12161D; color: #8791A3;
                padding: 3px 10px; border: none; font-size: 10px; font-family: 'Segoe UI';
            }
            QTabBar::tab:selected { color: #C76B52; border-bottom: 2px solid #C76B52; background: #151A24; }
        """)

        for category, symbols in MARKET_SYMBOLS.items():
            table = OverviewTable()
            table.populate(symbols, {})
            self._tables[category] = (table, symbols)
            self.tabs.addTab(table, category.upper())

        layout.addWidget(self.tabs)

    def update_prices(self, prices):
        for category, (table, symbols) in self._tables.items():
            table.populate(symbols, prices)
