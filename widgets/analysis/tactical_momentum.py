import numpy as np
import pandas as pd
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QLineEdit, QSpinBox, QCheckBox,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor, QFont
import pyqtgraph as pg
from pyqtgraph import DateAxisItem
import styles
import analysis_data as ad

DEFAULT_UNIVERSE = "SPY,EFA,AGG,GLD,TLT"


class _MomentumWorker(QThread):
    done = pyqtSignal(object, object, object, str)

    def __init__(self, tickers, years, lookback_months, top_k, absolute_momentum):
        super().__init__()
        self.tickers = tickers
        self.years = years
        self.lookback_months = lookback_months
        self.top_k = top_k
        self.absolute_momentum = absolute_momentum

    def run(self):
        try:
            start, end = ad.default_date_range(self.years + 2)
            prices = ad.get_multi_history(self.tickers, start=start, end=end)
            if prices.empty:
                self.done.emit(None, None, None, "No price data returned for these tickers.")
                return

            tickers = list(prices.columns)
            monthly_prices = prices.resample("ME").last()
            momentum = monthly_prices / monthly_prices.shift(self.lookback_months) - 1

            cutoff = end - pd.Timedelta(days=int(self.years * 365.25))
            usable_prices = prices[prices.index >= cutoff]
            if usable_prices.empty:
                self.done.emit(None, None, None, "Not enough history for the requested lookback window.")
                return

            prices_with_cash = usable_prices.copy()
            prices_with_cash["CASH"] = 1.0

            top_k = self.top_k
            absolute = self.absolute_momentum

            def weight_schedule(date, available_tickers):
                idx = momentum.index[momentum.index <= date]
                if len(idx) == 0:
                    return {"CASH": 1.0}
                row = momentum.loc[idx[-1]].dropna()
                if row.empty:
                    return {"CASH": 1.0}
                ranked = row.sort_values(ascending=False)
                if absolute:
                    ranked = ranked[ranked > 0]
                selected = ranked.head(top_k)
                if selected.empty:
                    return {"CASH": 1.0}
                w = {t: 1.0 / len(selected) for t in selected.index}
                return w

            port_series, port_stats = ad.run_backtest(prices_with_cash, weight_schedule, 10000.0, "monthly")

            bench_weights = {t: 1.0 / len(tickers) for t in tickers}
            bench_series, bench_stats = ad.run_backtest(usable_prices, bench_weights, 10000.0, "monthly")

            result = {
                "port_series": port_series, "port_stats": port_stats,
                "bench_series": bench_series, "bench_stats": bench_stats,
            }
            self.done.emit(result, None, None, "")
        except Exception as e:
            self.done.emit(None, None, None, f"Momentum backtest failed: {e}")


class TacticalMomentumWidget(QWidget):
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

        title = QLabel("MOMENTUM ROTATION")
        title.setStyleSheet(f"color: {styles.COLOR_HIGHLIGHT}; font-size: 13px; font-weight: bold; border: none;")
        lv.addWidget(title)

        sub = QLabel("Monthly rotation into the strongest trailing-momentum assets, vs. equal-weight buy & hold.")
        sub.setWordWrap(True)
        sub.setStyleSheet(f"color: {styles.COLOR_DIM}; font-size: 10px; border: none;")
        lv.addWidget(sub)

        self.universe_input = QLineEdit(DEFAULT_UNIVERSE)
        self.universe_input.setStyleSheet(self._input_style())
        lv.addWidget(self._labeled("Universe (comma-separated):", self.universe_input))

        self.lookback_spin = QSpinBox()
        self.lookback_spin.setRange(1, 12)
        self.lookback_spin.setValue(6)
        self.lookback_spin.setSuffix(" mo")
        self.lookback_spin.setStyleSheet(self._input_style())
        lv.addWidget(self._labeled("Momentum lookback:", self.lookback_spin))

        self.topk_spin = QSpinBox()
        self.topk_spin.setRange(1, 10)
        self.topk_spin.setValue(2)
        self.topk_spin.setStyleSheet(self._input_style())
        lv.addWidget(self._labeled("Hold top-K assets:", self.topk_spin))

        self.years_spin = QSpinBox()
        self.years_spin.setRange(2, 25)
        self.years_spin.setValue(10)
        self.years_spin.setSuffix(" yrs")
        self.years_spin.setStyleSheet(self._input_style())
        lv.addWidget(self._labeled("Backtest period:", self.years_spin))

        self.absolute_chk = QCheckBox("Absolute momentum (cash if negative)")
        self.absolute_chk.setChecked(True)
        self.absolute_chk.setStyleSheet(f"color: {styles.COLOR_ACCENT}; font-size: 10px;")
        lv.addWidget(self.absolute_chk)

        self.run_btn = QPushButton("▶ RUN BACKTEST")
        self.run_btn.setStyleSheet("""
            QPushButton { background: #171C25; color: #FFFFFF; border: 1px solid #C76B52; padding: 6px; font-size: 11px; font-family: 'Segoe UI'; font-weight: 600; }
            QPushButton:hover { background: #1B212C; border-color: #F2B39A; color: #F2B39A; }
        """)
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
        self.stats_table.setHorizontalHeaderLabels(["METRIC", "MOMENTUM STRATEGY", "BUY & HOLD"])
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
        lbl.setStyleSheet(f"color: {styles.COLOR_DIM}; font-size: 10px; border: none;")
        v.addWidget(lbl)
        v.addWidget(widget)
        return container

    def _input_style(self):
        return "color: #FFFFFF; background: #0A0D12; border: 1px solid #2E3542; padding: 3px; font-size: 11px; font-family: Consolas;"

    def run_backtest(self):
        tickers = [t.strip().upper() for t in self.universe_input.text().split(",") if t.strip()]
        if len(tickers) < 2:
            self.status_lbl.setText("Enter at least 2 tickers in the universe.")
            return

        self.run_btn.setEnabled(False)
        self.run_btn.setText("Running...")
        self.status_lbl.setText("Fetching data and rotating monthly...")

        if self._worker and self._worker.isRunning():
            self._worker.quit()
        self._worker = _MomentumWorker(
            tickers, self.years_spin.value(), self.lookback_spin.value(),
            self.topk_spin.value(), self.absolute_chk.isChecked(),
        )
        self._worker.done.connect(self._on_result)
        self._worker.start()

    def _on_result(self, result, _a, _b, error):
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
        self.plot.plot(times, port_series.values, pen=pg.mkPen(styles.COLOR_POSITIVE, width=2), name="Momentum strategy")

        if bench_series is not None and not bench_series.empty:
            b_times = bench_series.index.astype("int64").to_numpy() // 10 ** 9
            self.plot.plot(b_times, bench_series.values, pen=pg.mkPen(styles.COLOR_DIM, width=1, style=Qt.PenStyle.DashLine), name="Equal-weight buy & hold")

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
