from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QGridLayout, QScrollArea, QFrame, QTextEdit,
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread
from PyQt6.QtGui import QColor, QFont
import styles


class _FetchWorker(QThread):
    done = pyqtSignal(dict)

    def __init__(self, symbol):
        super().__init__()
        self.symbol = symbol

    def run(self):
        try:
            import yfinance as yf
            t = yf.Ticker(self.symbol)
            info = t.info or {}
            self.done.emit(info)
        except Exception:
            self.done.emit({})


def _fmt(val, decimals=2, suffix=""):
    if val is None or val == "N/A":
        return "N/A"
    try:
        v = float(val)
        if abs(v) >= 1e12:
            return f"{v/1e12:.2f}T{suffix}"
        if abs(v) >= 1e9:
            return f"{v/1e9:.2f}B{suffix}"
        if abs(v) >= 1e6:
            return f"{v/1e6:.2f}M{suffix}"
        return f"{v:,.{decimals}f}{suffix}"
    except Exception:
        return str(val)


class StatBox(QFrame):
    def __init__(self, label, value, color=None, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.Box)
        self.setStyleSheet(f"""
            QFrame {{
                background: #12161D; border: 1px solid #1F2530;
                border-radius: 0px;
            }}
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(1)

        lbl = QLabel(label)
        lbl.setStyleSheet(f"color: {styles.COLOR_DIM}; font-size: 9px; border: none; font-family: Consolas;")
        layout.addWidget(lbl)

        val_lbl = QLabel(str(value))
        val_lbl.setStyleSheet(
            f"color: {color or styles.COLOR_HIGHLIGHT}; font-size: 12px; font-weight: bold; "
            f"border: none; font-family: Consolas;"
        )
        layout.addWidget(val_lbl)
        self.val_lbl = val_lbl

    def update_value(self, value, color=None):
        self.val_lbl.setText(str(value))
        if color:
            self.val_lbl.setStyleSheet(
                f"color: {color}; font-size: 12px; font-weight: bold; border: none; font-family: Consolas;"
            )


class EquitySummaryWidget(QWidget):
    symbol_changed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_symbol = ""
        self._worker = None
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header_w = QWidget()
        header_w.setStyleSheet(f"background: #151A24; border-bottom: 1px solid {styles.COLOR_BORDER};")
        hl = QHBoxLayout(header_w)
        hl.setContentsMargins(8, 4, 8, 4)

        self.title_lbl = QLabel("DES  ·  EQUITY DESCRIPTION")
        self.title_lbl.setStyleSheet(f"color: {styles.COLOR_HIGHLIGHT}; font-size: 12px; font-weight: bold; border: none; ")
        hl.addWidget(self.title_lbl)
        hl.addStretch()

        self.sym_lbl = QLabel("No symbol loaded - use command: DES AAPL")
        self.sym_lbl.setStyleSheet(f"color: {styles.COLOR_DIM}; font-size: 11px; border: none;")
        hl.addWidget(self.sym_lbl)
        layout.addWidget(header_w)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: #0A0D12; }")

        container = QWidget()
        container.setStyleSheet("background: #0A0D12;")
        self._container_layout = QVBoxLayout(container)
        self._container_layout.setContentsMargins(8, 8, 8, 8)
        self._container_layout.setSpacing(8)

        self.price_row = QWidget()
        self.price_row.setStyleSheet("background: #12161D; border: 1px solid #1B212C;")
        pr_layout = QHBoxLayout(self.price_row)
        pr_layout.setContentsMargins(12, 8, 12, 8)
        pr_layout.setSpacing(24)

        self.lbl_price = QLabel("---")
        self.lbl_price.setStyleSheet(f"color: {styles.COLOR_HIGHLIGHT}; font-size: 24px; font-weight: bold; border: none;")
        pr_layout.addWidget(self.lbl_price)

        self.lbl_change = QLabel("")
        self.lbl_change.setStyleSheet(f"color: {styles.COLOR_DIM}; font-size: 14px; border: none;")
        pr_layout.addWidget(self.lbl_change)

        pr_layout.addStretch()

        self.lbl_name = QLabel("")
        self.lbl_name.setStyleSheet(f"color: {styles.COLOR_ACCENT}; font-size: 13px; border: none;")
        pr_layout.addWidget(self.lbl_name)

        self._container_layout.addWidget(self.price_row)

        grid_w = QWidget()
        grid_w.setStyleSheet("background: transparent;")
        self._grid = QGridLayout(grid_w)
        self._grid.setSpacing(4)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._container_layout.addWidget(grid_w)
        self._stat_boxes = {}

        stats = [
            ("Market Cap", "marketCap", None),
            ("P/E Ratio", "trailingPE", None),
            ("Forward P/E", "forwardPE", None),
            ("EPS (TTM)", "trailingEps", None),
            ("52W High", "fiftyTwoWeekHigh", styles.COLOR_POSITIVE),
            ("52W Low", "fiftyTwoWeekLow", styles.COLOR_NEGATIVE),
            ("Avg Volume", "averageVolume", None),
            ("Beta", "beta", None),
            ("Div Yield", "dividendYield", None),
            ("Revenue", "totalRevenue", None),
            ("Net Income", "netIncomeToCommon", None),
            ("ROE", "returnOnEquity", None),
            ("Debt/Equity", "debtToEquity", None),
            ("Sector", "sector", styles.COLOR_ACCENT),
            ("Industry", "industry", styles.COLOR_ACCENT),
            ("Country", "country", styles.COLOR_DIM),
        ]

        cols = 4
        for i, (label, key, color) in enumerate(stats):
            box = StatBox(label, "---", color)
            self._grid.addWidget(box, i // cols, i % cols)
            self._stat_boxes[key] = box

        desc_lbl = QLabel("DESCRIPTION")
        desc_lbl.setStyleSheet(f"color: {styles.COLOR_ACCENT}; font-size: 10px; font-weight: bold; border: none; padding-top: 4px;")
        self._container_layout.addWidget(desc_lbl)

        self.description = QTextEdit()
        self.description.setReadOnly(True)
        self.description.setMaximumHeight(100)
        self.description.setStyleSheet("""
            QTextEdit {
                background: #12161D; color: #D7DCE5; border: 1px solid #1F2530;
                font-family: Consolas; font-size: 10px;
            }
        """)
        self._container_layout.addWidget(self.description)
        self._container_layout.addStretch()

        scroll.setWidget(container)
        layout.addWidget(scroll)

    def load_symbol(self, symbol):
        symbol = symbol.upper().strip()
        if not symbol:
            return
        self.current_symbol = symbol
        self.sym_lbl.setText(f"Loading {symbol}...")
        self.lbl_price.setText("---")

        if self._worker and self._worker.isRunning():
            self._worker.quit()

        self._worker = _FetchWorker(symbol)
        self._worker.done.connect(self._on_data)
        self._worker.start()

    def _on_data(self, info):
        if not info:
            self.sym_lbl.setText(f"{self.current_symbol}  ·  No data")
            return

        sym = self.current_symbol
        name = info.get("longName") or info.get("shortName") or sym
        self.sym_lbl.setText(f"{sym}  ·  {name}")
        self.lbl_name.setText(name[:40])

        price = info.get("currentPrice") or info.get("regularMarketPrice")
        prev = info.get("regularMarketPreviousClose")
        if price:
            self.lbl_price.setText(f"{price:,.2f}")
            if prev:
                chg = price - prev
                pct = chg / prev * 100
                sign = "+" if chg >= 0 else ""
                color = styles.COLOR_POSITIVE if chg >= 0 else styles.COLOR_NEGATIVE
                self.lbl_change.setText(f"{sign}{chg:.2f}  ({sign}{pct:.2f}%)")
                self.lbl_change.setStyleSheet(f"color: {color}; font-size: 14px; border: none;")

        mappings = {
            "marketCap": lambda v: _fmt(v),
            "trailingPE": lambda v: _fmt(v),
            "forwardPE": lambda v: _fmt(v),
            "trailingEps": lambda v: _fmt(v),
            "fiftyTwoWeekHigh": lambda v: _fmt(v),
            "fiftyTwoWeekLow": lambda v: _fmt(v),
            "averageVolume": lambda v: _fmt(v),
            "beta": lambda v: _fmt(v, 3),
            "dividendYield": lambda v: _fmt((v or 0) * 100, 2, "%") if v else "N/A",
            "totalRevenue": lambda v: _fmt(v),
            "netIncomeToCommon": lambda v: _fmt(v),
            "returnOnEquity": lambda v: _fmt((v or 0) * 100, 2, "%") if v else "N/A",
            "debtToEquity": lambda v: _fmt(v),
            "sector": lambda v: str(v) if v else "N/A",
            "industry": lambda v: str(v) if v else "N/A",
            "country": lambda v: str(v) if v else "N/A",
        }

        for key, box in self._stat_boxes.items():
            val = info.get(key)
            formatted = mappings[key](val) if key in mappings else str(val or "N/A")
            box.update_value(formatted)

        desc = info.get("longBusinessSummary") or info.get("description") or ""
        self.description.setPlainText(desc)
