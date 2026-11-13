from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget,
    QTableWidgetItem, QHeaderView, QLineEdit, QPushButton,
    QMenu, QInputDialog, QDialog, QFormLayout, QDoubleSpinBox,
    QSpinBox, QDialogButtonBox, QTabWidget,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QCursor, QAction
import styles


def _color_for(pct):
    if pct is None:
        return styles.COLOR_NEUTRAL
    if pct > 0:
        return styles.COLOR_POSITIVE
    if pct < 0:
        return styles.COLOR_NEGATIVE
    return styles.COLOR_NEUTRAL


class AddPositionDialog(QDialog):
    def __init__(self, symbol, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Add Position: {symbol}")
        self.setModal(True)
        self.setStyleSheet(styles.TERMINAL_STYLE)
        layout = QFormLayout(self)
        layout.setSpacing(10)

        self.qty_spin = QSpinBox()
        self.qty_spin.setRange(1, 1000000)
        self.qty_spin.setValue(100)
        self.qty_spin.setStyleSheet("color: #FFFFFF; background: #171C25; border: 1px solid #2E3542;")
        layout.addRow("Quantity:", self.qty_spin)

        self.price_spin = QDoubleSpinBox()
        self.price_spin.setRange(0.001, 1000000)
        self.price_spin.setDecimals(2)
        self.price_spin.setValue(100.0)
        self.price_spin.setStyleSheet("color: #FFFFFF; background: #171C25; border: 1px solid #2E3542;")
        layout.addRow("Avg Price:", self.price_spin)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        buttons.setStyleSheet("""
            QPushButton { background: #171C25; color: #C76B52; border: 1px solid #2E3542; padding: 4px 16px; }
            QPushButton:hover { background: #1B212C; }
        """)
        layout.addRow(buttons)


class WatchlistTable(QTableWidget):
    symbol_double_clicked = pyqtSignal(str)
    remove_requested = pyqtSignal(str)
    add_position_requested = pyqtSignal(str)

    def __init__(self, columns, parent=None):
        super().__init__(parent)
        self.setColumnCount(len(columns))
        self.setHorizontalHeaderLabels(columns)
        self.verticalHeader().setVisible(False)
        self.setShowGrid(True)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.horizontalHeader().setStretchLastSection(False)
        self.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self.setColumnWidth(0, 80)
        self.setColumnWidth(1, 90)
        for i in range(2, len(columns)):
            self.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)
        self.verticalHeader().setDefaultSectionSize(22)
        self.horizontalHeader().setFixedHeight(24)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._context_menu)
        self.doubleClicked.connect(self._on_double_click)

    def _on_double_click(self, index):
        row = index.row()
        item = self.item(row, 0)
        if item:
            self.symbol_double_clicked.emit(item.text())

    def _context_menu(self, pos):
        row = self.rowAt(pos.y())
        if row < 0:
            return
        item = self.item(row, 0)
        if not item:
            return
        sym = item.text()

        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu { background: #151A24; color: #C76B52; border: 1px solid #C76B52; font-family: 'Segoe UI'; }
            QMenu::item { padding: 5px 16px; }
            QMenu::item:selected { background: #1B212C; color: #F2B39A; }
        """)
        menu.addAction(f"Chart: {sym}", lambda: self.symbol_double_clicked.emit(sym))
        menu.addAction(f"Add Position: {sym}", lambda: self.add_position_requested.emit(sym))
        menu.addSeparator()
        menu.addAction(f"Remove: {sym}", lambda: self.remove_requested.emit(sym))
        menu.exec(self.viewport().mapToGlobal(pos))


class WatchlistWidget(QWidget):
    symbol_selected = pyqtSignal(str)

    def __init__(self, data_manager, parent=None):
        super().__init__(parent)
        self.dm = data_manager
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header_w = QWidget()
        header_w.setStyleSheet(f"background-color: #151A24; border-bottom: 1px solid {styles.COLOR_BORDER};")
        hl = QHBoxLayout(header_w)
        hl.setContentsMargins(6, 2, 6, 2)
        hl.setSpacing(6)

        lbl = QLabel("  WATCHLIST & PORTFOLIO")
        lbl.setStyleSheet(f"color: {styles.COLOR_ACCENT}; font-size: 11px; font-weight: bold; border: none;")
        hl.addWidget(lbl)
        hl.addStretch()

        self.add_input = QLineEdit()
        self.add_input.setPlaceholderText("+ Add symbol")
        self.add_input.setFixedWidth(100)
        self.add_input.setStyleSheet(
            "color: #FFFFFF; background: #0A0D12; border: 1px solid #2E3542; padding: 1px 4px; font-size: 11px;"
        )
        self.add_input.returnPressed.connect(self._add_symbol)
        hl.addWidget(self.add_input)

        layout.addWidget(header_w)

        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane { border: none; background: #0A0D12; }
            QTabBar::tab { background: #12161D; color: #8791A3; padding: 3px 10px; border: none; font-size: 10px; font-family: 'Segoe UI'; }
            QTabBar::tab:selected { color: #C76B52; border-bottom: 2px solid #C76B52; background: #151A24; }
        """)

        self.watch_table = WatchlistTable(["SYMBOL", "PRICE", "CHG", "CHG%"])
        self.watch_table.symbol_double_clicked.connect(self.symbol_selected)
        self.watch_table.remove_requested.connect(self._remove_symbol)
        self.watch_table.add_position_requested.connect(self._add_position)
        self.tabs.addTab(self.watch_table, "WATCHLIST")

        self.port_table = WatchlistTable(["SYMBOL", "PRICE", "CHG%", "QTY", "P&L", "P&L%"])
        self.port_table.symbol_double_clicked.connect(self.symbol_selected)
        self.port_table.remove_requested.connect(lambda sym: self.dm.remove_position(sym))
        self.tabs.addTab(self.port_table, "PORTFOLIO")

        layout.addWidget(self.tabs)

        self.status_bar = QLabel("")
        self.status_bar.setStyleSheet(
            f"background: #12161D; color: {styles.COLOR_DIM}; font-size: 10px; padding: 2px 8px; border-top: 1px solid #1F2530;"
        )
        layout.addWidget(self.status_bar)

    def _add_symbol(self):
        sym = self.add_input.text().upper().strip()
        if sym:
            self.dm.add_to_watchlist(sym)
            self.add_input.clear()

    def _remove_symbol(self, sym):
        self.dm.remove_from_watchlist(sym)
        self.update_prices(self.dm.prices)

    def _add_position(self, sym):
        dlg = AddPositionDialog(sym, self)
        if dlg.exec():
            self.dm.add_position(sym, dlg.qty_spin.value(), dlg.price_spin.value())
            self.update_prices(self.dm.prices)

    def update_prices(self, prices):
        syms = self.dm.watchlist
        self.watch_table.setRowCount(len(syms))

        for row, sym in enumerate(syms):
            data = prices.get(sym)
            sym_item = QTableWidgetItem(sym)
            sym_item.setForeground(QColor(styles.COLOR_NEUTRAL))
            sym_item.setFont(QFont("Consolas", 10, QFont.Weight.Bold))
            self.watch_table.setItem(row, 0, sym_item)

            if data:
                price = data["price"]
                chg = data.get("change", 0)
                pct = data.get("pct", 0)
                color = _color_for(pct)
                sign = "+" if chg >= 0 else ""

                p = QTableWidgetItem(f"{price:,.2f}")
                p.setForeground(QColor(styles.COLOR_HIGHLIGHT))
                p.setFont(QFont("Consolas", 10))
                p.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.watch_table.setItem(row, 1, p)

                c = QTableWidgetItem(f"{sign}{chg:.2f}")
                c.setForeground(QColor(color))
                c.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.watch_table.setItem(row, 2, c)

                pp = QTableWidgetItem(f"{sign}{pct:.2f}%")
                pp.setForeground(QColor(color))
                pp.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.watch_table.setItem(row, 3, pp)
            else:
                for col in range(1, 4):
                    item = QTableWidgetItem("---")
                    item.setForeground(QColor(styles.COLOR_DIM))
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                    self.watch_table.setItem(row, col, item)

        portfolio = self.dm.portfolio
        port_syms = list(portfolio.keys())
        self.port_table.setRowCount(len(port_syms))
        total_pnl = 0

        for row, sym in enumerate(port_syms):
            pos = portfolio[sym]
            data = prices.get(sym)
            qty = pos["qty"]
            avg = pos["avg_price"]

            sym_item = QTableWidgetItem(sym)
            sym_item.setForeground(QColor(styles.COLOR_NEUTRAL))
            sym_item.setFont(QFont("Consolas", 10, QFont.Weight.Bold))
            self.port_table.setItem(row, 0, sym_item)

            if data:
                price = data["price"]
                pct = data.get("pct", 0)
                pnl = (price - avg) * qty
                pnl_pct = ((price - avg) / avg * 100) if avg else 0
                total_pnl += pnl
                color = _color_for(pnl_pct)
                sign = "+" if pnl >= 0 else ""

                items = [
                    (f"{price:,.2f}", styles.COLOR_HIGHLIGHT),
                    (f"{'+' if pct>=0 else ''}{pct:.2f}%", color),
                    (f"{qty:,}", styles.COLOR_NEUTRAL),
                    (f"{sign}{pnl:,.2f}", color),
                    (f"{sign}{pnl_pct:.2f}%", color),
                ]
                for col, (txt, col_color) in enumerate(items):
                    it = QTableWidgetItem(txt)
                    it.setForeground(QColor(col_color))
                    it.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                    it.setFont(QFont("Consolas", 10))
                    self.port_table.setItem(row, col + 1, it)
            else:
                for col in range(1, 6):
                    it = QTableWidgetItem("---")
                    it.setForeground(QColor(styles.COLOR_DIM))
                    it.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                    self.port_table.setItem(row, col, it)

        if portfolio:
            color = styles.COLOR_POSITIVE if total_pnl >= 0 else styles.COLOR_NEGATIVE
            sign = "+" if total_pnl >= 0 else ""
            self.status_bar.setText(f"  Total P&L: {sign}{total_pnl:,.2f}")
            self.status_bar.setStyleSheet(
                f"background: #12161D; color: {color}; font-size: 10px; font-weight: bold; "
                f"padding: 2px 8px; border-top: 1px solid #1F2530;"
            )
        else:
            self.status_bar.setText(f"  {len(syms)} symbols tracked")
