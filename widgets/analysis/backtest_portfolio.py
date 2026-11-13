from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QComboBox, QDoubleSpinBox, QLineEdit, QSpinBox,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor, QFont
import pyqtgraph as pg
from pyqtgraph import DateAxisItem
from datetime import datetime
import styles
import analysis_data as ad

DEFAULT_ROWS = [("SPY", 60.0), ("BND", 40.0)]


class _BacktestWorker(QThread):
    done = pyqtSignal(object, object, object, object, str)

    def __init__(self, weights, benchmark_weights, start_date, end_date, initial, rebalance):
        super().__init__()
        self.weights = weights
        self.benchmark_weights = benchmark_weights
        self.start_date = start_date
        self.end_date = end_date
        self.initial = initial
        self.rebalance = rebalance

    def run(self):
        try:
            all_tickers = set(self.weights) | set(self.benchmark_weights)
            prices = ad.get_multi_history(all_tickers, start=self.start_date, end=self.end_date)
            if prices.empty:
                self.done.emit(None, None, None, None, "No price data returned for these tickers.")
                return

            port_tickers = [t for t in self.weights if t in prices.columns]
            if not port_tickers:
                self.done.emit(None, None, None, None, "None of the portfolio tickers had usable data.")
                return

            port_prices = prices[port_tickers]
            port_series, port_stats = ad.run_backtest(
                port_prices, {t: self.weights[t] for t in port_tickers}, self.initial, self.rebalance
            )

            bench_tickers = [t for t in self.benchmark_weights if t in prices.columns]
            bench_series, bench_stats = (None, None)
            if bench_tickers:
                bench_prices = prices[bench_tickers]
                bench_series, bench_stats = ad.run_backtest(
                    bench_prices, {t: self.benchmark_weights[t] for t in bench_tickers}, self.initial, self.rebalance
                )

            self.done.emit(port_series, port_stats, bench_series, bench_stats, "")
        except Exception as e:
            self.done.emit(None, None, None, None, f"Backtest failed: {e}")


class BacktestPortfolioWidget(QWidget):
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

        title = QLabel("BACKTEST PORTFOLIO")
        title.setStyleSheet(f"color: {styles.COLOR_HIGHLIGHT}; font-size: 13px; font-weight: bold; border: none;")
        lv.addWidget(title)

        sub = QLabel("Test a fixed asset allocation against history or a benchmark.")
        sub.setWordWrap(True)
        sub.setStyleSheet(f"color: {styles.COLOR_DIM}; font-size: 10px; border: none;")
        lv.addWidget(sub)

        lv.addWidget(self._section_label("ALLOCATION"))

        self.table = QTableWidget(len(DEFAULT_ROWS), 2)
        self.table.setHorizontalHeaderLabels(["Ticker", "Weight %"])
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(1, 80)
        self.table.setFixedHeight(140)
        for row, (sym, w) in enumerate(DEFAULT_ROWS):
            self.table.setItem(row, 0, QTableWidgetItem(sym))
            self.table.setItem(row, 1, QTableWidgetItem(str(w)))
        lv.addWidget(self.table)

        row_btns = QHBoxLayout()
        add_btn = QPushButton("+ Row")
        rm_btn = QPushButton("− Row")
        for b in (add_btn, rm_btn):
            b.setStyleSheet(self._btn_style())
        add_btn.clicked.connect(self._add_row)
        rm_btn.clicked.connect(self._remove_row)
        row_btns.addWidget(add_btn)
        row_btns.addWidget(rm_btn)
        lv.addLayout(row_btns)

        portfolio_btn = QPushButton("Use My Portfolio")
        portfolio_btn.setStyleSheet(self._btn_style())
        portfolio_btn.clicked.connect(self._use_my_portfolio)
        lv.addWidget(portfolio_btn)

        lv.addWidget(self._section_label("PARAMETERS"))

        self.initial_spin = QDoubleSpinBox()
        self.initial_spin.setRange(100, 10_000_000)
        self.initial_spin.setValue(10000)
        self.initial_spin.setPrefix("$ ")
        self.initial_spin.setDecimals(0)
        self.initial_spin.setSingleStep(1000)
        self.initial_spin.setStyleSheet(self._input_style())
        lv.addWidget(self._labeled("Initial amount:", self.initial_spin))

        self.years_spin = QSpinBox()
        self.years_spin.setRange(1, 30)
        self.years_spin.setValue(10)
        self.years_spin.setSuffix(" yrs")
        self.years_spin.setStyleSheet(self._input_style())
        lv.addWidget(self._labeled("Lookback period:", self.years_spin))

        self.rebalance_combo = QComboBox()
        self.rebalance_combo.addItems(["Monthly", "Quarterly", "Annually", "None"])
        self.rebalance_combo.setStyleSheet(self._input_style())
        lv.addWidget(self._labeled("Rebalance:", self.rebalance_combo))

        self.benchmark_combo = QComboBox()
        self.benchmark_combo.addItems(list(ad.LAZY_PORTFOLIOS.keys()) + ["Custom Ticker"])
        self.benchmark_combo.setStyleSheet(self._input_style())
        self.benchmark_combo.currentTextChanged.connect(self._on_benchmark_changed)
        lv.addWidget(self._labeled("Benchmark:", self.benchmark_combo))

        self.custom_bench_input = QLineEdit()
        self.custom_bench_input.setPlaceholderText("e.g. SPY")
        self.custom_bench_input.setStyleSheet(self._input_style())
        self.custom_bench_input.setVisible(False)
        lv.addWidget(self.custom_bench_input)

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
        self.stats_table.setHorizontalHeaderLabels(["METRIC", "PORTFOLIO", "BENCHMARK"])
        self.stats_table.verticalHeader().setVisible(False)
        self.stats_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.stats_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.stats_table.setMaximumHeight(240)
        rv.addWidget(self.stats_table, 1)

        layout.addWidget(right, 1)

    def _section_label(self, text):
        lbl = QLabel(text)
        lbl.setStyleSheet(f"color: {styles.COLOR_ACCENT}; font-size: 10px; font-weight: bold; border: none; margin-top: 6px;")
        return lbl

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

    def _btn_style(self):
        return """
            QPushButton { background: #171C25; color: #C76B52; border: 1px solid #2E3542; padding: 3px; font-size: 10px; font-family: 'Segoe UI'; }
            QPushButton:hover { background: #1B212C; border-color: #C76B52; }
        """

    def _input_style(self):
        return "color: #FFFFFF; background: #0A0D12; border: 1px solid #2E3542; padding: 3px; font-size: 11px; font-family: Consolas;"

    def _use_my_portfolio(self):
        if not self.dm:
            self.status_lbl.setText("Portfolio data unavailable.")
            return
        weights = self.dm.get_portfolio_weights()
        if not weights:
            self.status_lbl.setText("No saved positions yet - add some via Watchlist → Portfolio tab.")
            return
        self.table.setRowCount(len(weights))
        for row, (sym, w) in enumerate(weights.items()):
            self.table.setItem(row, 0, QTableWidgetItem(sym))
            self.table.setItem(row, 1, QTableWidgetItem(f"{w * 100:.1f}"))
        self.status_lbl.setText(f"Loaded {len(weights)} holdings from your portfolio.")

    def _add_row(self):
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(""))
        self.table.setItem(row, 1, QTableWidgetItem("0"))

    def _remove_row(self):
        row = self.table.currentRow()
        if row >= 0:
            self.table.removeRow(row)

    def _on_benchmark_changed(self, text):
        self.custom_bench_input.setVisible(text == "Custom Ticker")

    def _read_weights(self):
        weights = {}
        for row in range(self.table.rowCount()):
            sym_item = self.table.item(row, 0)
            w_item = self.table.item(row, 1)
            if not sym_item or not sym_item.text().strip():
                continue
            sym = sym_item.text().upper().strip()
            try:
                w = float(w_item.text()) if w_item else 0.0
            except ValueError:
                w = 0.0
            if w > 0:
                weights[sym] = weights.get(sym, 0) + w
        return weights

    def run_backtest(self):
        weights = self._read_weights()
        if not weights:
            self.status_lbl.setText("Add at least one ticker with a positive weight.")
            return

        bench_choice = self.benchmark_combo.currentText()
        if bench_choice == "Custom Ticker":
            custom = self.custom_bench_input.text().upper().strip()
            benchmark_weights = {custom: 1.0} if custom else {}
        else:
            benchmark_weights = ad.LAZY_PORTFOLIOS.get(bench_choice, {})

        start, end = ad.default_date_range(self.years_spin.value())
        rebalance = self.rebalance_combo.currentText().lower()

        self.run_btn.setEnabled(False)
        self.run_btn.setText("Running...")
        self.status_lbl.setText("Fetching historical data and simulating...")

        if self._worker and self._worker.isRunning():
            self._worker.quit()
        self._worker = _BacktestWorker(
            weights, benchmark_weights, start, end, self.initial_spin.value(), rebalance
        )
        self._worker.done.connect(self._on_results)
        self._worker.start()

    def _on_results(self, port_series, port_stats, bench_series, bench_stats, error):
        self.run_btn.setEnabled(True)
        self.run_btn.setText("▶ RUN BACKTEST")

        if error:
            self.status_lbl.setText(error)
            return

        self.status_lbl.setText(f"Backtest complete  ·  {len(port_series)} trading days")
        self.plot.clear()

        times = port_series.index.astype("int64").to_numpy() // 10 ** 9
        self.plot.plot(times, port_series.values, pen=pg.mkPen(styles.COLOR_POSITIVE, width=2), name="Portfolio")

        if bench_series is not None and not bench_series.empty:
            b_times = bench_series.index.astype("int64").to_numpy() // 10 ** 9
            self.plot.plot(b_times, bench_series.values, pen=pg.mkPen(styles.COLOR_DIM, width=1, style=Qt.PenStyle.DashLine), name="Benchmark")

        rows = [
            ("CAGR", port_stats.get("cagr"), bench_stats.get("cagr") if bench_stats else None, "pct"),
            ("Volatility (ann.)", port_stats.get("vol"), bench_stats.get("vol") if bench_stats else None, "pct"),
            ("Sharpe Ratio", port_stats.get("sharpe"), bench_stats.get("sharpe") if bench_stats else None, "num"),
            ("Sortino Ratio", port_stats.get("sortino"), bench_stats.get("sortino") if bench_stats else None, "num"),
            ("Max Drawdown", port_stats.get("max_drawdown"), bench_stats.get("max_drawdown") if bench_stats else None, "pct"),
            ("Best Year", port_stats.get("best_year"), bench_stats.get("best_year") if bench_stats else None, "pct"),
            ("Worst Year", port_stats.get("worst_year"), bench_stats.get("worst_year") if bench_stats else None, "pct"),
            ("Final Value", port_stats.get("final_value"), bench_stats.get("final_value") if bench_stats else None, "usd"),
            ("Total Return", port_stats.get("total_return"), bench_stats.get("total_return") if bench_stats else None, "pct"),
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
