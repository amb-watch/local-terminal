from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QStackedWidget, QPushButton,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QColor
import styles

from widgets.analysis.backtest_portfolio import BacktestPortfolioWidget
from widgets.analysis.backtest_asset_allocation import BacktestAssetAllocationWidget
from widgets.analysis.portfolio_optimization import PortfolioOptimizationWidget
from widgets.analysis.black_litterman import BlackLittermanWidget
from widgets.analysis.rolling_optimization import RollingOptimizationWidget
from widgets.analysis.monte_carlo import MonteCarloWidget
from widgets.analysis.factor_regression import FactorRegressionWidget
from widgets.analysis.pca_analysis import PCAAnalysisWidget
from widgets.analysis.asset_correlations import AssetCorrelationsWidget
from widgets.analysis.tactical_momentum import TacticalMomentumWidget
from widgets.analysis.dual_momentum import DualMomentumWidget
from widgets.analysis.target_volatility import TargetVolatilityWidget

# (category, [(display name, widget_class_or_None, command_key)])
CATEGORIES = [
    ("BACKTESTING", [
        ("Backtest Portfolio", BacktestPortfolioWidget, "BACKTEST"),
        ("Backtest Asset Allocation", BacktestAssetAllocationWidget, "RISKPARITY"),
        ("Backtest Dynamic Allocation", None, None),
        ("Manager Performance Analysis", None, None),
    ]),
    ("FACTOR ANALYSIS", [
        ("Factor Regression", FactorRegressionWidget, "FACTOR"),
        ("Risk Factor Allocation", None, None),
        ("Match Factor Exposures", None, None),
        ("Principal Component Analysis", PCAAnalysisWidget, "PCA"),
        ("Factor Statistics", None, None),
        ("Fund Factor Regressions", None, None),
        ("Fund Performance Attribution", None, None),
    ]),
    ("ASSET ANALYTICS", [
        ("Asset Correlations", AssetCorrelationsWidget, "CORREL"),
        ("Fund Screener", None, None),
        ("Fund Rankings", None, None),
        ("Fund Performance", None, None),
        ("Asset Autocorrelation", None, None),
        ("Asset Cointegration", None, None),
    ]),
    ("MONTE CARLO SIMULATION", [
        ("Monte Carlo Simulation", MonteCarloWidget, "MONTECARLO"),
        ("Financial Goals", None, None),
        ("Asset Liability Modeling", None, None),
    ]),
    ("PORTFOLIO OPTIMIZATION", [
        ("Efficient Frontier / Optimization", PortfolioOptimizationWidget, "OPTIMIZE"),
        ("Black-Litterman Model", BlackLittermanWidget, "BLACKLITTERMAN"),
        ("Rolling Optimization", RollingOptimizationWidget, "ROLLINGOPT"),
    ]),
    ("TACTICAL ASSET ALLOCATION", [
        ("Momentum Rotation", TacticalMomentumWidget, "MOMENTUM"),
        ("Market Valuation", None, None),
        ("Moving Averages", None, None),
        ("Dual Momentum", DualMomentumWidget, "DUALMOMENTUM"),
        ("Adaptive Allocation", None, None),
        ("Target Volatility", TargetVolatilityWidget, "TARGETVOL"),
    ]),
]

HEADER_ROLE = Qt.ItemDataRole.UserRole
STACK_INDEX_ROLE = Qt.ItemDataRole.UserRole + 1


class AnalysisHubWidget(QWidget):
    back_requested = pyqtSignal()

    def __init__(self, data_manager=None, parent=None):
        super().__init__(parent)
        self.dm = data_manager
        self._command_to_index = {}
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QWidget()
        header.setStyleSheet(f"background: #151A24; border-bottom: 1px solid {styles.COLOR_BORDER};")
        hl = QHBoxLayout(header)
        hl.setContentsMargins(10, 6, 10, 6)

        title = QLabel("ANALYSIS WORKBENCH")
        title.setStyleSheet(f"color: {styles.COLOR_HIGHLIGHT}; font-size: 14px; font-weight: bold; border: none;")
        hl.addWidget(title)

        sub = QLabel("  Backtest allocations, run factor & correlation analysis, optimize, and stress-test with real market data.")
        sub.setStyleSheet(f"color: {styles.COLOR_DIM}; font-size: 10px; border: none;")
        hl.addWidget(sub)
        hl.addStretch()

        layout.addWidget(header)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        self.nav_list = QListWidget()
        self.nav_list.setFixedWidth(260)
        self.nav_list.setStyleSheet("""
            QListWidget { background: #12161D; border: none; border-right: 1px solid #1F2530; font-family: 'Segoe UI'; }
            QListWidget::item { padding: 5px 10px; }
            QListWidget::item:selected { background: #1B212C; color: #F2B39A; }
        """)
        self.nav_list.itemClicked.connect(self._on_item_clicked)

        self.stack = QStackedWidget()

        for category, tools in CATEGORIES:
            header_item = QListWidgetItem(f"▸ {category}")
            header_item.setFont(QFont(styles.UI_FONT_FAMILY, 10, QFont.Weight.DemiBold))
            header_item.setForeground(QColor(styles.COLOR_ACCENT))
            header_item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.nav_list.addItem(header_item)

            for name, widget_cls, cmd_key in tools:
                item = QListWidgetItem(f"    {name}")
                item.setFont(QFont(styles.UI_FONT_FAMILY, 10))
                if widget_cls is not None:
                    widget = widget_cls(data_manager=self.dm)
                    idx = self.stack.addWidget(widget)
                    item.setData(STACK_INDEX_ROLE, idx)
                    item.setForeground(QColor(styles.COLOR_WHITE))
                    if cmd_key:
                        self._command_to_index[cmd_key] = idx
                else:
                    item.setText(f"    {name}  · coming soon")
                    item.setForeground(QColor("#2E3542"))
                    item.setFlags(Qt.ItemFlag.NoItemFlags)
                self.nav_list.addItem(item)

        body.addWidget(self.nav_list)
        body.addWidget(self.stack, 1)

        body_widget = QWidget()
        body_widget.setLayout(body)
        layout.addWidget(body_widget, 1)

        if self.stack.count() > 0:
            self.stack.setCurrentIndex(0)

    def _on_item_clicked(self, item):
        idx = item.data(STACK_INDEX_ROLE)
        if idx is not None:
            self.stack.setCurrentIndex(idx)

    def show_tool(self, command_key):
        idx = self._command_to_index.get(command_key)
        if idx is not None:
            self.stack.setCurrentIndex(idx)
            return True
        return False
