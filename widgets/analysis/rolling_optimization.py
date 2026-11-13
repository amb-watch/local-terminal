import numpy as np
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

DEFAULT_TICKERS = "SPY,QQQ,TLT,GLD"


class _RollingOptWorker(QThread):
    done = pyqtSignal(object, str)

    def __init__(self, tickers, years, lookback_years, rebalance_months):
        super().__init__()
        self.tickers = tickers
        self.years = years
        self.lookback_years = lookback_years
        self.rebalance_months = rebalance_months

    def run(self):
        from scipy.optimize import minimize

        try:
            start, end = ad.default_date_range(self.years + self.lookback_years)
            prices = ad.get_multi_history(self.tickers, start=start, end=end)
            if prices.empty or len(prices.columns) < 2:
                self.done.emit(None, "Need at least 2 valid tickers with price history.")
                return

            tickers = list(prices.columns)
            n = len(tickers)
            cutoff = end - pd.Timedelta(days=int(self.years * 365.25))
            monthly_dates = prices.resample("ME").last().index
            rebalance_dates = [d for d in monthly_dates if d >= cutoff][::max(self.rebalance_months, 1)]
            if not rebalance_dates:
                self.done.emit(None, "Not enough history for the requested backtest period.")
                return

            weights_by_date = {}
            for date in rebalance_dates:
                window_start = date - pd.Timedelta(days=int(self.lookback_years * 365.25))
                hist = prices[(prices.index > window_start) & (prices.index <= date)]
                rets = hist.pct_change().dropna()
                w_equal = np.ones(n) / n
                if len(rets) < 60:
                    weights_by_date[date] = w_equal
                    continue

                mean_ann = rets.mean().values * ad.TRADING_DAYS
                cov_ann = rets.cov().values * ad.TRADING_DAYS
                bounds = [(0.0, 1.0)] * n
                cons = [{"type": "eq", "fun": lambda w: np.sum(w) - 1}]

                def neg_sharpe(w):
                    v = np.sqrt(max(w @ cov_ann @ w, 0))
                    return 0.0 if v == 0 else -(w @ mean_ann) / v

                res = minimize(neg_sharpe, w_equal, method="SLSQP", bounds=bounds, constraints=cons)
                weights_by_date[date] = res.x if res.success else w_equal

            sorted_dates = sorted(weights_by_date.keys())

            def weight_schedule(date, available_tickers):
                candidates = [d for d in sorted_dates if d <= date]
                chosen = candidates[-1] if candidates else sorted_dates[0]
                w = weights_by_date[chosen]
                return {t: w[i] for i, t in enumerate(tickers)}

            usable_prices = prices[prices.index >= cutoff]
            port_series, port_stats = ad.run_backtest(usable_prices, weight_schedule, 10000.0, "monthly")

            bench_weights = {t: 1.0 / n for t in tickers}
            bench_series, bench_stats = ad.run_backtest(usable_prices, bench_weights, 10000.0, "monthly")

            self.done.emit({
                "port_series": port_series, "port_stats": port_stats,
                "bench_series": bench_series, "bench_stats": bench_stats,
                "n_rebalances": len(sorted_dates),
            }, "")
        except Exception as e:
            self.done.emit(None, f"Rolling optimization failed: {e}")


class RollingOptimizationWidget(QWidget):
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

        title = QLabel("ROLLING OPTIMIZATION")
        title.setStyleSheet(f"color: {styles.COLOR_HIGHLIGHT}; font-size: 13px; font-weight: bold; border: none;")
        lv.addWidget(title)

        sub = QLabel(
            "Re-runs Max-Sharpe optimization on a trailing window at each rebalance, "
            "using only data available up to that point (no lookahead)."
        )
        sub.setWordWrap(True)
        sub.setStyleSheet(f"color: {styles.COLOR_DIM}; font-size: 10px; border: none;")
        lv.addWidget(sub)

        self.tickers_input = QLineEdit(DEFAULT_TICKERS)
        self.tickers_input.setStyleSheet(self._input_style())
        lv.addWidget(self._labeled("Tickers (comma-separated):", self.tickers_input))

        portfolio_btn = QPushButton("Use My Portfolio")
        portfolio_btn.setStyleSheet(self._btn_style())
        portfolio_btn.clicked.connect(self._use_my_portfolio)
        lv.addWidget(portfolio_btn)

        self.lookback_spin = QSpinBox()
        self.lookback_spin.setRange(1, 10)
        self.lookback_spin.setValue(3)
        self.lookback_spin.setSuffix(" yrs")
        self.lookback_spin.setStyleSheet(self._input_style())
        lv.addWidget(self._labeled("Optimization lookback window:", self.lookback_spin))

        self.rebalance_spin = QSpinBox()
        self.rebalance_spin.setRange(1, 24)
        self.rebalance_spin.setValue(12)
        self.rebalance_spin.setSuffix(" mo")
        self.rebalance_spin.setStyleSheet(self._input_style())
        lv.addWidget(self._labeled("Re-optimize every:", self.rebalance_spin))

        self.years_spin = QSpinBox()
        self.years_spin.setRange(2, 20)
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
        self.stats_table.setHorizontalHeaderLabels(["METRIC", "ROLLING OPT.", "EQUAL WEIGHT"])
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

    def _btn_style(self):
        return """
            QPushButton { background: #171C25; color: #C76B52; border: 1px solid #2E3542; padding: 3px; font-size: 10px; font-family: 'Segoe UI'; }
            QPushButton:hover { background: #1A0A00; border-color: #C76B52; }
        """

    def _primary_btn_style(self):
        return """
            QPushButton { background: #171C25; color: #FFFFFF; border: 1px solid #C76B52; padding: 6px; font-size: 11px; font-family: 'Segoe UI'; font-weight: 600; }
            QPushButton:hover { background: #1B212C; border-color: #F2B39A; color: #F2B39A; }
        """

    def _use_my_portfolio(self):
        if not self.dm:
            self.status_lbl.setText("Portfolio data unavailable.")
            return
        weights = self.dm.get_portfolio_weights()
        if not weights:
            self.status_lbl.setText("No saved positions yet - add some via Watchlist → Portfolio tab.")
            return
        self.tickers_input.setText(",".join(weights.keys()))
        self.status_lbl.setText(f"Loaded {len(weights)} holdings from your portfolio.")

    def run_backtest(self):
        tickers = [t.strip().upper() for t in self.tickers_input.text().split(",") if t.strip()]
        if len(tickers) < 2:
            self.status_lbl.setText("Enter at least 2 tickers.")
            return

        self.run_btn.setEnabled(False)
        self.run_btn.setText("Running...")
        self.status_lbl.setText("Fetching data and re-optimizing on a rolling window...")

        if self._worker and self._worker.isRunning():
            self._worker.quit()
        self._worker = _RollingOptWorker(
            tickers, self.years_spin.value(), self.lookback_spin.value(), self.rebalance_spin.value()
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
        self.status_lbl.setText(f"{result['n_rebalances']} re-optimizations  ·  {len(port_series)} trading days")

        self.plot.clear()
        times = port_series.index.astype("int64").to_numpy() // 10 ** 9
        self.plot.plot(times, port_series.values, pen=pg.mkPen(styles.COLOR_POSITIVE, width=2), name="Rolling optimized")

        if bench_series is not None and not bench_series.empty:
            b_times = bench_series.index.astype("int64").to_numpy() // 10 ** 9
            self.plot.plot(b_times, bench_series.values, pen=pg.mkPen(styles.COLOR_DIM, width=1, style=Qt.PenStyle.DashLine), name="Equal weight")

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
