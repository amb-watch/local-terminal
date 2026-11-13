import numpy as np
import pandas as pd
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QComboBox, QLineEdit, QSpinBox,
)
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtGui import QColor, QFont
import styles
import analysis_data as ad

MODEL_FACTORS = {
    "CAPM": ["Mkt-RF"],
    "FF3": ["Mkt-RF", "SMB", "HML"],
    "FF5": ["Mkt-RF", "SMB", "HML", "RMW", "CMA"],
    "Carhart": ["Mkt-RF", "SMB", "HML", "Mom"],
}


class _FactorWorker(QThread):
    done = pyqtSignal(object, str)

    def __init__(self, tickers, model, years):
        super().__init__()
        self.tickers = tickers
        self.model = model
        self.years = years

    def run(self):
        try:
            start, end = ad.default_date_range(self.years)
            factors, err = ad.get_fama_french_factors(self.model, start, end)
            if factors is None:
                self.done.emit(None, err or "Could not load Fama-French factor data.")
                return

            prices = ad.get_multi_history(self.tickers, start=start, end=end)
            if prices.empty:
                self.done.emit(None, "No price data returned for these tickers.")
                return

            tickers = [t for t in self.tickers if t in prices.columns]
            if not tickers:
                self.done.emit(None, "None of the tickers had usable data.")
                return

            monthly_prices = prices[tickers].resample("ME").last()
            monthly_rets = monthly_prices.pct_change().dropna()
            equal_w = np.ones(len(tickers)) / len(tickers)
            asset_returns = pd.Series(monthly_rets.values @ equal_w, index=monthly_rets.index)

            factors.index = factors.index.to_period("M").to_timestamp("M")
            asset_returns.index = asset_returns.index.to_period("M").to_timestamp("M")

            merged = pd.concat([asset_returns.rename("asset"), factors], axis=1, join="inner").dropna()
            if len(merged) < 12:
                self.done.emit(None, f"Only {len(merged)} overlapping months of data - need at least 12.")
                return

            factor_cols = MODEL_FACTORS[self.model]
            missing = [c for c in factor_cols if c not in merged.columns]
            if missing:
                self.done.emit(None, f"Factor data missing columns: {missing}")
                return

            y = (merged["asset"] - merged["RF"]).values
            X = merged[factor_cols].values

            reg = ad.ols_regress(y, X)
            alpha_monthly = reg["coef"][0]
            alpha_annual = (1 + alpha_monthly) ** 12 - 1

            result = {
                "factor_names": factor_cols,
                "coef": reg["coef"],
                "se": reg["se"],
                "tstat": reg["tstat"],
                "r2": reg["r2"],
                "n": reg["n"],
                "alpha_annual": alpha_annual,
                "tickers": tickers,
                "date_range": (merged.index[0], merged.index[-1]),
            }
            self.done.emit(result, "")
        except Exception as e:
            self.done.emit(None, f"Regression failed: {e}")


class FactorRegressionWidget(QWidget):
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

        title = QLabel("FACTOR REGRESSION")
        title.setStyleSheet(f"color: {styles.COLOR_HIGHLIGHT}; font-size: 13px; font-weight: bold; border: none;")
        lv.addWidget(title)

        sub = QLabel("Regress returns on real Fama-French / Carhart factors (Ken French Data Library).")
        sub.setWordWrap(True)
        sub.setStyleSheet(f"color: {styles.COLOR_DIM}; font-size: 10px; border: none;")
        lv.addWidget(sub)

        self.tickers_input = QLineEdit("AAPL")
        self.tickers_input.setStyleSheet(self._input_style())
        lv.addWidget(self._labeled("Ticker(s), comma-separated (equal-weight):", self.tickers_input))

        portfolio_btn = QPushButton("Use My Portfolio")
        portfolio_btn.setStyleSheet(self._btn_style())
        portfolio_btn.clicked.connect(self._use_my_portfolio)
        lv.addWidget(portfolio_btn)

        self.model_combo = QComboBox()
        self.model_combo.addItems(list(MODEL_FACTORS.keys()))
        self.model_combo.setCurrentText("FF3")
        self.model_combo.setStyleSheet(self._input_style())
        lv.addWidget(self._labeled("Model:", self.model_combo))

        self.years_spin = QSpinBox()
        self.years_spin.setRange(2, 30)
        self.years_spin.setValue(10)
        self.years_spin.setSuffix(" yrs")
        self.years_spin.setStyleSheet(self._input_style())
        lv.addWidget(self._labeled("Lookback period:", self.years_spin))

        self.run_btn = QPushButton("▶ RUN REGRESSION")
        self.run_btn.setStyleSheet("""
            QPushButton { background: #171C25; color: #FFFFFF; border: 1px solid #C76B52; padding: 6px; font-size: 11px; font-family: 'Segoe UI'; font-weight: 600; }
            QPushButton:hover { background: #1B212C; border-color: #F2B39A; color: #F2B39A; }
        """)
        self.run_btn.clicked.connect(self.run_regression)
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

        self.summary_lbl = QLabel("Enter a ticker and run a regression to see results.")
        self.summary_lbl.setWordWrap(True)
        self.summary_lbl.setStyleSheet(f"color: {styles.COLOR_HIGHLIGHT}; font-size: 13px; border: none;")
        rv.addWidget(self.summary_lbl)

        self.results_table = QTableWidget(0, 4)
        self.results_table.setHorizontalHeaderLabels(["FACTOR", "COEFFICIENT (β)", "STD ERR", "T-STAT"])
        self.results_table.verticalHeader().setVisible(False)
        self.results_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.results_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        rv.addWidget(self.results_table)

        note = QLabel(
            "Alpha is the intercept (monthly), annualized above. Betas measure sensitivity to each factor: "
            "Mkt-RF = market risk premium, SMB = size (small minus big), HML = value (high minus low book/market), "
            "RMW = profitability, CMA = investment, Mom = momentum. |t-stat| > ~2 is conventionally significant."
        )
        note.setWordWrap(True)
        note.setStyleSheet(f"color: {styles.COLOR_DIM}; font-size: 10px; border: none;")
        rv.addWidget(note)

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

    def run_regression(self):
        tickers = [t.strip().upper() for t in self.tickers_input.text().split(",") if t.strip()]
        if not tickers:
            self.status_lbl.setText("Enter at least one ticker.")
            return

        self.run_btn.setEnabled(False)
        self.run_btn.setText("Running...")
        self.status_lbl.setText("Fetching factor data and asset history...")

        if self._worker and self._worker.isRunning():
            self._worker.quit()
        self._worker = _FactorWorker(tickers, self.model_combo.currentText(), self.years_spin.value())
        self._worker.done.connect(self._on_result)
        self._worker.start()

    def _on_result(self, result, error):
        self.run_btn.setEnabled(True)
        self.run_btn.setText("▶ RUN REGRESSION")

        if error:
            self.status_lbl.setText(error)
            self.summary_lbl.setText(error)
            return

        self.status_lbl.setText(f"{result['n']} monthly observations")
        d0, d1 = result["date_range"]
        self.summary_lbl.setText(
            f"{', '.join(result['tickers'])}  ·  {self.model_combo.currentText()} model  ·  "
            f"{d0.strftime('%b %Y')} – {d1.strftime('%b %Y')}\n"
            f"Annualized alpha: {result['alpha_annual']*100:+.2f}%   R²: {result['r2']:.3f}"
        )

        names = ["Alpha (intercept)"] + result["factor_names"]
        self.results_table.setRowCount(len(names))
        for i, name in enumerate(names):
            self.results_table.setItem(i, 0, self._cell(name, styles.COLOR_ACCENT))
            self.results_table.setItem(i, 1, self._cell(f"{result['coef'][i]:.4f}", styles.COLOR_HIGHLIGHT))
            self.results_table.setItem(i, 2, self._cell(f"{result['se'][i]:.4f}", styles.COLOR_DIM))
            tstat = result["tstat"][i]
            color = styles.COLOR_POSITIVE if abs(tstat) > 2 else styles.COLOR_DIM
            self.results_table.setItem(i, 3, self._cell(f"{tstat:.2f}", color))

    def _cell(self, text, color):
        item = QTableWidgetItem(text)
        item.setForeground(QColor(color))
        item.setFont(QFont("Consolas", 10))
        return item
