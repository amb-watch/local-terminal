from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QVBoxLayout,
)
from PyQt6.QtCore import Qt, pyqtSignal, QStringListModel
from PyQt6.QtGui import QFont, QColor
import styles


COMMANDS = {
    "CHART": "Chart - e.g. CHART AAPL 6mo",
    "DES": "Equity summary / fundamentals - DES AAPL",
    "OPTIONS": "Options chain - OPTIONS TSLA (alias: OMON)",
    "EQS": "Stock screener (alias: SCREENER)",
    "HMAP": "Sector heatmap (alias: HEATMAP)",
    "ECO": "Economic calendar (alias: CALENDAR)",
    "NEWS": "Symbol news - NEWS TSLA",
    "ALRT": "Price alert - ALRT TSLA 350 above",
    "WATCH": "Add to watchlist - WATCH NVDA",
    "REMOVE": "Remove from watchlist",
    "PORT": "Portfolio view",
    "MKTOVW": "Market indices overview",
    "FX": "Forex rates",
    "COMDTY": "Commodities",
    "CRYPTO": "Crypto prices",
    "ANALYSIS": "Open the Analysis Workbench",
    "BACKTEST": "Backtest a portfolio allocation",
    "OPTIMIZE": "Efficient frontier / portfolio optimization (alias: EFRONTIER)",
    "MONTECARLO": "Monte Carlo simulation (alias: MC)",
    "FACTOR": "Fama-French / Carhart factor regression",
    "CORREL": "Asset correlation matrix",
    "MOMENTUM": "Momentum rotation backtest",
    "RISKPARITY": "Backtest asset allocation (risk parity, alias: ALLOC)",
    "PCA": "Principal component analysis",
    "BLACKLITTERMAN": "Black-Litterman model (alias: BL)",
    "ROLLINGOPT": "Rolling optimization backtest",
    "DUALMOMENTUM": "Dual momentum backtest",
    "TARGETVOL": "Target volatility backtest",
    "HELP": "Show all commands",
    "EXIT": "Close terminal",
}


class CommandBar(QWidget):
    command_issued = pyqtSignal(str, list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(36)
        self._history = []
        self._hist_idx = -1
        self._build_ui()

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.setStyleSheet(f"background-color: #050500; border-top: 2px solid {styles.COLOR_ACCENT};")

        prefix = QLabel(" CMD:")
        prefix.setStyleSheet(f"color: {styles.COLOR_HIGHLIGHT}; font-size: 12px; font-weight: bold; padding: 0 8px; border: none;")
        prefix.setFont(QFont(styles.UI_FONT_FAMILY, 11, QFont.Weight.DemiBold))
        layout.addWidget(prefix)

        self.input = QLineEdit()
        self.input.setStyleSheet("""
            QLineEdit {
                background: transparent; color: #FFFFFF; border: none;
                font-family: Consolas; font-size: 13px; padding: 0 4px;
                caret-color: #C76B52;
            }
        """)
        self.input.setPlaceholderText("Enter command (HELP for list)  ·  e.g. CHART AAPL 3mo")
        self.input.returnPressed.connect(self._execute)
        self.input.textChanged.connect(self._on_text_changed)
        self.input.installEventFilter(self)
        layout.addWidget(self.input, 1)

        self.hint_label = QLabel("")
        self.hint_label.setStyleSheet(f"color: {styles.COLOR_DIM}; font-size: 10px; padding: 0 12px; border: none;")
        layout.addWidget(self.hint_label)

        fn_keys = ["F1:HELP", "F2:CHART", "F3:NEWS", "F4:HMAP", "F5:DES", "F6:OPT", "F7:EQS", "F9:CAL", "F10:ALRT", "F11:ANALYSIS", "F12:EXIT"]
        for key in fn_keys:
            parts = key.split(":")
            btn_w = QWidget()
            btn_w.setStyleSheet(f"background: #151A24; border-left: 1px solid #1F2530;")
            btn_layout = QHBoxLayout(btn_w)
            btn_layout.setContentsMargins(4, 0, 4, 0)
            btn_layout.setSpacing(2)

            fn_lbl = QLabel(parts[0])
            fn_lbl.setStyleSheet("color: #0A0D12; background: #8791A3; font-size: 9px; padding: 0 2px; border: none;")
            btn_layout.addWidget(fn_lbl)

            cmd_lbl = QLabel(parts[1])
            cmd_lbl.setStyleSheet(f"color: {styles.COLOR_DIM}; font-size: 9px; border: none;")
            btn_layout.addWidget(cmd_lbl)

            layout.addWidget(btn_w)

    def _on_text_changed(self, text):
        parts = text.upper().strip().split()
        if parts:
            cmd = parts[0]
            if cmd in COMMANDS:
                self.hint_label.setText(f" → {COMMANDS[cmd]}")
            else:
                matches = [c for c in COMMANDS if c.startswith(cmd)]
                if matches:
                    self.hint_label.setText(f" → {' | '.join(matches[:3])}")
                else:
                    self.hint_label.setText("")
        else:
            self.hint_label.setText("")

    def _execute(self):
        text = self.input.text().strip()
        if not text:
            return

        self._history.append(text)
        self._hist_idx = len(self._history)

        parts = text.upper().split()
        cmd = parts[0]
        args = parts[1:] if len(parts) > 1 else []

        self.command_issued.emit(cmd, args)
        self.input.clear()

    def eventFilter(self, obj, event):
        from PyQt6.QtCore import QEvent
        from PyQt6.QtGui import QKeyEvent
        if obj == self.input and event.type() == QEvent.Type.KeyPress:
            if event.key() == Qt.Key.Key_Up:
                if self._history and self._hist_idx > 0:
                    self._hist_idx -= 1
                    self.input.setText(self._history[self._hist_idx])
                return True
            if event.key() == Qt.Key.Key_Down:
                if self._hist_idx < len(self._history) - 1:
                    self._hist_idx += 1
                    self.input.setText(self._history[self._hist_idx])
                else:
                    self._hist_idx = len(self._history)
                    self.input.clear()
                return True
        return super().eventFilter(obj, event)

    def set_focus(self):
        self.input.setFocus()
        self.input.selectAll()
