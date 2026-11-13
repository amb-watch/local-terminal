import pandas as pd
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QLineEdit, QSpinBox,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor, QFont
import pyqtgraph as pg
from pyqtgraph import DateAxisItem
import styles
import analysis_data as ad

DEFAULT_RISKY = "SPY,EFA"
DEFAULT_SAFE = "AGG"


class _DualMomentumWorker(QThread):
    done = pyqtSignal(object, str)

    def __init__(self, risky, safe, years, lookback_months):
        super().__init__()
        self.risky = risky
        self.safe = safe
        self.years = years
        self.lookback_months = lookback_months

    def run(self):
        try:
            start, end = ad.default_date_range(self.years + 1)
            all_tickers = self.risky + [self.safe]
            prices = ad.get_multi_history(all_tickers, start=start, end=end)
            if prices.empty:
                self.done.emit(None, "No price data returned for these tickers.")
                return

            risky = [t for t in self.risky if t in prices.columns]
            if len(risky) < 2 or self.safe not in prices.columns:
                self.done.emit(None, "Need at least 2 risky assets and 1 safe asset with valid data.")
                return

            monthly = prices.resample("ME").last()
            momentum = monthly / monthly.shift(self.lookback_months) - 1

            cutoff = end - pd.Timedelta(days=int(self.years * 365.25))
            usable_prices = prices[prices.index >= cutoff]
            prices_with_cash = usable_prices.copy()
            prices_with_cash["CASH"] = 1.0

            def weight_schedule(date, available_tickers):
                idx = momentum.index[momentum.index <= date]
                if len(idx) == 0:
                    return {"CASH": 1.0}
                row = momentum.loc[idx[-1], risky].dropna()
                if row.empty:
                    return {"CASH": 1.0}
                winner = row.idxmax()
                if row[winner] <= 0:
                    return {"CASH": 1.0}
                return {winner: 1.0}

            port_series, port_stats = ad.run_backtest(prices_with_cash, weight_schedule, 10000.0, "monthly")

            bench_weights = {risky[0]: 1.0}
            bench_series, bench_stats = ad.run_backtest(usable_prices[[risky[0]]], bench_weights, 10000.0, "monthly")

            self.done.emit({
                "port_series": port_series, "port_stats": port_stats,
                "bench_series": bench_series, "bench_stats": bench_stats,
                "bench_label": f"Buy & hold {risky[0]}",
            }, "")
        except Exception as e:
            self.done.emit(None, f"Dual momentum backtest failed: {e}")


class DualMomentumWidget(QWidget):
    def __init__(self, data_manager=None, parent=None):
        super().__init__(parent)
        self.dm = data_manager
        self._worker = None
        self._build_ui()

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        left = QWidget()
        left.setFixedWidth(300)
        left.setStyleSheet("background: #12161D; border-right: 1px solid #1F2530;")
        lv = QVBoxLayout(left)
        lv.setContentsMargins(10, 10, 10, 10)
        lv.setSpacing(8)

        title = QLabel("DUAL MOMENTUM")
        title.setStyleSheet(f"color: {styles.COLOR_HIGHLIGHT}; font-size: 13px; font-weight: bold; border: none;")
        lv.addWidget(title)

        sub = QLabel(
            "Classic GEM-style strategy: hold whichever risky asset has the strongest "
            "trailing momentum (relative), or move to a safe asset if even the winner's "
            "own momentum is negative (absolute)."
        )
        sub.setWordWrap(True)
        sub.setStyleSheet(f"color: {styles.COLOR_DIM}; font-size: 10px; border: none;")
        lv.addWidget(sub)

        self.risky_input = QLineEdit(DEFAULT_RISKY)
        self.risky_input.setStyleSheet(self._input_style())
        lv.addWidget(self._labeled("Risky assets (comma-separated):", self.risky_input))

        self.safe_input = QLineEdit(DEFAULT_SAFE)
        self.safe_input.setStyleSheet(self._input_style())
        lv.addWidget(self._labeled("Safe asset (absolute-momentum filter):", self.safe_input))

        self.lookback_spin = QSpinBox()
        self.lookback_spin.setRange(1, 12)
        self.lookback_spin.setValue(12)
        self.lookback_spin.setSuffix(" mo")
        self.lookback_spin.setStyleSheet(self._input_style())
        lv.addWidget(self._labeled("Momentum lookback:", self.lookback_spin))

        self.years_spin = QSpinBox()
        self.years_spin.setRange(2, 25)
        self.years_spin.setValue(10)
        self.years_spin.setSuffix(" yrs")
        self.years_spin.setStyleSheet(self._input_style())
        lv.addWidget(self._labeled("Backtest period:", self.years_spin))

        self.run_btn = QPushButton("▶ RUN BACKTEST")
        self.run_btn.setStyleSheet(self._primary_btn_style())
        self.run_btn.clicked.connect(self.run_backtest)
        lv.addWidget(self.run_btn)

        self.status_lbl = QLabel("")
        self.status_lbl.setWordWrap(True)
        self.status_lbl.setStyleSheet(f"color: {styles.COLOR_DIM}; font-size: 10px; border: none;")
        lv.addWidget(self.status_lbl)

        lv.addStretch()
        layout.addWidget(left)

        right = QWidget()
        rv = QVBoxLayout(right)
        rv.setContentsMargins(8, 8, 8, 8)
        rv.setSpacing(6)

        pg.setConfigOptions(antialias=True, background="k", foreground=styles.COLOR_ACCENT)
        self.plot = pg.PlotWidget(axisItems={"bottom": DateAxisItem()})
        self.plot.setBackground("#0A0D12")
        self.plot.showGrid(x=True, y=True, alpha=0.15)
        self.plot.addLegend(offset=(10, 10))
        self.plot.getAxis("left").setTextPen(pg.mkPen(styles.COLOR_ACCENT))
        self.plot.getAxis("bottom").setTextPen(pg.mkPen(styles.COLOR_ACCENT))
        rv.addWidget(self.plot, 2)

        self.stats_table = QTableWidget(0, 3)
        self.stats_table.setHorizontalHeaderLabels(["METRIC", "DUAL MOMENTUM", "BENCHMARK"])
        self.stats_table.verticalHeader().setVisible(False)
        self.stats_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.stats_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.stats_table.setMaximumHeight(220)
        rv.addWidget(self.stats_table, 1)

        layout.addWidget(right, 1)

    def _labeled(self, text, widget):
        container = QWidget()
        v = QVBoxLayout(container)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(2)
        lbl = QLabel(text)
        lbl.setWordWrap(True)
        lbl.setStyleSheet(f"color: {styles.COLOR_DIM}; font-size: 10px; border: none;")
        v.addWidget(lbl)
        v.addWidget(widget)
        return container

    def _input_style(self):
        return "color: #FFFFFF; background: #0A0D12; border: 1px solid #2E3542; padding: 3px; font-size: 11px; font-family: Consolas;"

    def _primary_btn_style(self):
        return """
            QPushButton { background: #171C25; color: #FFFFFF; border: 1px solid #C76B52; padding: 6px; font-size: 11px; font-family: 'Segoe UI'; font-weight: 600; }
            QPushButton:hover { background: #1B212C; border-color: #F2B39A; color: #F2B39A; }
        """

    def run_backtest(self):
        risky = [t.strip().upper() for t in self.risky_input.text().split(",") if t.strip()]
        safe = self.safe_input.text().strip().upper()
        if len(risky) < 2 or not safe:
            self.status_lbl.setText("Enter at least 2 risky assets and 1 safe asset.")
            return

        self.run_btn.setEnabled(False)
        self.run_btn.setText("Running...")
        self.status_lbl.setText("Fetching data and rotating monthly...")

        if self._worker and self._worker.isRunning():
            self._worker.quit()
        self._worker = _DualMomentumWorker(risky, safe, self.years_spin.value(), self.lookback_spin.value())
        self._worker.done.connect(self._on_result)
        self._worker.start()

    def _on_result(self, result, error):
        self.run_btn.setEnabled(True)
        self.run_btn.setText("▶ RUN BACKTEST")

        if error:
            self.status_lbl.setText(error)
            return

        port_series = result["port_series"]
        bench_series = result["bench_series"]
        self.status_lbl.setText(f"Backtest complete  ·  {len(port_series)} trading days")

        self.plot.clear()
        times = port_series.index.astype("int64").to_numpy() // 10 ** 9
        self.plot.plot(times, port_series.values, pen=pg.mkPen(styles.COLOR_POSITIVE, width=2), name="Dual Momentum")

        if bench_series is not None and not bench_series.empty:
            b_times = bench_series.index.astype("int64").to_numpy() // 10 ** 9
            self.plot.plot(b_times, bench_series.values, pen=pg.mkPen(styles.COLOR_DIM, width=1, style=Qt.PenStyle.DashLine), name=result["bench_label"])

        port_stats = result["port_stats"]
        bench_stats = result["bench_stats"]
        rows = [
            ("CAGR", port_stats.get("cagr"), bench_stats.get("cagr"), "pct"),
            ("Volatility (ann.)", port_stats.get("vol"), bench_stats.get("vol"), "pct"),
            ("Sharpe Ratio", port_stats.get("sharpe"), bench_stats.get("sharpe"), "num"),
            ("Max Drawdown", port_stats.get("max_drawdown"), bench_stats.get("max_drawdown"), "pct"),
            ("Best Year", port_stats.get("best_year"), bench_stats.get("best_year"), "pct"),
            ("Worst Year", port_stats.get("worst_year"), bench_stats.get("worst_year"), "pct"),
            ("Final Value", port_stats.get("final_value"), bench_stats.get("final_value"), "usd"),
        ]
        self.stats_table.setRowCount(len(rows))
        for r, (label, pval, bval, fmt) in enumerate(rows):
            self.stats_table.setItem(r, 0, self._cell(label, styles.COLOR_ACCENT))
            self.stats_table.setItem(r, 1, self._cell(self._fmt(pval, fmt), styles.COLOR_HIGHLIGHT))
            self.stats_table.setItem(r, 2, self._cell(self._fmt(bval, fmt), styles.COLOR_DIM))

    def _fmt(self, val, kind):
        if val is None:
            return "-"
        if kind == "pct":
            return f"{val * 100:.2f}%"
        if kind == "usd":
            return f"${val:,.0f}"
        return f"{val:.2f}"

    def _cell(self, text, color):
        item = QTableWidgetItem(text)
        item.setForeground(QColor(color))
        item.setFont(QFont("Consolas", 10))
        return item
