import numpy as np
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QLineEdit, QSpinBox,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QFont, QPen
import styles
import analysis_data as ad

DEFAULT_TICKERS = "SPY,QQQ,TLT,GLD,VNQ"

FREQ_MAP = {"Daily": "D", "Weekly": "W", "Monthly": "ME"}


def _corr_to_color(c):
    c = max(-1.0, min(1.0, c))
    if c >= 0:
        intensity = int(c * 200)
        return QColor(0, intensity + 30, 0)
    intensity = int(abs(c) * 200)
    return QColor(intensity + 30, 0, 0)


class _CorrelationWorker(QThread):
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
            corr = rets.corr()
            tickers = list(corr.columns)
            matrix = corr.values

            n = len(tickers)
            off_diag = matrix[~np.eye(n, dtype=bool)]
            avg_corr = float(off_diag.mean()) if len(off_diag) else 0.0

            self.done.emit({"tickers": tickers, "matrix": matrix, "avg_corr": avg_corr, "n_obs": len(rets)}, "")
        except Exception as e:
            self.done.emit(None, f"Correlation analysis failed: {e}")


class CorrelationGrid(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.tickers = []
        self.matrix = None
        self.setMinimumHeight(300)

    def set_data(self, tickers, matrix):
        self.tickers = tickers
        self.matrix = matrix
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#0A0D12"))

        if not self.tickers or self.matrix is None:
            return

        n = len(self.tickers)
        label_w = 70
        w = self.width() - label_w
        h = self.height() - 24
        cell_w = w / n
        cell_h = h / n

        painter.setFont(QFont("Consolas", 9, QFont.Weight.Bold))
        for i, t in enumerate(self.tickers):
            painter.setPen(QColor(styles.COLOR_ACCENT))
            painter.drawText(int(label_w + i * cell_w), 0, int(cell_w), 24,
                              Qt.AlignmentFlag.AlignCenter, t[:6])
            painter.drawText(0, int(24 + i * cell_h), label_w - 4, int(cell_h),
                              Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, t[:8])

        painter.setFont(QFont("Consolas", 9))
        for i in range(n):
            for j in range(n):
                val = self.matrix[i, j]
                x = label_w + j * cell_w
                y = 24 + i * cell_h
                painter.fillRect(int(x), int(y), int(cell_w) - 1, int(cell_h) - 1, _corr_to_color(val))
                painter.setPen(QPen(QColor("#1A1F29"), 1))
                painter.drawRect(int(x), int(y), int(cell_w) - 1, int(cell_h) - 1)
                painter.setPen(QColor("#FFFFFF"))
                painter.drawText(int(x), int(y), int(cell_w), int(cell_h),
                                  Qt.AlignmentFlag.AlignCenter, f"{val:.2f}")


class AssetCorrelationsWidget(QWidget):
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

        title = QLabel("ASSET CORRELATIONS")
        title.setStyleSheet(f"color: {styles.COLOR_HIGHLIGHT}; font-size: 13px; font-weight: bold; border: none;")
        lv.addWidget(title)

        sub = QLabel("Real pairwise return-correlation matrix - lower average = better diversification.")
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

        self.run_btn = QPushButton("▶ COMPUTE")
        self.run_btn.setStyleSheet("""
            QPushButton { background: #171C25; color: #FFFFFF; border: 1px solid #C76B52; padding: 6px; font-size: 11px; font-family: 'Segoe UI'; font-weight: 600; }
            QPushButton:hover { background: #1B212C; border-color: #F2B39A; color: #F2B39A; }
        """)
        self.run_btn.clicked.connect(self.run_analysis)
        lv.addWidget(self.run_btn)

        self.status_lbl = QLabel("")
        self.status_lbl.setWordWrap(True)
        self.status_lbl.setStyleSheet(f"color: {styles.COLOR_DIM}; font-size: 10px; border: none;")
        lv.addWidget(self.status_lbl)

        self.avg_lbl = QLabel("")
        self.avg_lbl.setWordWrap(True)
        self.avg_lbl.setStyleSheet(f"color: {styles.COLOR_HIGHLIGHT}; font-size: 12px; font-weight: bold; border: none; margin-top: 8px;")
        lv.addWidget(self.avg_lbl)

        lv.addStretch()
        layout.addWidget(left)

        right = QWidget()
        rv = QVBoxLayout(right)
        rv.setContentsMargins(12, 12, 12, 12)
        self.grid = CorrelationGrid()
        rv.addWidget(self.grid)
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
        self.status_lbl.setText("Fetching historical prices...")

        if self._worker and self._worker.isRunning():
            self._worker.quit()
        self._worker = _CorrelationWorker(tickers, self.years_spin.value(), self.freq_combo.currentText())
        self._worker.done.connect(self._on_result)
        self._worker.start()

    def _on_result(self, result, error):
        self.run_btn.setEnabled(True)
        self.run_btn.setText("▶ COMPUTE")

        if error:
            self.status_lbl.setText(error)
            return

        self.status_lbl.setText(f"{result['n_obs']} observations  ·  {len(result['tickers'])} assets")
        self.avg_lbl.setText(f"Avg. pairwise correlation: {result['avg_corr']:.3f}")
        self.grid.set_data(result["tickers"], result["matrix"])
