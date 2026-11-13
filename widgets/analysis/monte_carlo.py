import numpy as np
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QDoubleSpinBox, QSpinBox,
)
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtGui import QColor, QFont
import pyqtgraph as pg
import styles
import analysis_data as ad

DEFAULT_ROWS = [("SPY", 70.0), ("BND", 30.0)]


class _MonteCarloWorker(QThread):
    done = pyqtSignal(object, str)

    def __init__(self, weights, initial, years, annual_contribution, n_sims, target):
        super().__init__()
        self.weights = weights
        self.initial = initial
        self.years = years
        self.annual_contribution = annual_contribution
        self.n_sims = n_sims
        self.target = target

    def run(self):
        try:
            start, end = ad.default_date_range(15)
            prices = ad.get_multi_history(self.weights.keys(), start=start, end=end)
            if prices.empty:
                self.done.emit(None, "No price data returned for these tickers.")
                return

            tickers = [t for t in self.weights if t in prices.columns]
            if not tickers:
                self.done.emit(None, "None of the tickers had usable data.")
                return

            monthly_prices = prices[tickers].resample("ME").last()
            monthly_rets = monthly_prices.pct_change().dropna()

            w = np.array([self.weights[t] for t in tickers])
            w = w / w.sum()
            port_monthly_rets = monthly_rets.values @ w

            mu = float(np.mean(port_monthly_rets))
            sigma = float(np.std(port_monthly_rets))
            if sigma == 0:
                sigma = 1e-6

            n_months = self.years * 12
            rng = np.random.default_rng(7)
            sim_returns = rng.normal(mu, sigma, size=(self.n_sims, n_months))

            monthly_contribution = self.annual_contribution / 12.0
            paths = np.zeros((self.n_sims, n_months + 1))
            paths[:, 0] = self.initial
            for m in range(1, n_months + 1):
                paths[:, m] = paths[:, m - 1] * (1 + sim_returns[:, m - 1]) + monthly_contribution

            percentiles = {p: np.percentile(paths, p, axis=0) for p in (5, 25, 50, 75, 95)}
            ending_values = paths[:, -1]

            success_rate = None
            if self.target and self.target > 0:
                success_rate = float(np.mean(ending_values >= self.target))

            result = {
                "months": np.arange(n_months + 1),
                "percentiles": percentiles,
                "ending_values": ending_values,
                "success_rate": success_rate,
                "mu_annual": (1 + mu) ** 12 - 1,
                "sigma_annual": sigma * np.sqrt(12),
                "tickers": tickers,
            }
            self.done.emit(result, "")
        except Exception as e:
            self.done.emit(None, f"Simulation failed: {e}")


class MonteCarloWidget(QWidget):
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

        title = QLabel("MONTE CARLO SIMULATION")
        title.setStyleSheet(f"color: {styles.COLOR_HIGHLIGHT}; font-size: 13px; font-weight: bold; border: none;")
        lv.addWidget(title)

        sub = QLabel("Simulate portfolio paths from its real historical return distribution.")
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
        self.table.setFixedHeight(110)
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

        self.contribution_spin = QDoubleSpinBox()
        self.contribution_spin.setRange(-500_000, 500_000)
        self.contribution_spin.setValue(0)
        self.contribution_spin.setPrefix("$ ")
        self.contribution_spin.setDecimals(0)
        self.contribution_spin.setSingleStep(500)
        self.contribution_spin.setStyleSheet(self._input_style())
        lv.addWidget(self._labeled("Annual contribution (+) / withdrawal (−):", self.contribution_spin))

        self.years_spin = QSpinBox()
        self.years_spin.setRange(1, 50)
        self.years_spin.setValue(20)
        self.years_spin.setSuffix(" yrs")
        self.years_spin.setStyleSheet(self._input_style())
        lv.addWidget(self._labeled("Time horizon:", self.years_spin))

        self.sims_spin = QSpinBox()
        self.sims_spin.setRange(100, 5000)
        self.sims_spin.setValue(1000)
        self.sims_spin.setSingleStep(100)
        self.sims_spin.setStyleSheet(self._input_style())
        lv.addWidget(self._labeled("Simulations:", self.sims_spin))

        self.target_spin = QDoubleSpinBox()
        self.target_spin.setRange(0, 100_000_000)
        self.target_spin.setValue(0)
        self.target_spin.setPrefix("$ ")
        self.target_spin.setDecimals(0)
        self.target_spin.setSingleStep(1000)
        self.target_spin.setStyleSheet(self._input_style())
        lv.addWidget(self._labeled("Goal (0 = none):", self.target_spin))

        self.run_btn = QPushButton("▶ RUN SIMULATION")
        self.run_btn.setStyleSheet("""
            QPushButton { background: #171C25; color: #FFFFFF; border: 1px solid #C76B52; padding: 6px; font-size: 11px; font-family: 'Segoe UI'; font-weight: 600; }
            QPushButton:hover { background: #1B212C; border-color: #F2B39A; color: #F2B39A; }
        """)
        self.run_btn.clicked.connect(self.run_simulation)
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
        self.plot = pg.PlotWidget()
        self.plot.setBackground("#0A0D12")
        self.plot.showGrid(x=True, y=True, alpha=0.15)
        self.plot.setLabel("bottom", "Month")
        self.plot.setLabel("left", "Portfolio Value ($)")
        self.plot.addLegend(offset=(10, 10))
        self.plot.getAxis("left").setTextPen(pg.mkPen(styles.COLOR_ACCENT))
        self.plot.getAxis("bottom").setTextPen(pg.mkPen(styles.COLOR_ACCENT))
        rv.addWidget(self.plot, 2)

        self.hist_plot = pg.PlotWidget()
        self.hist_plot.setBackground("#0A0D12")
        self.hist_plot.showGrid(x=True, y=True, alpha=0.15)
        self.hist_plot.setLabel("bottom", "Ending Value ($)")
        self.hist_plot.setMaximumHeight(160)
        self.hist_plot.getAxis("left").setTextPen(pg.mkPen(styles.COLOR_ACCENT))
        self.hist_plot.getAxis("bottom").setTextPen(pg.mkPen(styles.COLOR_ACCENT))
        rv.addWidget(self.hist_plot, 1)

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
        lbl.setWordWrap(True)
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

    def run_simulation(self):
        weights = self._read_weights()
        if not weights:
            self.status_lbl.setText("Add at least one ticker with a positive weight.")
            return

        self.run_btn.setEnabled(False)
        self.run_btn.setText("Simulating...")
        self.status_lbl.setText("Fetching data and running simulations...")

        if self._worker and self._worker.isRunning():
            self._worker.quit()
        self._worker = _MonteCarloWorker(
            weights, self.initial_spin.value(), self.years_spin.value(),
            self.contribution_spin.value(), self.sims_spin.value(), self.target_spin.value(),
        )
        self._worker.done.connect(self._on_result)
        self._worker.start()

    def _on_result(self, result, error):
        self.run_btn.setEnabled(True)
        self.run_btn.setText("▶ RUN SIMULATION")

        if error:
            self.status_lbl.setText(error)
            return

        msg = f"{self.sims_spin.value()} paths  ·  hist. return {result['mu_annual']*100:.1f}%/yr, vol {result['sigma_annual']*100:.1f}%/yr"
        if result["success_rate"] is not None:
            msg += f"  ·  goal success rate: {result['success_rate']*100:.1f}%"
        self.status_lbl.setText(msg)

        self.plot.clear()
        months = result["months"]
        pct = result["percentiles"]

        band = pg.FillBetweenItem(
            pg.PlotDataItem(months, pct[5]), pg.PlotDataItem(months, pct[95]),
            brush=pg.mkBrush(255, 102, 0, 25),
        )
        self.plot.addItem(band)
        band2 = pg.FillBetweenItem(
            pg.PlotDataItem(months, pct[25]), pg.PlotDataItem(months, pct[75]),
            brush=pg.mkBrush(255, 102, 0, 55),
        )
        self.plot.addItem(band2)

        self.plot.plot(months, pct[50], pen=pg.mkPen(styles.COLOR_HIGHLIGHT, width=2), name="Median")
        self.plot.plot(months, pct[5], pen=pg.mkPen(styles.COLOR_DIM, width=1), name="5th / 95th pct")
        self.plot.plot(months, pct[95], pen=pg.mkPen(styles.COLOR_DIM, width=1))

        self.hist_plot.clear()
        y, x = np.histogram(result["ending_values"], bins=40)
        curve = pg.PlotCurveItem(x, y, stepMode="center", fillLevel=0, brush=pg.mkBrush(255, 102, 0, 100))
        self.hist_plot.addItem(curve)

    def sizeHint(self):
        from PyQt6.QtCore import QSize
        return QSize(900, 600)
