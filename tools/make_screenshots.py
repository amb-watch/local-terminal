"""Generates the README screenshots by driving the real app and grabbing its widgets.

    python tools/make_screenshots.py

The window is created far outside the visible desktop, so nothing flashes on your screen.
Needs internet (it fetches live market data) and takes a few minutes. Output: docs/screenshots/*.png
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
OUT = os.path.join(ROOT, "docs", "screenshots")
os.makedirs(OUT, exist_ok=True)

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QApplication
import styles

app = QApplication(sys.argv)
app.setStyleSheet(styles.TERMINAL_STYLE)

import main as amb_main
from main_window import AMBTerminal

splash_holder = {}


class _CaptureSplash:
    def __init__(self, screen, pixmap, flags):
        pixmap.save(os.path.join(OUT, "splash.png"))

    def move(self, *a): pass
    def show(self): pass


amb_main.QSplashScreen = _CaptureSplash
amb_main.create_splash(app.primaryScreen())

AMBTerminal.showFullScreen = lambda self: None  # don't take over the monitor
win = AMBTerminal()
win.move(-6000, -6000)          # keep it off the visible desktop
win.resize(1920, 1080)
win.show()

# (command key, run-method name, file name, pre-hook)
TOOLS = [
    ("BACKTEST", "run_backtest", "backtest-portfolio"),
    ("RISKPARITY", "run_backtest", "risk-parity"),
    ("OPTIMIZE", "run_optimization", "efficient-frontier"),
    ("BLACKLITTERMAN", "run_solve", "black-litterman"),
    ("ROLLINGOPT", "run_backtest", "rolling-optimization"),
    ("MONTECARLO", "run_simulation", "monte-carlo"),
    ("FACTOR", "run_regression", "factor-regression"),
    ("PCA", "run_analysis", "pca"),
    ("CORREL", "run_analysis", "correlations"),
    ("MOMENTUM", "run_backtest", "momentum-rotation"),
    ("DUALMOMENTUM", "run_backtest", "dual-momentum"),
    ("TARGETVOL", "run_backtest", "target-volatility"),
]


def grab(widget, name):
    path = os.path.join(OUT, name + ".png")
    widget.grab().save(path)
    print("saved", path, flush=True)


def run_tools(i=0):
    if i >= len(TOOLS):
        print("done", flush=True)
        app.quit()
        return
    key, method, name = TOOLS[i]
    hub = win.analysis_hub
    hub.show_tool(key)
    widget = hub.stack.currentWidget()
    if key == "BLACKLITTERMAN":
        widget.views_input.setText("QQQ:15,TLT:2")
    if key == "BACKTEST":
        widget._use_my_portfolio()
    getattr(widget, method)()
    waited = {"t": 0}

    def poll():
        waited["t"] += 1
        # run_btn is re-enabled when the worker has delivered its result
        if widget.run_btn.isEnabled() or waited["t"] > 90:
            QTimer.singleShot(800, lambda: (grab(hub, name), run_tools(i + 1)))
        else:
            QTimer.singleShot(1000, poll)

    QTimer.singleShot(1500, poll)


def stage_terminal_shots():
    grab(win, "terminal-line")
    win.chart_widget._set_chart_type("candles")
    QTimer.singleShot(1500, lambda: (grab(win.chart_widget, "chart-candles"), stage_portfolio()))


def stage_portfolio():
    win.chart_widget._set_chart_type("line")
    for sym, qty, avg in (("AAPL", 40, 190.0), ("MSFT", 25, 400.0), ("SPY", 30, 500.0)):
        win.dm.add_position(sym, qty, avg)
    win.watchlist.update_prices(win.dm.prices)
    win.watchlist.tabs.setCurrentIndex(1)
    QTimer.singleShot(1000, lambda: (grab(win.watchlist, "portfolio"), stage_analysis()))


def stage_analysis():
    win.center_stack.setCurrentIndex(1)
    QTimer.singleShot(800, run_tools)


# give the price/news/chart threads time to load before the first shot
QTimer.singleShot(25000, stage_terminal_shots)
sys.exit(app.exec())
