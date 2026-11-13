from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QRectF, QPointF
from PyQt6.QtGui import QPainter, QColor, QFont, QPen, QLinearGradient
import styles

SECTORS = {
    "Technology": {
        "etf": "XLK",
        "stocks": [("AAPL", "Apple"), ("MSFT", "Microsoft"), ("NVDA", "NVIDIA"),
                   ("AVGO", "Broadcom"), ("ORCL", "Oracle"), ("ADBE", "Adobe"),
                   ("CRM", "Salesforce"), ("AMD", "AMD"), ("INTC", "Intel")],
        "weight": 3,
    },
    "Financials": {
        "etf": "XLF",
        "stocks": [("JPM", "JPMorgan"), ("BAC", "BofA"), ("WFC", "Wells Fargo"),
                   ("GS", "Goldman"), ("MS", "Morgan Stanley"), ("BLK", "BlackRock")],
        "weight": 2,
    },
    "Healthcare": {
        "etf": "XLV",
        "stocks": [("UNH", "UnitedHealth"), ("JNJ", "J&J"), ("LLY", "Eli Lilly"),
                   ("ABBV", "AbbVie"), ("MRK", "Merck"), ("PFE", "Pfizer")],
        "weight": 2,
    },
    "Consumer Disc": {
        "etf": "XLY",
        "stocks": [("AMZN", "Amazon"), ("TSLA", "Tesla"), ("HD", "Home Depot"),
                   ("MCD", "McDonald's"), ("NKE", "Nike"), ("SBUX", "Starbucks")],
        "weight": 2,
    },
    "Industrials": {
        "etf": "XLI",
        "stocks": [("CAT", "Caterpillar"), ("BA", "Boeing"), ("HON", "Honeywell"),
                   ("GE", "GE"), ("UPS", "UPS"), ("RTX", "Raytheon")],
        "weight": 1,
    },
    "Energy": {
        "etf": "XLE",
        "stocks": [("XOM", "ExxonMobil"), ("CVX", "Chevron"), ("COP", "ConocoPhillips"),
                   ("EOG", "EOG"), ("SLB", "Schlumberger")],
        "weight": 1,
    },
    "Comm Services": {
        "etf": "XLC",
        "stocks": [("META", "Meta"), ("GOOGL", "Alphabet"), ("NFLX", "Netflix"),
                   ("DIS", "Disney"), ("CMCSA", "Comcast")],
        "weight": 2,
    },
    "Consumer Stap": {
        "etf": "XLP",
        "stocks": [("WMT", "Walmart"), ("PG", "P&G"), ("KO", "Coca-Cola"),
                   ("PEP", "PepsiCo"), ("COST", "Costco")],
        "weight": 1,
    },
    "Materials": {
        "etf": "XLB",
        "stocks": [("LIN", "Linde"), ("APD", "Air Products"), ("FCX", "Freeport"),
                   ("NEM", "Newmont")],
        "weight": 1,
    },
    "Utilities": {
        "etf": "XLU",
        "stocks": [("NEE", "NextEra"), ("D", "Dominion"), ("SO", "Southern")],
        "weight": 1,
    },
}


def _pct_to_color(pct):
    if pct is None:
        return QColor("#1F2530")
    pct = max(-5.0, min(5.0, pct))
    if pct >= 0:
        intensity = int(pct / 5.0 * 200)
        return QColor(0, intensity + 30, 0)
    else:
        intensity = int(abs(pct) / 5.0 * 200)
        return QColor(intensity + 30, 0, 0)


class _HeatmapWorker(QThread):
    done = pyqtSignal(dict)

    def run(self):
        import yfinance as yf
        from data_manager import YFINANCE_LOCK
        all_syms = []
        for sector in SECTORS.values():
            all_syms.append(sector["etf"])
            for sym, _ in sector["stocks"]:
                all_syms.append(sym)

        try:
            with YFINANCE_LOCK:
                data = yf.download(all_syms, period="2d", interval="1d",
                                   progress=False, threads=True, auto_adjust=True)
            results = {}
            if not data.empty:
                close = data["Close"] if "Close" in data.columns else data.xs("Close", axis=1, level=0)
                for sym in all_syms:
                    try:
                        col = close[sym].dropna()
                        if len(col) >= 2:
                            prev, curr = float(col.iloc[-2]), float(col.iloc[-1])
                            results[sym] = (curr - prev) / prev * 100 if prev else 0
                    except Exception:
                        pass
            self.done.emit(results)
        except Exception:
            self.done.emit({})


class HeatmapCanvas(QWidget):
    stock_clicked = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._data = {}
        self._rects = []
        self.setMinimumHeight(200)
        self.setMouseTracking(True)
        self._hovered = None

    def set_data(self, data):
        self._data = data
        self._rects = []
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#0A0D12"))

        w = self.width()
        h = self.height()
        self._rects = []

        total_weight = sum(s["weight"] for s in SECTORS.values())
        col_widths = {name: int(s["weight"] / total_weight * w) for name, s in SECTORS.items()}

        x = 0
        for sector_name, sector in SECTORS.items():
            col_w = col_widths[sector_name]
            etf = sector["etf"]
            etf_pct = self._data.get(etf)

            header_h = 28
            header_color = _pct_to_color(etf_pct)
            painter.fillRect(x, 0, col_w - 1, header_h, header_color)
            painter.setPen(QPen(QColor("#2E3542"), 1))
            painter.drawRect(x, 0, col_w - 1, header_h - 1)

            painter.setFont(QFont("Consolas", 8, QFont.Weight.Bold))
            painter.setPen(QColor("#FFFFFF"))
            short = sector_name[:10]
            painter.drawText(x + 2, 0, col_w - 4, header_h // 2 + 2,
                             Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, short)

            if etf_pct is not None:
                sign = "+" if etf_pct >= 0 else ""
                painter.setFont(QFont("Consolas", 8))
                color = QColor("#00FF88") if etf_pct >= 0 else QColor("#FF4444")
                painter.setPen(color)
                painter.drawText(x + 2, header_h // 2, col_w - 4, header_h // 2,
                                 Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                                 f"{sign}{etf_pct:.2f}%")

            stocks = sector["stocks"]
            n = len(stocks)
            if n == 0:
                x += col_w
                continue

            rows = max(1, (h - header_h) // 40) if n <= 3 else max(2, (h - header_h) // 28)
            cols_in_sec = max(1, (n + rows - 1) // rows)
            cell_w = col_w // cols_in_sec
            cell_h = (h - header_h) // rows

            for i, (sym, label) in enumerate(stocks):
                cr = i // cols_in_sec
                cc = i % cols_in_sec
                cx = x + cc * cell_w
                cy = header_h + cr * cell_h

                pct = self._data.get(sym)
                bg = _pct_to_color(pct)
                cell_rect = (cx, cy, cell_w - 1, cell_h - 1)
                painter.fillRect(*cell_rect, bg)

                if self._hovered == sym:
                    painter.setPen(QPen(QColor("#FFFFFF"), 2))
                    painter.drawRect(cx, cy, cell_w - 2, cell_h - 2)
                else:
                    painter.setPen(QPen(QColor("#1A1F29"), 1))
                    painter.drawRect(*cell_rect)

                painter.setFont(QFont("Consolas", 9, QFont.Weight.Bold))
                painter.setPen(QColor("#FFFFFF"))
                painter.drawText(cx + 2, cy + 2, cell_w - 4, cell_h // 2 - 2,
                                 Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, sym)

                if pct is not None:
                    sign = "+" if pct >= 0 else ""
                    painter.setFont(QFont("Consolas", 8))
                    c = QColor("#88FF88") if pct >= 0 else QColor("#FF8888")
                    painter.setPen(c)
                    painter.drawText(cx + 2, cy + cell_h // 2, cell_w - 4, cell_h // 2 - 2,
                                     Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                                     f"{sign}{pct:.1f}%")

                self._rects.append((cx, cy, cell_w - 1, cell_h - 1, sym))
            x += col_w

    def mouseMoveEvent(self, event):
        pos = event.position()
        for cx, cy, cw, ch, sym in self._rects:
            if cx <= pos.x() < cx + cw and cy <= pos.y() < cy + ch:
                if self._hovered != sym:
                    self._hovered = sym
                    self.update()
                self.setToolTip(sym)
                return
        if self._hovered:
            self._hovered = None
            self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position()
            for cx, cy, cw, ch, sym in self._rects:
                if cx <= pos.x() < cx + cw and cy <= pos.y() < cy + ch:
                    self.stock_clicked.emit(sym)
                    return


class HeatmapWidget(QWidget):
    stock_clicked = pyqtSignal(str)

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
        hl.setContentsMargins(8, 4, 8, 4)

        lbl = QLabel("HMAP  ·  S&P 500 SECTOR HEATMAP")
        lbl.setStyleSheet(f"color: {styles.COLOR_HIGHLIGHT}; font-size: 12px; font-weight: bold; border: none; ")
        hl.addWidget(lbl)
        hl.addStretch()

        self.status_lbl = QLabel("Loading data...")
        self.status_lbl.setStyleSheet(f"color: {styles.COLOR_DIM}; font-size: 10px; border: none;")
        hl.addWidget(self.status_lbl)

        refresh_btn = QPushButton("↺ Refresh")
        refresh_btn.setStyleSheet("""
            QPushButton { background: #151A24; color: #C76B52; border: 1px solid #2E3542; padding: 2px 8px; font-size: 10px; font-family: 'Segoe UI'; }
            QPushButton:hover { background: #1B212C; border-color: #C76B52; }
        """)
        refresh_btn.clicked.connect(self.refresh)
        hl.addWidget(refresh_btn)
        layout.addWidget(header_w)

        legend_w = QWidget()
        legend_w.setStyleSheet("background: #12161D; border-bottom: 1px solid #1A1F29;")
        legend_layout = QHBoxLayout(legend_w)
        legend_layout.setContentsMargins(8, 3, 8, 3)
        legend_layout.setSpacing(4)

        for label, color in [("< -3%", "#CC0000"), ("-3% to -1%", "#881111"),
                               ("-1% to 0%", "#441111"), ("0%", "#1F2530"),
                               ("0% to +1%", "#114411"), ("+1% to +3%", "#118811"),
                               ("> +3%", "#00CC00")]:
            dot = QLabel("■")
            dot.setStyleSheet(f"color: {color}; font-size: 12px; border: none;")
            legend_layout.addWidget(dot)
            lbl2 = QLabel(label)
            lbl2.setStyleSheet(f"color: {styles.COLOR_DIM}; font-size: 9px; border: none;")
            legend_layout.addWidget(lbl2)
            legend_layout.addSpacing(4)

        legend_layout.addStretch()
        legend_w.setFixedHeight(24)
        layout.addWidget(legend_w)

        self.canvas = HeatmapCanvas()
        self.canvas.stock_clicked.connect(self.stock_clicked)
        layout.addWidget(self.canvas, 1)

        self.refresh()

    def refresh(self):
        self.status_lbl.setText("Fetching sector data...")
        if self._worker and self._worker.isRunning():
            self._worker.quit()
        self._worker = _HeatmapWorker()
        self._worker.done.connect(self._on_data)
        self._worker.start()

    def _on_data(self, data):
        if data:
            self.canvas.set_data(data)
            self.status_lbl.setText(f"{len(data)} symbols loaded")
        else:
            self.status_lbl.setText("No data")

    def update_with_prices(self, prices):
        for sym, data in prices.items():
            if sym in self.canvas._data:
                self.canvas._data[sym] = data.get("pct", 0)
        self.canvas.update()
