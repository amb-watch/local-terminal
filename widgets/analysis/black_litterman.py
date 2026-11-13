import numpy as np
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QLineEdit, QSpinBox, QDoubleSpinBox,
)
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtGui import QColor, QFont
import styles
import analysis_data as ad

DEFAULT_TICKERS = "SPY,QQQ,TLT,GLD"


def _parse_views(text, tickers):
    """'QQQ:12,TLT:3' -> [(index_in_tickers, 0.12), (index_in_tickers, 0.03)]"""
    views = []
    for chunk in text.split(","):
        chunk = chunk.strip()
        if not chunk or ":" not in chunk:
            continue
        sym, val = chunk.split(":", 1)
        sym = sym.strip().upper()
        try:
            ret = float(val.strip()) / 100.0
        except ValueError:
            continue
        if sym in tickers:
            views.append((tickers.index(sym), ret))
    return views


class _BlackLittermanWorker(QThread):
    done = pyqtSignal(object, str)

    def __init__(self, tickers, views_text, years, tau, risk_aversion):
        super().__init__()
        self.tickers = tickers
        self.views_text = views_text
        self.years = years
        self.tau = tau
        self.risk_aversion = risk_aversion

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
            cov_ann = rets.cov().values * ad.TRADING_DAYS

            market_weights = np.ones(n) / n
            views = _parse_views(self.views_text, tickers)

            posterior, prior = ad.black_litterman(cov_ann, market_weights, views, self.tau, self.risk_aversion)

            bounds = [(0.0, 1.0)] * n
            cons = [{"type": "eq", "fun": lambda w: np.sum(w) - 1}]

            def neg_sharpe(w):
                v = np.sqrt(max(w @ cov_ann @ w, 0))
                return 0.0 if v == 0 else -(w @ posterior) / v

            res = minimize(neg_sharpe, market_weights, method="SLSQP", bounds=bounds, constraints=cons)
            weights = res.x if res.success else market_weights

            self.done.emit({
                "tickers": tickers,
                "prior": prior,
                "posterior": posterior,
                "weights": weights,
                "n_views": len(views),
            }, "")
        except Exception as e:
            self.done.emit(None, f"Black-Litterman optimization failed: {e}")


class BlackLittermanWidget(QWidget):
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

        title = QLabel("BLACK-LITTERMAN MODEL")
        title.setStyleSheet(f"color: {styles.COLOR_HIGHLIGHT}; font-size: 13px; font-weight: bold; border: none;")
        lv.addWidget(title)

        sub = QLabel(
            "Blends market-implied equilibrium returns with your own views, then "
            "optimizes for Max Sharpe on the blended (posterior) returns."
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

        self.views_input = QLineEdit("")
        self.views_input.setPlaceholderText("e.g. QQQ:15,TLT:2")
        self.views_input.setStyleSheet(self._input_style())
        lv.addWidget(self._labeled("Your views (ticker:annual return %, comma-separated, optional):", self.views_input))

        self.tau_spin = QDoubleSpinBox()
        self.tau_spin.setRange(0.01, 1.0)
        self.tau_spin.setSingleStep(0.01)
        self.tau_spin.setValue(0.05)
        self.tau_spin.setStyleSheet(self._input_style())
        lv.addWidget(self._labeled("Tau (uncertainty in the prior):", self.tau_spin))

        self.risk_spin = QDoubleSpinBox()
        self.risk_spin.setRange(0.5, 10.0)
        self.risk_spin.setSingleStep(0.1)
        self.risk_spin.setValue(2.5)
        self.risk_spin.setStyleSheet(self._input_style())
        lv.addWidget(self._labeled("Risk-aversion coefficient:", self.risk_spin))

        self.years_spin = QSpinBox()
        self.years_spin.setRange(2, 30)
        self.years_spin.setValue(10)
        self.years_spin.setSuffix(" yrs")
        self.years_spin.setStyleSheet(self._input_style())
        lv.addWidget(self._labeled("Lookback period (for covariance):", self.years_spin))

        self.run_btn = QPushButton("▶ SOLVE")
        self.run_btn.setStyleSheet(self._primary_btn_style())
        self.run_btn.clicked.connect(self.run_solve)
        lv.addWidget(self.run_btn)

        self.status_lbl = QLabel("")
        self.status_lbl.setWordWrap(True)
        self.status_lbl.setStyleSheet(f"color: {styles.COLOR_DIM}; font-size: 10px; border: none;")
        lv.addWidget(self.status_lbl)

        lv.addStretch()
        layout.addWidget(left)

        right = QWidget()
        rv = QVBoxLayout(right)
        rv.setContentsMargins(12, 12, 12, 12)
        rv.setSpacing(10)

        note = QLabel(
            "Market weights are approximated as equal-weight (no market-cap data source is wired in). "
            "Tickers you give a view for pull the posterior return toward your number; the rest stay near "
            "the equilibrium (prior) estimate."
        )
        note.setWordWrap(True)
        note.setStyleSheet(f"color: {styles.COLOR_DIM}; font-size: 10px; border: none;")
        rv.addWidget(note)

        self.results_table = QTableWidget(0, 4)
        self.results_table.setHorizontalHeaderLabels(["TICKER", "PRIOR (EQUILIBRIUM)", "POSTERIOR (BL)", "OPTIMAL WEIGHT"])
        self.results_table.verticalHeader().setVisible(False)
        self.results_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.results_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        rv.addWidget(self.results_table)

        rv.addStretch()
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

    def run_solve(self):
        tickers = [t.strip().upper() for t in self.tickers_input.text().split(",") if t.strip()]
        if len(tickers) < 2:
            self.status_lbl.setText("Enter at least 2 tickers.")
            return

        self.run_btn.setEnabled(False)
        self.run_btn.setText("Solving...")
        self.status_lbl.setText("Fetching data and blending views...")

        if self._worker and self._worker.isRunning():
            self._worker.quit()
        self._worker = _BlackLittermanWorker(
            tickers, self.views_input.text(), self.years_spin.value(),
            self.tau_spin.value(), self.risk_spin.value(),
        )
        self._worker.done.connect(self._on_result)
        self._worker.start()

    def _on_result(self, result, error):
        self.run_btn.setEnabled(True)
        self.run_btn.setText("▶ SOLVE")

        if error:
            self.status_lbl.setText(error)
            return

        self.status_lbl.setText(f"{result['n_views']} view(s) applied across {len(result['tickers'])} assets")

        tickers = result["tickers"]
        self.results_table.setRowCount(len(tickers))
        for i, t in enumerate(tickers):
            self.results_table.setItem(i, 0, self._cell(t, styles.COLOR_ACCENT))
            self.results_table.setItem(i, 1, self._cell(f"{result['prior'][i] * 100:+.2f}%", styles.COLOR_DIM))
            self.results_table.setItem(i, 2, self._cell(f"{result['posterior'][i] * 100:+.2f}%", styles.COLOR_HIGHLIGHT))
            self.results_table.setItem(i, 3, self._cell(f"{result['weights'][i] * 100:.1f}%", styles.COLOR_POSITIVE))

    def _cell(self, text, color):
        item = QTableWidgetItem(text)
        item.setForeground(QColor(color))
        item.setFont(QFont("Consolas", 10))
        return item
