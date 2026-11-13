import numpy as np
import pandas as pd
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QLineEdit, QSpinBox, QDoubleSpinBox,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor, QFont
import pyqtgraph as pg
from pyqtgraph import DateAxisItem
import styles
import analysis_data as ad

DEFAULT_TICKER = "SPY"


class _TargetVolWorker(QThread):
    done = pyqtSignal(object, str)

    def __init__(self, ticker, years, target_vol, vol_window):
        super().__init__()
        self.ticker = ticker
        self.years = years
        self.target_vol = target_vol
        self.vol_window = vol_window

    def run(self):
        try:
            start, end = ad.default_date_range(self.years + 1)
            prices = ad.get_multi_history([self.ticker], start=start, end=end)
            if prices.empty or self.ticker not in prices.columns:
                self.done.emit(None, "No price data returned for this ticker.")
                return

            rets = ad.daily_returns(prices[[self.ticker]])
            realized_vol = ad.rolling_annualized_vol(rets, self.vol_window)[self.ticker]

            cutoff = end - pd.Timedelta(days=int(self.years * 365.25))
            usable_prices = prices[prices.index >= cutoff]
            if usable_prices.empty:
                self.done.emit(None, "Not enough history for the requested period.")
                return

            prices_with_cash = usable_prices.copy()
            prices_with_cash["CASH"] = 1.0
            target = self.target_vol

            def weight_schedule(date, available_tickers):
                idx = realized_vol.index[realized_vol.index <= date]
                if len(idx) == 0 or pd.isna(realized_vol.loc[idx[-1]]) or realized_vol.loc[idx[-1]] <= 0:
                    return {self.ticker: 1.0}
                vol_now = realized_vol.loc[idx[-1]]
                exposure = min(target / vol_now, 1.0)
                return {self.ticker: exposure, "CASH": 1.0 - exposure}

            port_series, port_stats = ad.run_backtest(prices_with_cash, weight_schedule, 10000.0, "monthly")

            bench_series, bench_stats = ad.run_backtest(usable_prices, {self.ticker: 1.0}, 10000.0, "monthly")

            self.done.emit({
                "port_series": port_series, "port_stats": port_stats,
                "bench_series": bench_series, "bench_stats": bench_stats,
            }, "")
        except Exception as e:
            self.done.emit(None, f"Target volatility backtest failed: {e}")


class TargetVolatilityWidget(QWidget):
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

        title = QLabel("TARGET VOLATILITY")
        title.setStyleSheet(f"color: {styles.COLOR_HIGHLIGHT}; font-size: 13px; font-weight: bold; border: none;")
        lv.addWidget(title)

        sub = QLabel(
            "Scales exposure to a single asset up or down each month so realized "
            "volatility tracks a target level - the rest sits in cash."
        )
        sub.setWordWrap(True)
        sub.setStyleSheet(f"color: {styles.COLOR_DIM}; font-size: 10px; border: none;")
        lv.addWidget(sub)

        self.ticker_input = QLineEdit(DEFAULT_TICKER)
        self.ticker_input.setStyleSheet(self._input_style())
        lv.addWidget(self._labeled("Ticker:", self.ticker_input))

        self.target_spin = QDoubleSpinBox()
        self.target_spin.setRange(1, 50)
        self.target_spin.setValue(10.0)
        self.target_spin.setSuffix(" %")
        self.target_spin.setDecimals(1)
        self.target_spin.setStyleSheet(self._input_style())
        lv.addWidget(self._labeled("Target annualized volatility:", self.target_spin))

        self.window_spin = QSpinBox()
        self.window_spin.setRange(5, 120)
        self.window_spin.setValue(20)
        self.window_spin.setSuffix(" days")
        self.window_spin.setStyleSheet(self._input_style())
        lv.addWidget(self._labeled("Realized-vol lookback window:", self.window_spin))

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
        self.stats_table.setHorizontalHeaderLabels(["METRIC", "VOL-TARGETED", "BUY & HOLD"])
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
        ticker = self.ticker_input.text().strip().upper()
        if not ticker:
            self.status_lbl.setText("Enter a ticker.")
            return

        self.run_btn.setEnabled(False)
        self.run_btn.setText("Running...")
        self.status_lbl.setText("Fetching data and scaling exposure monthly...")

        if self._worker and self._worker.isRunning():
            self._worker.quit()
        self._worker = _TargetVolWorker(
            ticker, self.years_spin.value(), self.target_spin.value() / 100.0, self.window_spin.value()
        )
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
        self.plot.plot(times, port_series.values, pen=pg.mkPen(styles.COLOR_POSITIVE, width=2), name="Vol-targeted")

        if bench_series is not None and not bench_series.empty:
            b_times = bench_series.index.astype("int64").to_numpy() // 10 ** 9
            self.plot.plot(b_times, bench_series.values, pen=pg.mkPen(styles.COLOR_DIM, width=1, style=Qt.PenStyle.DashLine), name="Buy & hold")

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
