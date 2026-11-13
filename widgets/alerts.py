from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QLineEdit, QDoubleSpinBox, QComboBox, QPushButton,
    QDialog, QFormLayout, QDialogButtonBox,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont
from datetime import datetime
import styles


class AlertDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("NEW PRICE ALERT")
        self.setModal(True)
        self.setStyleSheet(styles.TERMINAL_STYLE)
        layout = QFormLayout(self)
        layout.setSpacing(10)

        self.sym_input = QLineEdit()
        self.sym_input.setPlaceholderText("e.g. AAPL, BTC-USD")
        self.sym_input.setStyleSheet("color: #FFFFFF; background: #171C25; border: 1px solid #2E3542; padding: 2px 6px;")
        layout.addRow("Symbol:", self.sym_input)

        self.cond_combo = QComboBox()
        self.cond_combo.addItems(["Price ABOVE", "Price BELOW", "Change % ABOVE", "Change % BELOW"])
        self.cond_combo.setStyleSheet("color: #C76B52; background: #171C25; border: 1px solid #2E3542;")
        layout.addRow("Condition:", self.cond_combo)

        self.value_spin = QDoubleSpinBox()
        self.value_spin.setRange(-1000000, 10000000)
        self.value_spin.setDecimals(2)
        self.value_spin.setValue(100.0)
        self.value_spin.setStyleSheet("color: #FFFFFF; background: #171C25; border: 1px solid #2E3542;")
        layout.addRow("Value:", self.value_spin)

        self.note_input = QLineEdit()
        self.note_input.setPlaceholderText("Optional note")
        self.note_input.setStyleSheet("color: #D7DCE5; background: #171C25; border: 1px solid #2E3542;")
        layout.addRow("Note:", self.note_input)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        buttons.setStyleSheet("""
            QPushButton { background: #171C25; color: #C76B52; border: 1px solid #2E3542; padding: 4px 16px; }
            QPushButton:hover { background: #1B212C; }
        """)
        layout.addRow(buttons)


class AlertsWidget(QWidget):
    alert_triggered = pyqtSignal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._alerts = []
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header_w = QWidget()
        header_w.setStyleSheet(f"background: #151A24; border-bottom: 1px solid {styles.COLOR_BORDER};")
        hl = QHBoxLayout(header_w)
        hl.setContentsMargins(8, 3, 8, 3)
        hl.setSpacing(8)

        lbl = QLabel("ALRT  ·  PRICE ALERTS")
        lbl.setStyleSheet(f"color: {styles.COLOR_HIGHLIGHT}; font-size: 12px; font-weight: bold; border: none; ")
        hl.addWidget(lbl)
        hl.addStretch()

        quick_sym = QLineEdit()
        quick_sym.setPlaceholderText("Symbol")
        quick_sym.setFixedWidth(70)
        quick_sym.setStyleSheet("color: #FFFFFF; background: #171C25; border: 1px solid #2E3542; padding: 1px 4px; font-size: 10px;")
        hl.addWidget(quick_sym)
        self._quick_sym = quick_sym

        quick_price = QDoubleSpinBox()
        quick_price.setRange(0, 10000000)
        quick_price.setDecimals(2)
        quick_price.setFixedWidth(90)
        quick_price.setStyleSheet("color: #FFFFFF; background: #171C25; border: 1px solid #2E3542; font-size: 10px; font-family: Consolas;")
        hl.addWidget(quick_price)
        self._quick_price = quick_price

        self._quick_cond = QComboBox()
        self._quick_cond.addItems(["ABOVE", "BELOW"])
        self._quick_cond.setFixedWidth(70)
        self._quick_cond.setStyleSheet("""
            QComboBox { background: #171C25; color: #FFFFFF; border: 1px solid #2E3542; padding: 1px 2px; font-size: 10px; font-family: Consolas; }
            QComboBox QAbstractItemView { background: #151A24; color: #C76B52; }
        """)
        hl.addWidget(self._quick_cond)

        add_btn = QPushButton("+ ADD")
        add_btn.setStyleSheet("""
            QPushButton { background: #171C25; color: #FFFFFF; border: 1px solid #C76B52; padding: 2px 8px; font-size: 10px; font-family: 'Segoe UI'; }
            QPushButton:hover { background: #1B212C; border-color: #F2B39A; color: #F2B39A; }
        """)
        add_btn.clicked.connect(self._add_quick)
        hl.addWidget(add_btn)

        adv_btn = QPushButton("Advanced")
        adv_btn.setStyleSheet("""
            QPushButton { background: #171C25; color: #8791A3; border: 1px solid #242A36; padding: 2px 8px; font-size: 10px; font-family: 'Segoe UI'; }
            QPushButton:hover { color: #C76B52; border-color: #C76B52; }
        """)
        adv_btn.clicked.connect(self._open_advanced)
        hl.addWidget(adv_btn)

        layout.addWidget(header_w)

        self.alerts_table = QTableWidget()
        self.alerts_table.setColumnCount(6)
        self.alerts_table.setHorizontalHeaderLabels(["SYMBOL", "CONDITION", "TARGET", "CURRENT", "STATUS", "NOTE"])
        self.alerts_table.verticalHeader().setVisible(False)
        self.alerts_table.setShowGrid(True)
        self.alerts_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.alerts_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        hdr = self.alerts_table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.alerts_table.setColumnWidth(0, 70)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self.alerts_table.setColumnWidth(1, 100)
        for i in range(2, 6):
            hdr.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)
        self.alerts_table.verticalHeader().setDefaultSectionSize(22)
        self.alerts_table.horizontalHeader().setFixedHeight(22)
        self.alerts_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.alerts_table.customContextMenuRequested.connect(self._context_menu)
        layout.addWidget(self.alerts_table)

        self.triggered_label = QLabel("  No alerts triggered")
        self.triggered_label.setStyleSheet(f"background: #12161D; color: {styles.COLOR_DIM}; font-size: 10px; padding: 2px 8px; border-top: 1px solid #1F2530;")
        layout.addWidget(self.triggered_label)

    def _add_quick(self):
        sym = self._quick_sym.text().upper().strip()
        if not sym:
            return
        cond_str = self._quick_cond.currentText()
        target = self._quick_price.value()
        cond = "above" if cond_str == "ABOVE" else "below"
        self._add_alert(sym, cond, target, "")
        self._quick_sym.clear()

    def _open_advanced(self):
        dlg = AlertDialog(self)
        if dlg.exec():
            sym = dlg.sym_input.text().upper().strip()
            cond_text = dlg.cond_combo.currentText()
            value = dlg.value_spin.value()
            note = dlg.note_input.text()
            cond_map = {
                "Price ABOVE": "above", "Price BELOW": "below",
                "Change % ABOVE": "pct_above", "Change % BELOW": "pct_below",
            }
            cond = cond_map.get(cond_text, "above")
            if sym:
                self._add_alert(sym, cond, value, note)

    def _add_alert(self, symbol, condition, target, note):
        alert = {
            "id": len(self._alerts),
            "symbol": symbol,
            "condition": condition,
            "target": target,
            "note": note,
            "status": "ACTIVE",
            "current": None,
        }
        self._alerts.append(alert)
        self._refresh_table()

    def _refresh_table(self):
        self.alerts_table.setRowCount(len(self._alerts))
        for row, a in enumerate(self._alerts):
            status_colors = {"ACTIVE": styles.COLOR_ACCENT, "TRIGGERED": styles.COLOR_POSITIVE, "EXPIRED": styles.COLOR_DIM}
            cond_labels = {
                "above": "Price > ", "below": "Price < ",
                "pct_above": "Chg% > ", "pct_below": "Chg% < ",
            }
            cond_str = cond_labels.get(a["condition"], "") + f"{a['target']:,.2f}"
            if "pct" in a["condition"]:
                cond_str += "%"

            current_str = f"{a['current']:,.2f}" if a["current"] else "---"
            items = [
                (a["symbol"], styles.COLOR_ACCENT),
                (cond_str, styles.COLOR_WHITE),
                (f"{a['target']:,.2f}", styles.COLOR_HIGHLIGHT),
                (current_str, styles.COLOR_WHITE),
                (a["status"], status_colors.get(a["status"], styles.COLOR_DIM)),
                (a.get("note", ""), styles.COLOR_DIM),
            ]
            for col, (txt, color) in enumerate(items):
                item = QTableWidgetItem(txt)
                item.setForeground(QColor(color))
                item.setFont(QFont("Consolas", 10))
                if col in (2, 3):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.alerts_table.setItem(row, col, item)

    def _context_menu(self, pos):
        from PyQt6.QtWidgets import QMenu
        row = self.alerts_table.rowAt(pos.y())
        if row < 0:
            return
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu { background: #151A24; color: #C76B52; border: 1px solid #C76B52; font-family: Consolas; }
            QMenu::item { padding: 5px 16px; }
            QMenu::item:selected { background: #1B212C; }
        """)
        menu.addAction("Delete Alert", lambda: self._delete_alert(row))
        menu.exec(self.alerts_table.viewport().mapToGlobal(pos))

    def _delete_alert(self, row):
        if 0 <= row < len(self._alerts):
            self._alerts.pop(row)
            self._refresh_table()

    def add_alert_for_symbol(self, symbol, target_price, condition="above"):
        self._add_alert(symbol, condition, target_price, "")

    def check_prices(self, prices):
        triggered = []
        for a in self._alerts:
            if a["status"] != "ACTIVE":
                continue
            sym = a["symbol"]
            data = prices.get(sym)
            if not data:
                continue

            price = data.get("price")
            pct = data.get("pct", 0)
            a["current"] = price

            cond = a["condition"]
            target = a["target"]
            fired = False

            if cond == "above" and price and price >= target:
                fired = True
            elif cond == "below" and price and price <= target:
                fired = True
            elif cond == "pct_above" and pct >= target:
                fired = True
            elif cond == "pct_below" and pct <= target:
                fired = True

            if fired:
                a["status"] = "TRIGGERED"
                msg = f"ALERT: {sym} {cond.upper()} {target:.2f} (current: {price:.2f})"
                triggered.append((sym, msg))
                self.alert_triggered.emit(sym, msg)

        if triggered:
            self.triggered_label.setText(f"  ● {triggered[-1][1]}")
            self.triggered_label.setStyleSheet(
                f"background: #151A24; color: {styles.COLOR_POSITIVE}; font-size: 10px; "
                f"font-weight: bold; padding: 2px 8px; border-top: 1px solid #1F2530;"
            )

        self._refresh_table()
        return triggered
