from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QApplication, QMessageBox, QTabWidget, QStackedWidget,
)
from PyQt6.QtCore import Qt, QTimer, pyqtSlot
from PyQt6.QtGui import QFont
from datetime import datetime
import styles

from widgets.title_bar import TitleBar
from widgets.market_overview import MarketOverviewWidget
from widgets.chart_widget import ChartWidget
from widgets.watchlist import WatchlistWidget
from widgets.news_feed import NewsFeedWidget
from widgets.command_bar import CommandBar
from widgets.status_bar import StatusBar
from widgets.equity_summary import EquitySummaryWidget
from widgets.options_chain import OptionsChainWidget
from widgets.screener import ScreenerWidget
from widgets.heatmap import HeatmapWidget
from widgets.economic_calendar import EconomicCalendarWidget
from widgets.alerts import AlertsWidget
from widgets.analysis.analysis_hub import AnalysisHubWidget
from data_manager import DataManager

TAB_NEWS = 0
TAB_DES = 1
TAB_OPTIONS = 2
TAB_SCREENER = 3
TAB_HEATMAP = 4
TAB_CALENDAR = 5
TAB_ALERTS = 6


class AMBTerminal(QMainWindow):
    def __init__(self, target_screen=None):
        super().__init__()
        self.dm = DataManager()
        self._df = None
        self._setup_window(target_screen)
        self._build_ui()
        self._connect_signals()
        self._start_data()

    def _setup_window(self, target_screen=None):
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.Window
        )
        self.setStyleSheet(styles.TERMINAL_STYLE)
        if target_screen is not None:
            self.setGeometry(target_screen.geometry())
        self.showFullScreen()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self.title_bar = TitleBar(self)
        root_layout.addWidget(self.title_bar)

        # Main horizontal split: left sidebar | right content
        main_split = QSplitter(Qt.Orientation.Horizontal)
        main_split.setHandleWidth(3)
        main_split.setStyleSheet("QSplitter::handle { background: #1A1A1A; }")

        # LEFT: Market Overview + Watchlist (stacked vertically)
        left_split = QSplitter(Qt.Orientation.Vertical)
        left_split.setHandleWidth(3)
        left_split.setStyleSheet("QSplitter::handle { background: #1A1A1A; }")

        self.market_overview = MarketOverviewWidget()
        left_split.addWidget(self.market_overview)

        self.watchlist = WatchlistWidget(self.dm)
        left_split.addWidget(self.watchlist)

        left_split.setSizes([350, 350])
        main_split.addWidget(left_split)

        # RIGHT: Chart on top + Function Tabs on bottom
        right_split = QSplitter(Qt.Orientation.Vertical)
        right_split.setHandleWidth(3)
        right_split.setStyleSheet("QSplitter::handle { background: #1A1A1A; }")

        self.chart_widget = ChartWidget(self.dm)
        right_split.addWidget(self.chart_widget)

        # Function tabs panel (lower right)
        self.function_tabs = QTabWidget()
        self.function_tabs.setStyleSheet("""
            QTabWidget::pane { border: none; background: #0A0D12; }
            QTabBar::tab {
                background: #12161D; color: #8791A3; padding: 3px 12px;
                border: none; font-size: 10px; font-family: Consolas;
                border-right: 1px solid #1A1F29;
            }
            QTabBar::tab:selected {
                color: #C76B52; border-bottom: 2px solid #C76B52; background: #151A24;
            }
            QTabBar::tab:hover { color: #F2B39A; }
        """)

        self.news_feed = NewsFeedWidget()
        self.function_tabs.addTab(self.news_feed, "NEWS")

        self.equity_summary = EquitySummaryWidget()
        self.function_tabs.addTab(self.equity_summary, "DES")

        self.options_chain = OptionsChainWidget()
        self.function_tabs.addTab(self.options_chain, "OPTIONS")

        self.screener = ScreenerWidget()
        self.function_tabs.addTab(self.screener, "SCREENER")

        self.heatmap = HeatmapWidget()
        self.function_tabs.addTab(self.heatmap, "HEATMAP")

        self.economic_calendar = EconomicCalendarWidget()
        self.function_tabs.addTab(self.economic_calendar, "CALENDAR")

        self.alerts_widget = AlertsWidget()
        self.function_tabs.addTab(self.alerts_widget, "ALERTS")

        right_split.addWidget(self.function_tabs)
        right_split.setSizes([520, 280])
        main_split.addWidget(right_split)

        main_split.setSizes([320, 1100])

        self.center_stack = QStackedWidget()
        self.center_stack.addWidget(main_split)

        self.analysis_hub = AnalysisHubWidget(self.dm)
        self.center_stack.addWidget(self.analysis_hub)

        root_layout.addWidget(self.center_stack, 1)

        self.command_bar = CommandBar()
        root_layout.addWidget(self.command_bar)

        self.status_bar_widget = StatusBar()
        root_layout.addWidget(self.status_bar_widget)

    def _connect_signals(self):
        self.title_bar.close_requested.connect(self._confirm_close)
        self.title_bar.settings_changed.connect(self._on_settings)
        self.title_bar.analysis_toggled.connect(self._toggle_analysis)
        self.command_bar.command_issued.connect(self._handle_command)
        self.watchlist.symbol_selected.connect(self._on_symbol_selected)
        self.chart_widget.symbol_changed.connect(self._on_symbol_changed)
        self.equity_summary.symbol_changed.connect(self._on_symbol_changed)
        self.screener.symbol_selected.connect(self._on_symbol_selected)
        self.heatmap.stock_clicked.connect(self._on_symbol_selected)
        self.alerts_widget.alert_triggered.connect(self._on_alert_triggered)

    def _start_data(self):
        self.dm.start()
        self.chart_widget.load_chart("SPY", "3mo")

        self._poll_timer = QTimer()
        self._poll_timer.timeout.connect(self._poll_updates)
        self._poll_timer.start(500)

        self._clock_timer = QTimer()
        self._clock_timer.timeout.connect(self._update_clock)
        self._clock_timer.start(1000)

    def _poll_updates(self):
        import queue
        try:
            while True:
                kind, data = self.dm.update_queue.get_nowait()
                if kind == "prices":
                    self.market_overview.update_prices(self.dm.prices)
                    self.watchlist.update_prices(self.dm.prices)
                    sym = self.chart_widget.current_symbol
                    if sym in data:
                        self.chart_widget.update_price(sym, data[sym])
                    triggered = self.alerts_widget.check_prices(self.dm.prices)
                    self.heatmap.update_with_prices(self.dm.prices)
                    self.status_bar_widget.set_data_status(
                        f"DATA: Yahoo Finance  ·  Updated {datetime.now().strftime('%H:%M:%S')}"
                    )
                elif kind == "news":
                    self.news_feed.update_news(data)
        except queue.Empty:
            pass

    def _update_clock(self):
        now = datetime.now()
        self.title_bar.update_time(now.strftime("%H:%M:%S  %d/%m/%Y"))
        hour = now.hour
        weekday = now.weekday()
        is_open = weekday < 5 and 14 <= hour < 21  # NYSE hours in CET (UTC+1)
        self.title_bar.set_market_status(is_open)

    def _on_symbol_selected(self, symbol):
        self.chart_widget.load_chart(symbol, self.chart_widget.current_period)
        self.status_bar_widget.set_message(f"Loading: {symbol}", styles.COLOR_ACCENT)

    def _on_symbol_changed(self, symbol):
        self.status_bar_widget.set_message(
            f"Chart: {symbol}  ·  Double-click watchlist to switch", styles.COLOR_DIM
        )

    def _toggle_analysis(self):
        showing_analysis = self.center_stack.currentIndex() == 1
        self.center_stack.setCurrentIndex(0 if showing_analysis else 1)
        self.title_bar.set_analysis_mode(not showing_analysis)

    def _open_analysis_tool(self, command_key):
        self.center_stack.setCurrentIndex(1)
        self.title_bar.set_analysis_mode(True)
        self.analysis_hub.show_tool(command_key)

    def _on_alert_triggered(self, sym, msg):
        self.status_bar_widget.set_message(f"⚡ {msg}", styles.COLOR_POSITIVE)
        self.function_tabs.setCurrentIndex(TAB_ALERTS)

    @pyqtSlot(str, list)
    def _handle_command(self, cmd, args):
        if cmd in ("QUIT", "EXIT"):
            self._confirm_close()
            return

        if cmd == "HELP":
            self._show_help()
            return

        if cmd == "CHART":
            sym = args[0] if args else self.chart_widget.current_symbol
            period = args[1].lower() if len(args) > 1 else "3mo"
            self.chart_widget.load_chart(sym, period)
            self.status_bar_widget.set_message(f"Chart: {sym} [{period}]", styles.COLOR_ACCENT)
            return

        if cmd in ("EQ", "DES"):
            sym = args[0] if args else self.chart_widget.current_symbol
            self.equity_summary.load_symbol(sym)
            self.function_tabs.setCurrentIndex(TAB_DES)
            self.status_bar_widget.set_message(f"DES: {sym}", styles.COLOR_ACCENT)
            return

        if cmd in ("OMON", "OPTIONS", "OPT"):
            sym = args[0] if args else self.chart_widget.current_symbol
            price = self.dm.prices.get(sym, {}).get("price")
            self.options_chain.load_symbol(sym, price)
            self.function_tabs.setCurrentIndex(TAB_OPTIONS)
            self.status_bar_widget.set_message(f"Options: {sym}", styles.COLOR_ACCENT)
            return

        if cmd in ("EQS", "SCREENER", "SCREEN"):
            self.function_tabs.setCurrentIndex(TAB_SCREENER)
            self.screener.run_scan()
            self.status_bar_widget.set_message("Screener running...", styles.COLOR_ACCENT)
            return

        if cmd in ("HMAP", "HEATMAP", "MAP"):
            self.function_tabs.setCurrentIndex(TAB_HEATMAP)
            self.status_bar_widget.set_message("Sector Heatmap", styles.COLOR_ACCENT)
            return

        if cmd in ("ECO", "CALENDAR", "CAL"):
            self.function_tabs.setCurrentIndex(TAB_CALENDAR)
            self.status_bar_widget.set_message("Economic Calendar", styles.COLOR_ACCENT)
            return

        if cmd in ("ALRT", "ALERT", "ALERTS"):
            self.function_tabs.setCurrentIndex(TAB_ALERTS)
            if args and len(args) >= 2:
                sym = args[0]
                try:
                    price = float(args[1])
                    cond = args[2].lower() if len(args) > 2 else "above"
                    self.alerts_widget.add_alert_for_symbol(sym, price, cond)
                    self.status_bar_widget.set_message(f"Alert set: {sym} {cond} {price}", styles.COLOR_POSITIVE)
                except ValueError:
                    pass
            return

        if cmd == "NEWS":
            sym = args[0] if args else ""
            self.function_tabs.setCurrentIndex(TAB_NEWS)
            if sym:
                self.news_feed.load_symbol_news(sym)
                self.status_bar_widget.set_message(f"Loading {sym} news...", styles.COLOR_ACCENT)
            return

        if cmd == "WATCH":
            if args:
                self.dm.add_to_watchlist(args[0])
                self.status_bar_widget.set_message(f"Added: {args[0]}", styles.COLOR_POSITIVE)
            return

        if cmd == "REMOVE":
            if args:
                self.dm.remove_from_watchlist(args[0])
                self.watchlist.update_prices(self.dm.prices)
                self.status_bar_widget.set_message(f"Removed: {args[0]}", styles.COLOR_NEGATIVE)
            return

        if cmd in ("MKTOVW", "FX", "COMDTY", "CRYPTO"):
            tab_map = {"MKTOVW": 0, "INDICES": 0, "FX": 1, "COMDTY": 2, "CRYPTO": 3}
            idx = tab_map.get(cmd, 0)
            self.market_overview.tabs.setCurrentIndex(idx)
            self.status_bar_widget.set_message(f"Market: {cmd}", styles.COLOR_ACCENT)
            return

        if cmd == "PORT":
            self.watchlist.tabs.setCurrentIndex(1)
            return

        if cmd == "ANALYSIS":
            self.center_stack.setCurrentIndex(1)
            self.title_bar.set_analysis_mode(True)
            self.status_bar_widget.set_message("Analysis Workbench", styles.COLOR_ACCENT)
            return

        if cmd == "BACKTEST":
            self._open_analysis_tool("BACKTEST")
            self.status_bar_widget.set_message("Backtest Portfolio", styles.COLOR_ACCENT)
            return

        if cmd in ("OPTIMIZE", "EFRONTIER"):
            self._open_analysis_tool("OPTIMIZE")
            self.status_bar_widget.set_message("Efficient Frontier / Optimization", styles.COLOR_ACCENT)
            return

        if cmd in ("MONTECARLO", "MC"):
            self._open_analysis_tool("MONTECARLO")
            self.status_bar_widget.set_message("Monte Carlo Simulation", styles.COLOR_ACCENT)
            return

        if cmd == "FACTOR":
            self._open_analysis_tool("FACTOR")
            self.status_bar_widget.set_message("Factor Regression", styles.COLOR_ACCENT)
            return

        if cmd == "CORREL":
            self._open_analysis_tool("CORREL")
            self.status_bar_widget.set_message("Asset Correlations", styles.COLOR_ACCENT)
            return

        if cmd == "MOMENTUM":
            self._open_analysis_tool("MOMENTUM")
            self.status_bar_widget.set_message("Momentum Rotation", styles.COLOR_ACCENT)
            return

        if cmd in ("RISKPARITY", "ALLOC"):
            self._open_analysis_tool("RISKPARITY")
            self.status_bar_widget.set_message("Backtest Asset Allocation", styles.COLOR_ACCENT)
            return

        if cmd == "PCA":
            self._open_analysis_tool("PCA")
            self.status_bar_widget.set_message("Principal Component Analysis", styles.COLOR_ACCENT)
            return

        if cmd in ("BLACKLITTERMAN", "BL"):
            self._open_analysis_tool("BLACKLITTERMAN")
            self.status_bar_widget.set_message("Black-Litterman Model", styles.COLOR_ACCENT)
            return

        if cmd == "ROLLINGOPT":
            self._open_analysis_tool("ROLLINGOPT")
            self.status_bar_widget.set_message("Rolling Optimization", styles.COLOR_ACCENT)
            return

        if cmd == "DUALMOMENTUM":
            self._open_analysis_tool("DUALMOMENTUM")
            self.status_bar_widget.set_message("Dual Momentum", styles.COLOR_ACCENT)
            return

        if cmd == "TARGETVOL":
            self._open_analysis_tool("TARGETVOL")
            self.status_bar_widget.set_message("Target Volatility", styles.COLOR_ACCENT)
            return

        # Treat unknown single word as symbol lookup
        if len(cmd) <= 10 and (cmd.isalpha() or "-" in cmd or "." in cmd):
            self.chart_widget.load_chart(cmd, "3mo")
            self.status_bar_widget.set_message(f"Looking up: {cmd}", styles.COLOR_ACCENT)
            return

        self.status_bar_widget.set_message(
            f"Unknown command: {cmd}  ·  Type HELP", styles.COLOR_NEGATIVE
        )

    def _show_help(self):
        help_text = (
            "CHART <SYM> [period]   - Chart: CHART AAPL 6mo\n"
            "DES <SYM>              - Equity summary / fundamentals\n"
            "OPTIONS <SYM>          - Options chain (OMON)\n"
            "EQS                    - Equity screener (SCREENER)\n"
            "HMAP                   - Sector heatmap\n"
            "ECO                    - Economic calendar\n"
            "NEWS <SYM>             - Symbol-specific news\n"
            "ALRT <SYM> <price>     - Set price alert: ALRT TSLA 300\n"
            "WATCH <SYM>            - Add to watchlist\n"
            "REMOVE <SYM>           - Remove from watchlist\n"
            "MKTOVW / FX / COMDTY / CRYPTO\n"
            "PORT                   - Portfolio view\n"
            "\n- ANALYSIS WORKBENCH -\n"
            "ANALYSIS               - Open the analysis workbench\n"
            "BACKTEST               - Backtest a portfolio allocation\n"
            "OPTIMIZE / EFRONTIER   - Efficient frontier / optimization\n"
            "MONTECARLO / MC        - Monte Carlo simulation\n"
            "FACTOR                 - Fama-French / Carhart factor regression\n"
            "CORREL                 - Asset correlation matrix\n"
            "MOMENTUM               - Momentum rotation backtest\n"
            "RISKPARITY / ALLOC     - Backtest asset allocation (risk parity)\n"
            "PCA                    - Principal component analysis\n"
            "BLACKLITTERMAN / BL    - Black-Litterman model\n"
            "ROLLINGOPT             - Rolling optimization backtest\n"
            "DUALMOMENTUM           - Dual momentum backtest\n"
            "TARGETVOL              - Target volatility backtest\n"
            "F11                    - Toggle Analysis Workbench\n"
            "\nEXIT / QUIT / F12      - Close terminal\n"
            "\nTip: Just type a symbol (e.g. TSLA) to chart it directly"
        )
        msg = QMessageBox(self)
        msg.setWindowTitle("AMB COMMAND REFERENCE")
        msg.setText(help_text)
        msg.setStyleSheet(styles.TERMINAL_STYLE + "QLabel { font-size: 12px; }")
        msg.exec()

    def _on_settings(self, settings):
        action = settings.get("action")
        if action == "refresh":
            import threading
            threading.Thread(target=self.dm._fetch_prices, daemon=True).start()
            self.status_bar_widget.set_message("Refreshing data...", styles.COLOR_HIGHLIGHT)
        elif action == "about":
            QMessageBox.information(
                self, "About",
                "AMB Terminal v2.0 - free, local portfolio analysis for learning to invest\n\n"
                "Panels: Chart, DES, Options, Screener, Heatmap, Calendar, Alerts\n"
                "Analysis Workbench (12 tools): Backtest Portfolio, Backtest Asset Allocation,\n"
                "Efficient Frontier / Optimization, Black-Litterman, Rolling Optimization,\n"
                "Monte Carlo Simulation, Factor Regression, Principal Component Analysis,\n"
                "Asset Correlations, Momentum Rotation, Dual Momentum, Target Volatility\n"
                "(more Portfolio Visualizer-style tools coming soon - see the ANALYSIS panel)\n\n"
                "Educational tool, not investment advice. Runs locally, no account needed.\n"
                "Data: Yahoo Finance (~15min delayed), Ken French Data Library (factors)\n"
                "Built with Python 3 + PyQt6 + pyqtgraph + scipy\n\n"
                "Close: Settings ▼ → Close Terminal or F12"
            )

    def _confirm_close(self):
        msg = QMessageBox(self)
        msg.setWindowTitle("Close Terminal")
        msg.setText("Close the AMB Terminal?")
        msg.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        msg.setDefaultButton(QMessageBox.StandardButton.No)
        msg.setStyleSheet(styles.TERMINAL_STYLE + "QLabel { color: #C76B52; font-size: 13px; } QPushButton { min-width: 80px; }")
        if msg.exec() == QMessageBox.StandardButton.Yes:
            self.dm.stop()
            QApplication.quit()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_F12:
            self._confirm_close()
        elif event.key() == Qt.Key.Key_F1:
            self._show_help()
        elif event.key() == Qt.Key.Key_F2:
            self.command_bar.input.setText("CHART ")
            self.command_bar.set_focus()
        elif event.key() == Qt.Key.Key_F3:
            self.command_bar.input.setText("NEWS ")
            self.command_bar.set_focus()
        elif event.key() == Qt.Key.Key_F4:
            self.function_tabs.setCurrentIndex(TAB_HEATMAP)
        elif event.key() == Qt.Key.Key_F5:
            self._handle_command("DES", [self.chart_widget.current_symbol])
        elif event.key() == Qt.Key.Key_F6:
            self._handle_command("OPTIONS", [self.chart_widget.current_symbol])
        elif event.key() == Qt.Key.Key_F7:
            self._handle_command("EQS", [])
        elif event.key() == Qt.Key.Key_F8:
            self.command_bar.input.setText("WATCH ")
            self.command_bar.set_focus()
        elif event.key() == Qt.Key.Key_F9:
            self.function_tabs.setCurrentIndex(TAB_CALENDAR)
        elif event.key() == Qt.Key.Key_F10:
            self.function_tabs.setCurrentIndex(TAB_ALERTS)
        elif event.key() == Qt.Key.Key_F11:
            self._toggle_analysis()
        elif event.key() == Qt.Key.Key_Escape:
            self.command_bar.set_focus()
        elif not self.command_bar.input.hasFocus():
            if event.text() and event.text().isprintable():
                self.command_bar.set_focus()
                self.command_bar.input.setText(event.text().upper())
                self.command_bar.input.setCursorPosition(len(event.text()))
        else:
            super().keyPressEvent(event)
