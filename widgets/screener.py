from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QComboBox, QPushButton, QDoubleSpinBox, QLineEdit,
    QCheckBox,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor, QFont
import styles

SP500_SAMPLE = [
    "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA", "BRK-B", "JPM", "V",
    "UNH", "LLY", "XOM", "JNJ", "MA", "AVGO", "PG", "HD", "COST", "MRK",
    "ABBV", "CVX", "PEP", "KO", "WMT", "BAC", "CSCO", "ACN", "MCD", "PFE",
    "TMO", "ABT", "NFLX", "DIS", "ADBE", "AMD", "QCOM", "INTC", "WFC", "GS",
    "CAT", "HON", "IBM", "GE", "BA", "RTX", "DE", "MMM", "AXP", "BLK",
    "SBUX", "TGT", "NKE", "LOW", "TJX", "ADP", "CMG", "BKNG", "ABNB", "UBER",
    "CRM", "NOW", "ORCL", "SAP", "SNOW", "PLTR", "COIN", "MSTR", "SQ", "PYPL",
    "NEE", "D", "SO", "DUK", "AEP", "XEL", "PLD", "AMT", "EQIX", "SPG",
    "XOM", "CVX", "COP", "EOG", "SLB", "MPC", "PSX", "VLO", "OXY", "HAL",
    "LIN", "APD", "FCX", "NEM", "NUE", "ALB", "MP", "GOLD", "AA",
]


class _ScreenerWorker(QThread):
    done = pyqtSignal(list)
    progress = pyqtSignal(int)

    def __init__(self, symbols, filters):
        super().__init__()
        self.symbols = symbols
        self.filters = filters

    def run(self):
        import yfinance as yf
        from data_manager import YFINANCE_LOCK
        try:
            with YFINANCE_LOCK:
                data = yf.download(self.symbols, period="2d", interval="1d",
                                   progress=False, threads=True, auto_adjust=True)
            results = []
            if data.empty:
                self.done.emit([])
                return

            if len(self.symbols) == 1:
                sym = self.symbols[0]
                col = data["Close"].dropna()
                if len(col) >= 2:
                    prev, curr = float(col.iloc[-2]), float(col.iloc[-1])
                    chg = curr - prev
                    pct = chg / prev * 100 if prev else 0
                    vol = float(data["Volume"].iloc[-1]) if "Volume" in data.columns else 0
                    results.append({"symbol": sym, "price": curr, "change": chg, "pct": pct, "volume": vol})
            else:
                close = data["Close"] if "Close" in data.columns else data.xs("Close", axis=1, level=0)
                volume = data["Volume"] if "Volume" in data.columns else None

                for sym in self.symbols:
                    try:
                        col = close[sym].dropna()
                        if len(col) >= 2:
                            prev, curr = float(col.iloc[-2]), float(col.iloc[-1])
                            chg = curr - prev
                            pct = chg / prev * 100 if prev else 0
                            vol = 0
                            if volume is not None:
                                try:
                                    vol = float(volume[sym].iloc[-1])
                                except Exception:
                                    pass
                            results.append({"symbol": sym, "price": curr, "change": chg, "pct": pct, "volume": vol})
                    except Exception:
                        pass

            f = self.filters
            filtered = []
            for r in results:
                if f.get("min_pct") is not None and r["pct"] < f["min_pct"]:
                    continue
                if f.get("max_pct") is not None and r["pct"] > f["max_pct"]:
                    continue
                if f.get("min_price") and r["price"] < f["min_price"]:
                    continue
                if f.get("max_price") and r["price"] > f["max_price"]:
                    continue
                filtered.append(r)

            sort_by = f.get("sort_by", "pct")
            reverse = f.get("sort_desc", True)
            filtered.sort(key=lambda x: x.get(sort_by, 0), reverse=reverse)
            self.done.emit(filtered[:100])
        except Exception:
            self.done.emit([])


class ScreenerWidget(QWidget):
    symbol_selected = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker = None
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

        lbl = QLabel("EQS  ·  EQUITY SCREENER")
        lbl.setStyleSheet(f"color: {styles.COLOR_HIGHLIGHT}; font-size: 12px; font-weight: bold; border: none; ")
        hl.addWidget(lbl)
        hl.addStretch()

        for label, tooltip in [("Min Chg%:", "Minimum % change"), ("Max Chg%:", "Maximum % change")]:
            l = QLabel(label)
            l.setStyleSheet(f"color: {styles.COLOR_DIM}; font-size: 10px; border: none;")
            l.setToolTip(tooltip)
            hl.addWidget(l)

            spin = QDoubleSpinBox()
            spin.setRange(-20, 20)
            spin.setDecimals(1)
            spin.setSingleStep(0.5)
            spin.setStyleSheet("color: #FFFFFF; background: #171C25; border: 1px solid #2E3542; font-size: 10px; font-family: Consolas;")
            spin.setFixedWidth(60)
            hl.addWidget(spin)
            if "Min" in label:
                self.min_pct = spin
                self.min_pct.setValue(-20)
            else:
                self.max_pct = spin
                self.max_pct.setValue(20)

        sort_lbl = QLabel("Sort:")
        sort_lbl.setStyleSheet(f"color: {styles.COLOR_DIM}; font-size: 10px; border: none;")
        hl.addWidget(sort_lbl)

        self.sort_combo = QComboBox()
        self.sort_combo.addItems(["CHG% ↓", "CHG% ↑", "Price ↓", "Price ↑", "Volume ↓"])
        self.sort_combo.setStyleSheet("""
            QComboBox { background: #171C25; color: #FFFFFF; border: 1px solid #2E3542; padding: 1px 4px; font-size: 10px; font-family: Consolas; }
            QComboBox QAbstractItemView { background: #151A24; color: #C76B52; }
        """)
        self.sort_combo.setFixedWidth(90)
        hl.addWidget(self.sort_combo)

        self.run_btn = QPushButton("▶ SCAN")
        self.run_btn.setStyleSheet("""
            QPushButton { background: #171C25; color: #FFFFFF; border: 1px solid #C76B52; padding: 3px 12px; font-size: 11px; font-family: 'Segoe UI'; font-weight: 600; }
            QPushButton:hover { background: #1B212C; border-color: #F2B39A; color: #F2B39A; }
        """)
        self.run_btn.clicked.connect(self.run_scan)
        hl.addWidget(self.run_btn)

        layout.addWidget(header_w)

        self.result_table = QTableWidget()
        self.result_table.setColumnCount(5)
        self.result_table.setHorizontalHeaderLabels(["SYMBOL", "PRICE", "CHG", "CHG %", "VOLUME"])
        self.result_table.verticalHeader().setVisible(False)
        self.result_table.setShowGrid(True)
        self.result_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.result_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        hdr = self.result_table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.result_table.setColumnWidth(0, 80)
        for i in range(1, 5):
            hdr.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)
        self.result_table.verticalHeader().setDefaultSectionSize(22)
        self.result_table.horizontalHeader().setFixedHeight(22)
        self.result_table.doubleClicked.connect(self._on_double_click)
        layout.addWidget(self.result_table)

        self.status_lbl = QLabel("  Press ▶ SCAN to run screener")
        self.status_lbl.setStyleSheet(f"background: #12161D; color: {styles.COLOR_DIM}; font-size: 10px; padding: 2px 8px; border-top: 1px solid #1F2530;")
        layout.addWidget(self.status_lbl)

    def run_scan(self):
        self.run_btn.setEnabled(False)
        self.run_btn.setText("Scanning...")
        self.result_table.setRowCount(0)
        self.status_lbl.setText("  Scanning S&P 500 universe...")

        sort_map = {
            "CHG% ↓": ("pct", True), "CHG% ↑": ("pct", False),
            "Price ↓": ("price", True), "Price ↑": ("price", False),
            "Volume ↓": ("volume", True),
        }
        sort_key, sort_desc = sort_map.get(self.sort_combo.currentText(), ("pct", True))

        filters = {
            "min_pct": self.min_pct.value(),
            "max_pct": self.max_pct.value(),
            "sort_by": sort_key,
            "sort_desc": sort_desc,
        }

        if self._worker and self._worker.isRunning():
            self._worker.quit()
        self._worker = _ScreenerWorker(list(set(SP500_SAMPLE)), filters)
        self._worker.done.connect(self._on_results)
        self._worker.start()

    def _on_results(self, results):
        self.run_btn.setEnabled(True)
        self.run_btn.setText("▶ SCAN")
        self.result_table.setRowCount(len(results))

        for row, r in enumerate(results):
            sym = r["symbol"]
            price = r["price"]
            chg = r["change"]
            pct = r["pct"]
            vol = r["volume"]
            color = styles.COLOR_POSITIVE if pct >= 0 else styles.COLOR_NEGATIVE
            sign = "+" if pct >= 0 else ""

            items = [
                (sym, styles.COLOR_ACCENT, True),
                (f"{price:,.2f}", styles.COLOR_HIGHLIGHT, False),
                (f"{sign}{chg:.2f}", color, False),
                (f"{sign}{pct:.2f}%", color, False),
                (f"{int(vol):,}", styles.COLOR_DIM, False),
            ]
            for col, (txt, col_color, bold) in enumerate(items):
                item = QTableWidgetItem(txt)
                item.setForeground(QColor(col_color))
                item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter if col > 0 else Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                f = QFont("Consolas", 10)
                if bold:
                    f.setWeight(QFont.Weight.Bold)
                item.setFont(f)
                self.result_table.setItem(row, col, item)

        self.status_lbl.setText(f"  {len(results)} stocks matched  ·  Double-click to chart")

    def _on_double_click(self, index):
        row = index.row()
        item = self.result_table.item(row, 0)
        if item:
            self.symbol_selected.emit(item.text())
