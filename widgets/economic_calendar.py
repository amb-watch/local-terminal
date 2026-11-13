from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QTabWidget,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor, QFont
from datetime import datetime, timedelta
import styles

FOMC_2026 = [
    "2026-01-28", "2026-03-18", "2026-04-29",
    "2026-06-17", "2026-07-29", "2026-09-16",
    "2026-10-28", "2026-12-09",
]

MACRO_EVENTS = [
    {"date": "2026-07-02", "time": "08:30", "event": "Non-Farm Payrolls (Jun)", "impact": "HIGH", "forecast": "~180K"},
    {"date": "2026-07-10", "time": "08:30", "event": "CPI (Jun)", "impact": "HIGH", "forecast": "~3.0%"},
    {"date": "2026-07-15", "time": "08:30", "event": "Retail Sales (Jun)", "impact": "MED", "forecast": "~0.3%"},
    {"date": "2026-07-17", "time": "08:30", "event": "Initial Jobless Claims", "impact": "MED", "forecast": "~220K"},
    {"date": "2026-07-23", "time": "09:45", "event": "Flash PMI (Jul)", "impact": "MED", "forecast": "~52.0"},
    {"date": "2026-07-29", "time": "14:00", "event": "FOMC Rate Decision", "impact": "HIGH", "forecast": "Hold"},
    {"date": "2026-07-30", "time": "08:30", "event": "GDP Q2 Preliminary", "impact": "HIGH", "forecast": "~2.1%"},
    {"date": "2026-08-07", "time": "08:30", "event": "Non-Farm Payrolls (Jul)", "impact": "HIGH", "forecast": "~175K"},
    {"date": "2026-08-13", "time": "08:30", "event": "CPI (Jul)", "impact": "HIGH", "forecast": "~3.1%"},
    {"date": "2026-08-14", "time": "08:30", "event": "PPI (Jul)", "impact": "MED", "forecast": "~2.8%"},
    {"date": "2026-08-22", "time": "10:00", "event": "Jackson Hole Symposium", "impact": "HIGH", "forecast": "Fed speech"},
    {"date": "2026-09-04", "time": "08:30", "event": "Non-Farm Payrolls (Aug)", "impact": "HIGH", "forecast": "~170K"},
    {"date": "2026-09-11", "time": "08:30", "event": "CPI (Aug)", "impact": "HIGH", "forecast": "~3.0%"},
    {"date": "2026-09-16", "time": "14:00", "event": "FOMC Rate Decision", "impact": "HIGH", "forecast": "Hold"},
    {"date": "2026-09-26", "time": "08:30", "event": "PCE Price Index (Aug)", "impact": "HIGH", "forecast": "~2.7%"},
]


class _EarningsWorker(QThread):
    done = pyqtSignal(list)

    def __init__(self, symbols):
        super().__init__()
        self.symbols = symbols

    def run(self):
        import yfinance as yf
        results = []
        for sym in self.symbols[:20]:
            try:
                t = yf.Ticker(sym)
                cal = t.calendar
                if cal is not None and not cal.empty:
                    for col in cal.columns:
                        row = cal[col]
                        earnings_date = row.get("Earnings Date")
                        if earnings_date:
                            try:
                                dt = str(earnings_date)[:10]
                                results.append({
                                    "date": dt, "symbol": sym,
                                    "event": f"{sym} Earnings",
                                    "impact": "MED", "forecast": "",
                                })
                            except Exception:
                                pass
            except Exception:
                pass
        results.sort(key=lambda x: x["date"])
        self.done.emit(results)


class EconomicCalendarWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker = None
        self._earnings = []
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header_w = QWidget()
        header_w.setStyleSheet(f"background: #151A24; border-bottom: 1px solid {styles.COLOR_BORDER};")
        hl = QHBoxLayout(header_w)
        hl.setContentsMargins(8, 4, 8, 4)

        lbl = QLabel("ECO  ·  ECONOMIC CALENDAR")
        lbl.setStyleSheet(f"color: {styles.COLOR_HIGHLIGHT}; font-size: 12px; font-weight: bold; border: none; ")
        hl.addWidget(lbl)
        hl.addStretch()

        now = datetime.now()
        self.date_lbl = QLabel(f"{now.strftime('%b %Y')}  ·  upcoming events")
        self.date_lbl.setStyleSheet(f"color: {styles.COLOR_DIM}; font-size: 11px; border: none;")
        hl.addWidget(self.date_lbl)
        layout.addWidget(header_w)

        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane { border: none; background: #171C25; }
            QTabBar::tab { background: #12161D; color: #8791A3; padding: 3px 10px; border: none; font-size: 10px; font-family: 'Segoe UI'; }
            QTabBar::tab:selected { color: #C76B52; border-bottom: 2px solid #C76B52; background: #151A24; }
        """)

        self.macro_table = self._make_table(["DATE", "TIME", "EVENT", "IMPACT", "FORECAST"])
        self._populate_macro()
        self.tabs.addTab(self.macro_table, "MACRO")

        self.earnings_table = self._make_table(["DATE", "SYMBOL", "EVENT", "IMPACT"])
        self.tabs.addTab(self.earnings_table, "EARNINGS")

        self.fomc_table = self._make_table(["DATE", "EVENT", "DAYS AWAY"])
        self._populate_fomc()
        self.tabs.addTab(self.fomc_table, "FOMC")

        layout.addWidget(self.tabs)
        self._load_earnings()

    def _make_table(self, cols):
        tbl = QTableWidget()
        tbl.setColumnCount(len(cols))
        tbl.setHorizontalHeaderLabels(cols)
        tbl.verticalHeader().setVisible(False)
        tbl.setShowGrid(True)
        tbl.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        tbl.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        hdr = tbl.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        tbl.setColumnWidth(0, 90)
        for i in range(1, len(cols)):
            hdr.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)
        tbl.verticalHeader().setDefaultSectionSize(22)
        tbl.horizontalHeader().setFixedHeight(22)
        return tbl

    def _add_row(self, table, row_data, highlight=False):
        row = table.rowCount()
        table.setRowCount(row + 1)
        for col, txt in enumerate(row_data):
            item = QTableWidgetItem(str(txt))
            item.setFont(QFont("Consolas", 10))
            impact_colors = {"HIGH": "#FF4B4B", "MED": "#F2B39A", "LOW": styles.COLOR_DIM}
            if col == 0:
                item.setForeground(QColor(styles.COLOR_DIM))
            elif col == len(row_data) - 1 and str(txt) in impact_colors:
                color = impact_colors[str(txt)]
                item.setForeground(QColor(color))
                item.setFont(QFont("Consolas", 10, QFont.Weight.Bold))
            else:
                item.setForeground(QColor(styles.COLOR_WHITE))

            if highlight:
                item.setBackground(QColor("#1B212C"))
            table.setItem(row, col, item)

    def _populate_macro(self):
        self.macro_table.setRowCount(0)
        today = datetime.now().date()
        events = sorted(MACRO_EVENTS, key=lambda x: x["date"])
        for ev in events:
            try:
                ev_date = datetime.strptime(ev["date"], "%Y-%m-%d").date()
                days_away = (ev_date - today).days
                if days_away < -7:
                    continue
                highlight = 0 <= days_away <= 3
                row_data = [ev["date"], ev["time"], ev["event"], ev["impact"], ev.get("forecast", "")]
                self._add_row(self.macro_table, row_data, highlight)
            except Exception:
                pass

    def _populate_fomc(self):
        self.fomc_table.setRowCount(0)
        today = datetime.now().date()
        for date_str in FOMC_2026:
            try:
                ev_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                days_away = (ev_date - today).days
                if days_away < -1:
                    continue
                label = f"{'▶ ' if days_away < 7 else ''}FOMC Rate Decision"
                row_data = [date_str, label, f"{days_away}d"]
                self._add_row(self.fomc_table, row_data, days_away < 7)
            except Exception:
                pass

    def _load_earnings(self):
        from data_manager import DEFAULT_WATCHLIST
        self._worker = _EarningsWorker(DEFAULT_WATCHLIST[:15])
        self._worker.done.connect(self._on_earnings)
        self._worker.start()

    def _on_earnings(self, items):
        self.earnings_table.setRowCount(0)
        today = datetime.now().date()
        for ev in items:
            try:
                ev_date = datetime.strptime(ev["date"], "%Y-%m-%d").date()
                if (ev_date - today).days < -1:
                    continue
                self._add_row(self.earnings_table,
                              [ev["date"], ev["symbol"], ev["event"], ev["impact"]])
            except Exception:
                pass
        if self.earnings_table.rowCount() == 0:
            self.earnings_table.setRowCount(1)
            item = QTableWidgetItem("No upcoming earnings data available")
            item.setForeground(QColor(styles.COLOR_DIM))
            self.earnings_table.setItem(0, 0, item)
