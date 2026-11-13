import numpy as np
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QComboBox, QDoubleSpinBox, QLineEdit, QSpinBox,
)
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtGui import QColor, QFont
import pyqtgraph as pg
import styles
import analysis_data as ad

DEFAULT_TICKERS = "SPY,QQQ,TLT,GLD"


class _OptimizationWorker(QThread):
    done = pyqtSignal(object, str)

    def __init__(self, tickers, years, rf):
        super().__init__()
        self.tickers = tickers
        self.years = years
        self.rf = rf

    def run(self):
        from scipy.optimize import minimize

        try:
            start, end = ad.default_date_range(self.years)
            prices = ad.get_multi_history(self.tickers, start=start, end=end)
            if prices.empty or len(prices.columns) < 2:
                self.done.emit(None, "Need at least 2 valid tickers with price history.")
                return

            tickers = list(prices.columns)
            n = len(tickers)
            rets = ad.daily_returns(prices)
            mean_ann = rets.mean().values * ad.TRADING_DAYS
            cov_ann = rets.cov().values * ad.TRADING_DAYS

            def port_ret(w):
                return float(w @ mean_ann)

            def port_vol(w):
                return float(np.sqrt(max(w @ cov_ann @ w, 0)))

            bounds = [(0.0, 1.0)] * n
            w0 = np.ones(n) / n
            sum_constraint = {"type": "eq", "fun": lambda w: np.sum(w) - 1}

            # Min variance
            res_minvar = minimize(port_vol, w0, method="SLSQP", bounds=bounds, constraints=[sum_constraint])
            w_minvar = res_minvar.x if res_minvar.success else w0

            # Max Sharpe
            def neg_sharpe(w):
                v = port_vol(w)
                if v == 0:
                    return 0
                return -(port_ret(w) - self.rf) / v

            res_sharpe = minimize(neg_sharpe, w0, method="SLSQP", bounds=bounds, constraints=[sum_constraint])
            w_sharpe = res_sharpe.x if res_sharpe.success else w0

            # Efficient frontier curve
            target_returns = np.linspace(mean_ann.min(), mean_ann.max(), 30)
            frontier = []
            for tr in target_returns:
                constraints = [
                    sum_constraint,
                    {"type": "eq", "fun": lambda w, tr=tr: port_ret(w) - tr},
                ]
                res = minimize(port_vol, w0, method="SLSQP", bounds=bounds, constraints=constraints)
                if res.success:
                    frontier.append((port_vol(res.x), tr))

            # Random portfolio cloud
            rng = np.random.default_rng(42)
            cloud_w = rng.dirichlet(np.ones(n), size=2000)
            cloud_ret = cloud_w @ mean_ann
            cloud_vol = np.sqrt(np.einsum("ij,jk,ik->i", cloud_w, cov_ann, cloud_w))

            w_equal = w0

            result = {
                "tickers": tickers,
                "mean_ann": mean_ann,
                "cov_ann": cov_ann,
                "frontier": frontier,
                "cloud_ret": cloud_ret,
                "cloud_vol": cloud_vol,
                "min_var": (port_vol(w_minvar), port_ret(w_minvar), w_minvar),
                "max_sharpe": (port_vol(w_sharpe), port_ret(w_sharpe), w_sharpe),
                "equal_weight": (port_vol(w_equal), port_ret(w_equal), w_equal),
            }
            self.done.emit(result, "")
        except Exception as e:
            self.done.emit(None, f"Optimization failed: {e}")


class PortfolioOptimizationWidget(QWidget):
    def __init__(self, data_manager=None, parent=None):
        super().__init__(parent)
        self.dm = data_manager
        self._worker = None
        self._result = None
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

        title = QLabel("EFFICIENT FRONTIER / OPTIMIZATION")
        title.setStyleSheet(f"color: {styles.COLOR_HIGHLIGHT}; font-size: 13px; font-weight: bold; border: none;")
        title.setWordWrap(True)
        lv.addWidget(title)

        sub = QLabel("Mean-variance optimization from real historical returns (long-only).")
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

        self.years_spin = QSpinBox()
        self.years_spin.setRange(1, 30)
        self.years_spin.setValue(10)
        self.years_spin.setSuffix(" yrs")
        self.years_spin.setStyleSheet(self._input_style())
        lv.addWidget(self._labeled("Lookback period:", self.years_spin))

        self.rf_spin = QDoubleSpinBox()
        self.rf_spin.setRange(0, 10)
        self.rf_spin.setValue(2.0)
        self.rf_spin.setSuffix(" %")
        self.rf_spin.setDecimals(1)
        self.rf_spin.setStyleSheet(self._input_style())
        lv.addWidget(self._labeled("Risk-free rate:", self.rf_spin))

        self.objective_combo = QComboBox()
        self.objective_combo.addItems(["Max Sharpe", "Min Variance", "Equal Weight"])
        self.objective_combo.setStyleSheet(self._input_style())
        self.objective_combo.currentTextChanged.connect(self._update_weights_table)
        lv.addWidget(self._labeled("Show weights for:", self.objective_combo))

        self.run_btn = QPushButton("▶ OPTIMIZE")
        self.run_btn.setStyleSheet("""
            QPushButton { background: #171C25; color: #FFFFFF; border: 1px solid #C76B52; padding: 6px; font-size: 11px; font-family: 'Segoe UI'; font-weight: 600; }
            QPushButton:hover { background: #1B212C; border-color: #F2B39A; color: #F2B39A; }
        """)
        self.run_btn.clicked.connect(self.run_optimization)
        lv.addWidget(self.run_btn)

        self.status_lbl = QLabel("")
        self.status_lbl.setWordWrap(True)
        self.status_lbl.setStyleSheet(f"color: {styles.COLOR_DIM}; font-size: 10px; border: none;")
        lv.addWidget(self.status_lbl)

        lv.addWidget(self._section_label("WEIGHTS"))
        self.weights_table = QTableWidget(0, 2)
        self.weights_table.setHorizontalHeaderLabels(["Ticker", "Weight"])
        self.weights_table.verticalHeader().setVisible(False)
        self.weights_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.weights_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        lv.addWidget(self.weights_table)

        lv.addStretch()
        layout.addWidget(left)

        right = QWidget()
        rv = QVBoxLayout(right)
        rv.setContentsMargins(8, 8, 8, 8)

        pg.setConfigOptions(antialias=True, background="k", foreground=styles.COLOR_ACCENT)
        self.plot = pg.PlotWidget()
        self.plot.setBackground("#0A0D12")
        self.plot.showGrid(x=True, y=True, alpha=0.15)
        self.plot.setLabel("bottom", "Volatility (annualized)")
        self.plot.setLabel("left", "Expected Return (annualized)")
        self.plot.addLegend(offset=(10, 10))
        self.plot.getAxis("left").setTextPen(pg.mkPen(styles.COLOR_ACCENT))
        self.plot.getAxis("bottom").setTextPen(pg.mkPen(styles.COLOR_ACCENT))
        rv.addWidget(self.plot)

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

    def _input_style(self):
        return "color: #FFFFFF; background: #0A0D12; border: 1px solid #2E3542; padding: 3px; font-size: 11px; font-family: Consolas;"

    def _btn_style(self):
        return """
            QPushButton { background: #171C25; color: #C76B52; border: 1px solid #2E3542; padding: 3px; font-size: 10px; font-family: 'Segoe UI'; }
            QPushButton:hover { background: #1A0A00; border-color: #C76B52; }
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

    def run_optimization(self):
        tickers = [t.strip() for t in self.tickers_input.text().split(",") if t.strip()]
        if len(tickers) < 2:
            self.status_lbl.setText("Enter at least 2 tickers.")
            return

        self.run_btn.setEnabled(False)
        self.run_btn.setText("Optimizing...")
        self.status_lbl.setText("Fetching data and solving efficient frontier...")

        if self._worker and self._worker.isRunning():
            self._worker.quit()
        self._worker = _OptimizationWorker(tickers, self.years_spin.value(), self.rf_spin.value() / 100.0)
        self._worker.done.connect(self._on_result)
        self._worker.start()

    def _on_result(self, result, error):
        self.run_btn.setEnabled(True)
        self.run_btn.setText("▶ OPTIMIZE")

        if error:
            self.status_lbl.setText(error)
            return

        self._result = result
        self.status_lbl.setText(f"Solved with {len(result['tickers'])} assets  ·  {len(result['frontier'])} frontier points")
        self.plot.clear()

        self.plot.plot(
            result["cloud_vol"], result["cloud_ret"], pen=None,
            symbol="o", symbolSize=3, symbolBrush=(120, 120, 120, 80), symbolPen=None,
            name="Random portfolios",
        )

        if result["frontier"]:
            fv = [p[0] for p in result["frontier"]]
            fr = [p[1] for p in result["frontier"]]
            self.plot.plot(fv, fr, pen=pg.mkPen(styles.COLOR_ACCENT, width=2), name="Efficient frontier")

        mv_vol, mv_ret, _ = result["min_var"]
        self.plot.plot([mv_vol], [mv_ret], pen=None, symbol="star", symbolSize=16,
                        symbolBrush="#00CCFF", name="Min Variance")

        ms_vol, ms_ret, _ = result["max_sharpe"]
        self.plot.plot([ms_vol], [ms_ret], pen=None, symbol="star", symbolSize=16,
                        symbolBrush="#FFFFFF", name="Max Sharpe")

        self._update_weights_table()

    def _update_weights_table(self):
        if not self._result:
            return
        choice = self.objective_combo.currentText()
        key_map = {"Max Sharpe": "max_sharpe", "Min Variance": "min_var", "Equal Weight": "equal_weight"}
        _, _, weights = self._result[key_map[choice]]
        tickers = self._result["tickers"]

        self.weights_table.setRowCount(len(tickers))
        for i, t in enumerate(tickers):
            self.weights_table.setItem(i, 0, self._cell(t, styles.COLOR_ACCENT))
            self.weights_table.setItem(i, 1, self._cell(f"{weights[i] * 100:.1f}%", styles.COLOR_HIGHLIGHT))

    def _cell(self, text, color):
        item = QTableWidgetItem(text)
        item.setForeground(QColor(color))
        item.setFont(QFont("Consolas", 10))
        return item
