from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QComboBox, QPushButton, QSplitter,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor, QFont
import styles


class _OptionsWorker(QThread):
    done = pyqtSignal(object, object, list)

    def __init__(self, symbol, expiry=None):
        super().__init__()
        self.symbol = symbol
        self.expiry = expiry

    def run(self):
        try:
            import yfinance as yf
            t = yf.Ticker(self.symbol)
            dates = list(t.options)
            if not dates:
                self.done.emit(None, None, [])
                return
            exp = self.expiry or dates[0]
            chain = t.option_chain(exp)
            self.done.emit(chain.calls, chain.puts, dates)
        except Exception:
            self.done.emit(None, None, [])


class OptionsTable(QTableWidget):
    COLS_CALLS = ["Strike", "Bid", "Ask", "Last", "Volume", "OI", "IV", "Delta", "Gamma"]
    COLS_PUTS  = ["Strike", "Bid", "Ask", "Last", "Volume", "OI", "IV", "Delta", "Gamma"]

    def __init__(self, is_calls=True, parent=None):
        super().__init__(parent)
        cols = self.COLS_CALLS if is_calls else self.COLS_PUTS
        self.setColumnCount(len(cols))
        self.setHorizontalHeaderLabels(cols)
        self.verticalHeader().setVisible(False)
        self.setShowGrid(True)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        hdr = self.horizontalHeader()
        for i in range(len(cols)):
            hdr.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)
        self.verticalHeader().setDefaultSectionSize(20)
        self.horizontalHeader().setFixedHeight(22)

    def populate(self, df, current_price=None):
        if df is None or df.empty:
            self.setRowCount(0)
            return
        self.setRowCount(len(df))
        cols_map = {
            "Strike": "strike", "Bid": "bid", "Ask": "ask", "Last": "lastPrice",
            "Volume": "volume", "OI": "openInterest",
            "IV": "impliedVolatility", "Delta": "delta", "Gamma": "gamma",
        }
        for row in range(len(df)):
            strike_val = float(df.iloc[row].get("strike", 0))
            for col, col_name in enumerate(self.COLS_CALLS):
                key = cols_map.get(col_name, col_name.lower())
                try:
                    raw = df.iloc[row].get(key, None)
                    if raw is None or (hasattr(raw, "__float__") and float(raw) != float(raw)):
                        txt = "---"
                    elif col_name == "IV":
                        txt = f"{float(raw)*100:.1f}%"
                    elif col_name in ("Delta", "Gamma"):
                        txt = f"{float(raw):.4f}" if raw else "---"
                    elif col_name in ("Volume", "OI"):
                        txt = f"{int(raw):,}" if raw else "0"
                    else:
                        txt = f"{float(raw):,.2f}" if raw else "---"
                except Exception:
                    txt = "---"

                item = QTableWidgetItem(txt)
                item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                item.setFont(QFont("Consolas", 10))

                if col_name == "Strike":
                    if current_price and abs(strike_val - current_price) < current_price * 0.01:
                        item.setBackground(QColor("#1B212C"))
                        item.setForeground(QColor(styles.COLOR_HIGHLIGHT))
                    else:
                        item.setForeground(QColor(styles.COLOR_NEUTRAL))
                elif col_name in ("Bid", "Ask", "Last"):
                    item.setForeground(QColor(styles.COLOR_HIGHLIGHT))
                elif col_name == "IV":
                    item.setForeground(QColor("#FF00FF"))
                else:
                    item.setForeground(QColor(styles.COLOR_WHITE))

                self.setItem(row, col, item)


class OptionsChainWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_symbol = ""
        self._worker = None
        self._current_price = None
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header_w = QWidget()
        header_w.setStyleSheet(f"background: #151A24; border-bottom: 1px solid {styles.COLOR_BORDER};")
        hl = QHBoxLayout(header_w)
        hl.setContentsMargins(8, 3, 8, 3)
        hl.setSpacing(8)

        lbl = QLabel("OMON  ·  OPTIONS CHAIN")
        lbl.setStyleSheet(f"color: {styles.COLOR_HIGHLIGHT}; font-size: 12px; font-weight: bold; border: none; ")
        hl.addWidget(lbl)

        self.sym_lbl = QLabel("No symbol - use: OMON AAPL")
        self.sym_lbl.setStyleSheet(f"color: {styles.COLOR_DIM}; font-size: 11px; border: none;")
        hl.addWidget(self.sym_lbl)

        hl.addStretch()

        exp_lbl = QLabel("Expiry:")
        exp_lbl.setStyleSheet(f"color: {styles.COLOR_DIM}; font-size: 10px; border: none;")
        hl.addWidget(exp_lbl)

        self.expiry_combo = QComboBox()
        self.expiry_combo.setStyleSheet("""
            QComboBox { background: #171C25; color: #FFFFFF; border: 1px solid #2E3542; padding: 1px 4px; font-size: 10px; font-family: Consolas; }
            QComboBox QAbstractItemView { background: #151A24; color: #C76B52; }
        """)
        self.expiry_combo.setFixedWidth(110)
        self.expiry_combo.currentTextChanged.connect(self._on_expiry_changed)
        hl.addWidget(self.expiry_combo)

        self.price_lbl = QLabel("")
        self.price_lbl.setStyleSheet(f"color: {styles.COLOR_HIGHLIGHT}; font-size: 11px; font-weight: bold; border: none;")
        hl.addWidget(self.price_lbl)

        layout.addWidget(header_w)

        col_header = QWidget()
        col_header.setStyleSheet("background: #12161D; border-bottom: 1px solid #1F2530;")
        ch = QHBoxLayout(col_header)
        ch.setContentsMargins(0, 2, 0, 2)

        calls_hdr = QLabel("  ◆ CALLS")
        calls_hdr.setStyleSheet(f"color: {styles.COLOR_POSITIVE}; font-size: 11px; font-weight: bold; border: none;")
        ch.addWidget(calls_hdr, 1, Qt.AlignmentFlag.AlignCenter)

        puts_hdr = QLabel("PUTS ◆  ")
        puts_hdr.setStyleSheet(f"color: {styles.COLOR_NEGATIVE}; font-size: 11px; font-weight: bold; border: none;")
        ch.addWidget(puts_hdr, 1, Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(col_header)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setStyleSheet("QSplitter::handle { background: #242A36; width: 2px; }")

        self.calls_table = OptionsTable(is_calls=True)
        self.puts_table = OptionsTable(is_calls=False)

        splitter.addWidget(self.calls_table)
        splitter.addWidget(self.puts_table)
        layout.addWidget(splitter)

    def load_symbol(self, symbol, price=None):
        symbol = symbol.upper().strip()
        if not symbol:
            return
        self.current_symbol = symbol
        self._current_price = price
        self.sym_lbl.setText(f"Loading {symbol} options...")
        if price:
            self.price_lbl.setText(f"Spot: {price:,.2f}")
        self._fetch(symbol)

    def _fetch(self, symbol, expiry=None):
        if self._worker and self._worker.isRunning():
            self._worker.quit()
        self._worker = _OptionsWorker(symbol, expiry)
        self._worker.done.connect(self._on_data)
        self._worker.start()

    def _on_expiry_changed(self, expiry):
        if self.current_symbol and expiry:
            self._fetch(self.current_symbol, expiry)

    def _on_data(self, calls, puts, dates):
        if not dates:
            self.sym_lbl.setText(f"{self.current_symbol}  ·  No options data")
            return

        self.expiry_combo.blockSignals(True)
        self.expiry_combo.clear()
        self.expiry_combo.addItems(dates)
        self.expiry_combo.blockSignals(False)

        self.sym_lbl.setText(f"{self.current_symbol}  ·  {len(dates)} expiry dates")
        self.calls_table.populate(calls, self._current_price)
        self.puts_table.populate(puts, self._current_price)
