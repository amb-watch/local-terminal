import numpy as np
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QComboBox, QLineEdit,
)
from PyQt6.QtCore import Qt, pyqtSignal, QObject
import pyqtgraph as pg
from pyqtgraph import DateAxisItem
import styles


def _hex_to_rgb(hex_color):
    h = hex_color.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


class _ChartLoader(QObject):
    data_ready = pyqtSignal(object)

pg.setConfigOptions(antialias=True, background="k", foreground=styles.COLOR_ACCENT)


PERIODS = ["1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y"]
INTERVALS = {
    "1d": "5m",
    "5d": "15m",
    "1mo": "1d",
    "3mo": "1d",
    "6mo": "1d",
    "1y": "1wk",
    "2y": "1wk",
    "5y": "1mo",
}


class CandlestickItem(pg.GraphicsObject):
    def __init__(self, data):
        super().__init__()
        self.data = data
        self.generatePicture()

    def generatePicture(self):
        import pyqtgraph as pg
        from PyQt6.QtGui import QPainter, QPen, QColor
        from PyQt6.QtCore import QRectF
        self.picture = pg.QtGui.QPicture()
        p = QPainter(self.picture)
        p.setPen(pg.mkPen(None))
        w = (self.data[1][0] - self.data[0][0]) * 0.35 if len(self.data) > 1 else 43200

        for (t, open_, high, low, close) in self.data:
            if close >= open_:
                color = QColor(styles.COLOR_POSITIVE)
            else:
                color = QColor(styles.COLOR_NEGATIVE)
            p.setBrush(pg.mkBrush(color))
            p.setPen(pg.mkPen(color, width=1))
            p.drawLine(pg.QtCore.QPointF(t, low), pg.QtCore.QPointF(t, high))
            p.drawRect(QRectF(t - w, open_, w * 2, close - open_))

        p.end()

    def paint(self, p, *args):
        p.drawPicture(0, 0, self.picture)

    def boundingRect(self):
        if not self.data:
            return pg.QtCore.QRectF()
        times = [d[0] for d in self.data]
        lows = [d[3] for d in self.data]
        highs = [d[2] for d in self.data]
        min_t, max_t = min(times), max(times)
        min_l, max_h = min(lows), max(highs)
        padding_t = (max_t - min_t) * 0.02 if max_t != min_t else 86400
        padding_p = (max_h - min_l) * 0.05 if max_h != min_l else 1
        return pg.QtCore.QRectF(
            min_t - padding_t, min_l - padding_p,
            (max_t - min_t) + 2 * padding_t,
            (max_h - min_l) + 2 * padding_p,
        )


class ChartWidget(QWidget):
    symbol_changed = pyqtSignal(str)

    def __init__(self, data_manager, parent=None):
        super().__init__(parent)
        self.dm = data_manager
        self.current_symbol = "AAPL"
        self.current_period = "3mo"
        self.chart_type = "line"
        self._df = None
        self._loader = _ChartLoader()
        self._loader.data_ready.connect(self._do_plot)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header_w = QWidget()
        header_w.setStyleSheet(f"background-color: #151A24; border-bottom: 1px solid {styles.COLOR_BORDER};")
        header_layout = QHBoxLayout(header_w)
        header_layout.setContentsMargins(6, 2, 6, 2)
        header_layout.setSpacing(6)

        lbl = QLabel("  CHART")
        lbl.setStyleSheet(f"color: {styles.COLOR_ACCENT}; font-size: 11px; font-weight: bold; border: none;")
        header_layout.addWidget(lbl)

        self.symbol_input = QLineEdit(self.current_symbol)
        self.symbol_input.setFixedWidth(80)
        self.symbol_input.setStyleSheet(
            "color: #FFFFFF; background: #0A0D12; border: 1px solid #2E3542; padding: 1px 4px; font-size: 11px;"
        )
        self.symbol_input.returnPressed.connect(self._on_symbol_entered)
        header_layout.addWidget(self.symbol_input)

        self.symbol_label = QLabel(self.current_symbol)
        self.symbol_label.setStyleSheet(f"color: {styles.COLOR_HIGHLIGHT}; font-weight: bold; font-size: 13px; border: none;")
        header_layout.addWidget(self.symbol_label)

        self.price_label = QLabel("---")
        self.price_label.setStyleSheet(f"color: {styles.COLOR_HIGHLIGHT}; font-size: 13px; font-weight: bold; border: none;")
        header_layout.addWidget(self.price_label)

        self.change_label = QLabel("")
        self.change_label.setStyleSheet(f"color: {styles.COLOR_DIM}; font-size: 11px; border: none;")
        header_layout.addWidget(self.change_label)

        header_layout.addStretch()

        self._chart_type_buttons = {}
        for kind, label in (("line", "Line"), ("candles", "Candles")):
            btn = QPushButton(label)
            btn.setFixedHeight(20)
            btn.setStyleSheet(self._chart_type_btn_style(kind == self.chart_type))
            btn.clicked.connect(lambda checked=False, k=kind: self._set_chart_type(k))
            header_layout.addWidget(btn)
            self._chart_type_buttons[kind] = btn

        for period in PERIODS:
            btn = QPushButton(period)
            btn.setFixedWidth(36)
            btn.setFixedHeight(20)
            btn.setStyleSheet("""
                QPushButton {
                    background: #0A0D12; color: #8791A3; border: 1px solid #242A36;
                    font-size: 9px; font-family: Consolas; padding: 0;
                }
                QPushButton:hover { color: #C76B52; border-color: #C76B52; }
                QPushButton[active="true"] { color: #FFFFFF; border-color: #FFFFFF; background: #1B212C; }
            """)
            btn.setProperty("period", period)
            btn.clicked.connect(self._period_clicked)
            if period == self.current_period:
                btn.setProperty("active", "true")
                btn.style().polish(btn)
            header_layout.addWidget(btn)
            setattr(self, f"btn_{period}", btn)

        layout.addWidget(header_w)

        chart_container = QWidget()
        chart_container.setStyleSheet("background: #0A0D12;")
        chart_v = QVBoxLayout(chart_container)
        chart_v.setContentsMargins(4, 4, 4, 0)
        chart_v.setSpacing(0)

        self.plot_widget = pg.PlotWidget(
            axisItems={"bottom": DateAxisItem()},
        )
        self.plot_widget.setBackground("#0A0D12")
        self.plot_widget.showGrid(x=True, y=True, alpha=0.15)
        self.plot_widget.getAxis("left").setTextPen(pg.mkPen(styles.COLOR_ACCENT))
        self.plot_widget.getAxis("bottom").setTextPen(pg.mkPen(styles.COLOR_ACCENT))
        self.plot_widget.getAxis("left").setPen(pg.mkPen(styles.COLOR_BORDER))
        self.plot_widget.getAxis("bottom").setPen(pg.mkPen(styles.COLOR_BORDER))
        self.plot_widget.setMouseEnabled(x=True, y=False)

        self.crosshair_v = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen("#2E3542", width=1, style=Qt.PenStyle.DashLine))
        self.crosshair_h = pg.InfiniteLine(angle=0, movable=False, pen=pg.mkPen("#2E3542", width=1, style=Qt.PenStyle.DashLine))
        self.plot_widget.addItem(self.crosshair_v)
        self.plot_widget.addItem(self.crosshair_h)
        self.plot_widget.scene().sigMouseMoved.connect(self._mouse_moved)

        chart_v.addWidget(self.plot_widget, 3)

        self.volume_widget = pg.PlotWidget(axisItems={"bottom": DateAxisItem()})
        self.volume_widget.setBackground("#0A0D12")
        self.volume_widget.showGrid(x=False, y=True, alpha=0.1)
        self.volume_widget.setMaximumHeight(80)
        self.volume_widget.setMouseEnabled(x=True, y=False)
        self.volume_widget.getAxis("left").setTextPen(pg.mkPen(styles.COLOR_DIM))
        self.volume_widget.getAxis("bottom").setTextPen(pg.mkPen(styles.COLOR_ACCENT))
        chart_v.addWidget(self.volume_widget, 1)

        self.indicator_widget = pg.PlotWidget()
        self.indicator_widget.setBackground("#0A0D12")
        self.indicator_widget.showGrid(x=False, y=True, alpha=0.1)
        self.indicator_widget.setMaximumHeight(70)
        self.indicator_widget.setMouseEnabled(x=True, y=False)
        self.indicator_widget.getAxis("left").setTextPen(pg.mkPen(styles.COLOR_DIM))
        chart_v.addWidget(self.indicator_widget, 1)

        indicator_bar = QWidget()
        indicator_bar.setStyleSheet("background: #12161D; border-top: 1px solid #1F2530;")
        ind_layout = QHBoxLayout(indicator_bar)
        ind_layout.setContentsMargins(6, 2, 6, 2)
        ind_layout.setSpacing(4)

        self._ind_active = {}
        self.indicator_labels = {}

        ind_configs = [
            ("MA20", "#0088FF"), ("MA50", "#FF8800"), ("EMA20", "#00CCFF"),
            ("BB", "#AAAAFF"), ("RSI", "#FF00FF"), ("MACD", "#00FF88"), ("VOL", "#8791A3"),
        ]
        for ind, color in ind_configs:
            btn = QPushButton(ind)
            btn.setCheckable(True)
            btn.setChecked(ind in ("MA20", "MA50", "RSI", "VOL"))
            btn.setFixedHeight(18)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: #171C25; color: #8791A3; border: 1px solid #242A36;
                    font-size: 9px; font-family: Consolas; padding: 0 4px;
                }}
                QPushButton:checked {{
                    color: {color}; border-color: {color}; background: #171C25;
                }}
                QPushButton:hover {{ border-color: {color}; color: {color}; }}
            """)
            btn.toggled.connect(lambda checked, i=ind: self._on_indicator_toggled(i, checked))
            self._ind_active[ind] = btn.isChecked()
            ind_layout.addWidget(btn)
            self.indicator_labels[ind] = btn

        ind_layout.addStretch()
        self.info_label = QLabel("")
        self.info_label.setStyleSheet("color: #8791A3; font-size: 10px; border: none;")
        ind_layout.addWidget(self.info_label)

        chart_v.addWidget(indicator_bar)
        layout.addWidget(chart_container)

    def _chart_type_btn_style(self, active):
        if active:
            return f"""
                QPushButton {{
                    background: #1B212C; color: {styles.COLOR_ACCENT}; border: 1px solid {styles.COLOR_ACCENT};
                    font-size: 10px; font-family: 'Segoe UI'; padding: 0 8px;
                }}
            """
        return """
            QPushButton {
                background: #0A0D12; color: #8791A3; border: 1px solid #242A36;
                font-size: 10px; font-family: 'Segoe UI'; padding: 0 8px;
            }
            QPushButton:hover { color: #FFFFFF; border-color: #2E3542; }
        """

    def _set_chart_type(self, kind):
        self.chart_type = kind
        for k, btn in self._chart_type_buttons.items():
            btn.setStyleSheet(self._chart_type_btn_style(k == kind))
        if self._df is not None and not self._df.empty:
            self._do_plot(self._df)

    def _period_clicked(self):
        btn = self.sender()
        period = btn.property("period")
        for p in PERIODS:
            b = getattr(self, f"btn_{p}", None)
            if b:
                b.setProperty("active", str(p == period).lower())
                b.style().polish(b)
        self.current_period = period
        self.load_chart(self.current_symbol, period)

    def _on_symbol_entered(self):
        sym = self.symbol_input.text().upper().strip()
        if sym:
            self.load_chart(sym, self.current_period)
            self.symbol_changed.emit(sym)

    def load_chart(self, symbol, period=None):
        if period:
            self.current_period = period
        self.current_symbol = symbol
        self.symbol_label.setText(symbol)
        self.symbol_input.setText(symbol)

        import threading
        threading.Thread(target=self._fetch_and_plot, args=(symbol, self.current_period), daemon=True).start()

    def _fetch_and_plot(self, symbol, period):
        interval = INTERVALS.get(period, "1d")
        df = self.dm.get_chart_data(symbol, period, interval)
        if not df.empty:
            self._loader.data_ready.emit(df)

    def _on_indicator_toggled(self, ind, checked):
        self._ind_active[ind] = checked
        if hasattr(self, "_df") and self._df is not None and not self._df.empty:
            self._do_plot(self._df)

    def _do_plot(self, df):
        self._df = df
        self.plot_widget.clear()
        self.volume_widget.clear()
        self.indicator_widget.clear()
        self.plot_widget.addItem(self.crosshair_v)
        self.plot_widget.addItem(self.crosshair_h)

        if df.empty:
            return

        times = np.array(df.index.astype(np.int64) // 10**9, dtype=float)
        closes = df["Close"].values.astype(float)
        opens = df["Open"].values.astype(float)
        highs = df["High"].values.astype(float)
        lows = df["Low"].values.astype(float)
        volumes = df["Volume"].values.astype(float)

        if self.chart_type == "candles" and len(times) > 1:
            candle_data = list(zip(times, opens, highs, lows, closes))
            candles = CandlestickItem(candle_data)
            self.plot_widget.addItem(candles)
        else:
            # Friendlier default for an investing-education tool: a clean
            # price line with a soft area fill, like a consumer stock app,
            # instead of dense OHLC candlesticks.
            line_color = styles.COLOR_POSITIVE if closes[-1] >= closes[0] else styles.COLOR_NEGATIVE
            self.plot_widget.plot(times, closes, pen=pg.mkPen(line_color, width=2))
            if len(times) > 1:
                r, g, b = _hex_to_rgb(line_color)
                floor = np.full_like(closes, float(min(closes)))
                fill = pg.FillBetweenItem(
                    pg.PlotDataItem(times, closes),
                    pg.PlotDataItem(times, floor),
                    brush=pg.mkBrush(r, g, b, 45),
                )
                self.plot_widget.addItem(fill)

        # MA20
        if self._ind_active.get("MA20") and len(closes) >= 20:
            ma20 = np.convolve(closes, np.ones(20)/20, mode="valid")
            self.plot_widget.plot(times[19:], ma20, pen=pg.mkPen("#0088FF", width=1))

        # MA50
        if self._ind_active.get("MA50") and len(closes) >= 50:
            ma50 = np.convolve(closes, np.ones(50)/50, mode="valid")
            self.plot_widget.plot(times[49:], ma50, pen=pg.mkPen("#FF8800", width=1))

        # EMA20
        if self._ind_active.get("EMA20") and len(closes) >= 20:
            ema20 = self._calc_ema(closes, 20)
            self.plot_widget.plot(times, ema20, pen=pg.mkPen("#00CCFF", width=1, style=Qt.PenStyle.DashLine))

        # Bollinger Bands
        if self._ind_active.get("BB") and len(closes) >= 20:
            ma20 = np.convolve(closes, np.ones(20)/20, mode="valid")
            t20 = times[19:]
            rolling_std = np.array([np.std(closes[i-19:i+1]) for i in range(19, len(closes))])
            upper = ma20 + 2 * rolling_std
            lower = ma20 - 2 * rolling_std
            self.plot_widget.plot(t20, upper, pen=pg.mkPen("#AAAAFF", width=1, style=Qt.PenStyle.DotLine))
            self.plot_widget.plot(t20, lower, pen=pg.mkPen("#AAAAFF", width=1, style=Qt.PenStyle.DotLine))
            fill = pg.FillBetweenItem(
                pg.PlotDataItem(t20, upper), pg.PlotDataItem(t20, lower),
                brush=pg.mkBrush(100, 100, 255, 20)
            )
            self.plot_widget.addItem(fill)

        padding = (times[-1] - times[0]) * 0.03 if len(times) > 1 else 86400
        price_range = max(highs) - min(lows)
        self.plot_widget.setXRange(times[0] - padding, times[-1] + padding, padding=0)
        self.plot_widget.setYRange(min(lows) - price_range * 0.05, max(highs) + price_range * 0.05, padding=0)

        # Volume
        if self._ind_active.get("VOL"):
            vol_colors = []
            for i in range(len(closes)):
                if closes[i] >= opens[i]:
                    vol_colors.append(pg.mkBrush(styles.COLOR_POSITIVE + "88"))
                else:
                    vol_colors.append(pg.mkBrush(styles.COLOR_NEGATIVE + "88"))
            bar_width = (times[-1] - times[0]) / len(times) * 0.7 if len(times) > 1 else 86400
            bg = pg.BarGraphItem(x=times, height=volumes, width=bar_width, brushes=vol_colors)
            self.volume_widget.addItem(bg)

        # Indicator panel: RSI or MACD
        if self._ind_active.get("RSI") and len(closes) >= 14:
            rsi = self._calc_rsi(closes)
            self.indicator_widget.plot(times[14:], rsi, pen=pg.mkPen("#FF00FF", width=1))
            self.indicator_widget.addLine(y=70, pen=pg.mkPen("#FF4B4B88", width=1, style=Qt.PenStyle.DashLine))
            self.indicator_widget.addLine(y=30, pen=pg.mkPen("#33FF3388", width=1, style=Qt.PenStyle.DashLine))
            self.indicator_widget.setYRange(0, 100)
        elif self._ind_active.get("MACD") and len(closes) >= 26:
            macd_line, signal, hist = self._calc_macd(closes)
            t_macd = times[25:]
            self.indicator_widget.plot(t_macd, macd_line, pen=pg.mkPen("#00FF88", width=1))
            self.indicator_widget.plot(t_macd[8:], signal, pen=pg.mkPen("#FF8800", width=1))
            hist_colors = [pg.mkBrush("#00AA44" if v >= 0 else "#AA2222") for v in hist]
            bw = (times[-1] - times[0]) / len(times) * 0.7 if len(times) > 1 else 86400
            self.indicator_widget.addItem(pg.BarGraphItem(x=t_macd[8:], height=hist, width=bw, brushes=hist_colors))

        price = closes[-1]
        prev = closes[-2] if len(closes) > 1 else closes[-1]
        chg = price - prev
        pct = (chg / prev * 100) if prev else 0
        sign = "+" if chg >= 0 else ""
        color = styles.COLOR_POSITIVE if chg >= 0 else styles.COLOR_NEGATIVE
        self.price_label.setText(f"{price:,.2f}")
        self.change_label.setText(f"{sign}{chg:,.2f} ({sign}{pct:.2f}%)")
        self.change_label.setStyleSheet(f"color: {color}; font-size: 11px; border: none;")

    def _calc_ema(self, data, period):
        ema = np.zeros_like(data)
        k = 2.0 / (period + 1)
        ema[0] = data[0]
        for i in range(1, len(data)):
            ema[i] = data[i] * k + ema[i-1] * (1 - k)
        return ema

    def _calc_macd(self, closes, fast=12, slow=26, signal=9):
        ema_fast = self._calc_ema(closes, fast)
        ema_slow = self._calc_ema(closes, slow)
        macd_line = ema_fast[slow-1:] - ema_slow[slow-1:]
        signal_line = self._calc_ema(macd_line, signal)[signal-1:]
        histogram = macd_line[signal-1:] - signal_line
        return macd_line, signal_line, histogram

    def _calc_rsi(self, closes, period=14):
        deltas = np.diff(closes)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        avg_gain = np.convolve(gains, np.ones(period)/period, mode="valid")
        avg_loss = np.convolve(losses, np.ones(period)/period, mode="valid")
        rs = np.where(avg_loss != 0, avg_gain / avg_loss, 100)
        return 100 - (100 / (1 + rs))

    def _mouse_moved(self, pos):
        if self.plot_widget.sceneBoundingRect().contains(pos):
            mp = self.plot_widget.plotItem.vb.mapSceneToView(pos)
            self.crosshair_v.setPos(mp.x())
            self.crosshair_h.setPos(mp.y())

    def update_price(self, symbol, data):
        if symbol == self.current_symbol:
            price = data.get("price")
            chg = data.get("change")
            pct = data.get("pct")
            if not price:
                return

            if self._df is not None and not self._df.empty:
                # Bake the live tick into today's bar and redraw so the chart
                # (candle, moving averages, RSI/MACD) reflects the current price
                # instead of only the header labels.
                last_idx = self._df.index[-1]
                self._df.loc[last_idx, "Close"] = price
                if price > self._df.loc[last_idx, "High"]:
                    self._df.loc[last_idx, "High"] = price
                if price < self._df.loc[last_idx, "Low"]:
                    self._df.loc[last_idx, "Low"] = price
                self._do_plot(self._df)
            else:
                sign = "+" if chg >= 0 else ""
                color = styles.COLOR_POSITIVE if chg >= 0 else styles.COLOR_NEGATIVE
                self.price_label.setText(f"{price:,.2f}")
                self.change_label.setText(f"{sign}{chg:,.2f} ({sign}{pct:.2f}%)")
                self.change_label.setStyleSheet(f"color: {color}; font-size: 11px; border: none;")
