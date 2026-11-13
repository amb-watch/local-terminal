import numpy as np
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QLineEdit, QSpinBox, QComboBox,
)
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtGui import QColor, QFont
import pyqtgraph as pg
import styles
import analysis_data as ad

DEFAULT_TICKERS = "SPY,QQQ,TLT,GLD,VNQ,EFA"
FREQ_MAP = {"Daily": "D", "Weekly": "W", "Monthly": "ME"}


class _PCAWorker(QThread):
    done = pyqtSignal(object, str)

    def __init__(self, tickers, years, freq_label):
        super().__init__()
        self.tickers = tickers
        self.years = years
        self.freq_label = freq_label

    def run(self):
        try:
            start, end = ad.default_date_range(self.years)
            prices = ad.get_multi_history(self.tickers, start=start, end=end)
            if prices.empty or len(prices.columns) < 2:
                self.done.emit(None, "Need at least 2 valid tickers with price history.")
                return

            freq = FREQ_MAP.get(self.freq_label, "D")
            resampled = prices.resample(freq).last() if freq != "D" else prices
            rets = resampled.pct_change().dropna()
            tickers = list(rets.columns)
            n = len(tickers)

            standardized = (rets - rets.mean()) / rets.std()
            corr = standardized.corr().values

            eigvals, eigvecs = np.linalg.eigh(corr)
            order = np.argsort(eigvals)[::-1]
            eigvals = eigvals[order]
            eigvecs = eigvecs[:, order]
            eigvals = np.clip(eigvals, 0, None)

            explained = eigvals / eigvals.sum() if eigvals.sum() > 0 else eigvals

            self.done.emit({
                "tickers": tickers,
                "explained": explained,
                "loadings": eigvecs,
                "n_obs": len(rets),
            }, "")
        except Exception as e:
            self.done.emit(None, f"PCA failed: {e}")


class PCAAnalysisWidget(QWidget):
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

        title = QLabel("PRINCIPAL COMPONENT ANALYSIS")
        title.setStyleSheet(f"color: {styles.COLOR_HIGHLIGHT}; font-size: 13px; font-weight: bold; border: none;")
        lv.addWidget(title)

        sub = QLabel("Decomposes the return correlation matrix into independent risk factors.")
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

        self.freq_combo = QComboBox()
        self.freq_combo.addItems(list(FREQ_MAP.keys()))
        self.freq_combo.setStyleSheet(self._input_style())
        lv.addWidget(self._labeled("Return frequency:", self.freq_combo))

        self.run_btn = QPushButton("▶ RUN PCA")
        self.run_btn.setStyleSheet(self._primary_btn_style())
        self.run_btn.clicked.connect(self.run_analysis)
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

        pg.setConfigOptions(antialias=True, background="k", foreground=styles.COLOR_ACCENT)
        self.plot = pg.PlotWidget()
        self.plot.setBackground("#0A0D12")
        self.plot.showGrid(x=False, y=True, alpha=0.15)
        self.plot.setLabel("left", "Explained Variance")
        self.plot.getAxis("left").setTextPen(pg.mkPen(styles.COLOR_ACCENT))
        self.plot.getAxis("bottom").setTextPen(pg.mkPen(styles.COLOR_ACCENT))
        self.plot.setMaximumHeight(220)
        rv.addWidget(self.plot)

        self.loadings_table = QTableWidget(0, 4)
        self.loadings_table.setHorizontalHeaderLabels(["ASSET", "PC1 LOADING", "PC2 LOADING", "PC3 LOADING"])
        self.loadings_table.verticalHeader().setVisible(False)
        self.loadings_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.loadings_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        rv.addWidget(self.loadings_table)

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

    def run_analysis(self):
        tickers = [t.strip().upper() for t in self.tickers_input.text().split(",") if t.strip()]
        if len(tickers) < 2:
            self.status_lbl.setText("Enter at least 2 tickers.")
            return

        self.run_btn.setEnabled(False)
        self.run_btn.setText("Computing...")
        self.status_lbl.setText("Fetching data and decomposing...")

        if self._worker and self._worker.isRunning():
            self._worker.quit()
        self._worker = _PCAWorker(tickers, self.years_spin.value(), self.freq_combo.currentText())
        self._worker.done.connect(self._on_result)
        self._worker.start()

    def _on_result(self, result, error):
        self.run_btn.setEnabled(True)
        self.run_btn.setText("▶ RUN PCA")

        if error:
            self.status_lbl.setText(error)
            return

        tickers = result["tickers"]
        explained = result["explained"]
        loadings = result["loadings"]

        self.status_lbl.setText(f"{result['n_obs']} observations  ·  {len(tickers)} assets  ·  PC1 explains {explained[0]*100:.1f}%")

        self.plot.clear()
        x = np.arange(len(explained))
        bars = pg.BarGraphItem(x=x, height=explained * 100, width=0.6, brush=pg.mkBrush(styles.COLOR_ACCENT))
        self.plot.addItem(bars)
        axis = self.plot.getAxis("bottom")
        axis.setTicks([[(i, f"PC{i+1}") for i in range(len(explained))]])

        n_show = min(3, loadings.shape[1])
        self.loadings_table.setRowCount(len(tickers))
        self.loadings_table.setColumnCount(1 + n_show)
        headers = ["ASSET"] + [f"PC{i+1} LOADING" for i in range(n_show)]
        self.loadings_table.setHorizontalHeaderLabels(headers)
        for i, t in enumerate(tickers):
            self.loadings_table.setItem(i, 0, self._cell(t, styles.COLOR_ACCENT))
            for c in range(n_show):
                val = loadings[i, c]
                color = styles.COLOR_POSITIVE if val >= 0 else styles.COLOR_NEGATIVE
                self.loadings_table.setItem(i, c + 1, self._cell(f"{val:+.3f}", color))

    def _cell(self, text, color):
        item = QTableWidgetItem(text)
        item.setForeground(QColor(color))
        item.setFont(QFont("Consolas", 10))
        return item
