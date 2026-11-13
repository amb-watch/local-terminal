from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QTextEdit, QSplitter, QPushButton, QLineEdit, QSizePolicy,
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread
from PyQt6.QtGui import QColor, QFont, QDesktopServices
from PyQt6.QtCore import QUrl
from datetime import datetime
import styles
from data_manager import parse_feed_time


class _SymbolNewsWorker(QThread):
    done = pyqtSignal(list, str)

    def __init__(self, symbol):
        super().__init__()
        self.symbol = symbol

    def run(self):
        import yfinance as yf
        import feedparser
        from urllib.parse import quote

        items = []
        seen_titles = set()

        try:
            t = yf.Ticker(self.symbol)
            raw = t.news or []
            for n in raw:
                # yfinance nests article fields under "content" (id, title, pubDate,
                # provider, canonicalUrl); fall back to flat keys for older versions.
                content = n.get("content") or n
                title = content.get("title", "") or n.get("title", "")
                if title and title.lower() not in seen_titles:
                    seen_titles.add(title.lower())

                    published, published_ts = "", 0.0
                    pub_date = content.get("pubDate") or content.get("displayTime")
                    if pub_date:
                        try:
                            dt_utc = datetime.fromisoformat(pub_date.replace("Z", "+00:00"))
                            dt_local = dt_utc.astimezone()
                            published = dt_local.strftime("%d %b  %H:%M")
                            published_ts = dt_local.timestamp()
                        except (ValueError, TypeError):
                            pass

                    provider = content.get("provider") or {}
                    publisher = provider.get("displayName") or n.get("publisher", "Yahoo")
                    link_obj = content.get("canonicalUrl") or content.get("clickThroughUrl") or {}
                    link = link_obj.get("url", "") or n.get("link", "")
                    summary = content.get("summary", "") or n.get("summary", "")

                    items.append({
                        "source": publisher,
                        "title": title,
                        "summary": summary,
                        "link": link,
                        "published": published,
                        "published_ts": published_ts,
                        "symbol": self.symbol,
                    })
        except Exception:
            pass

        try:
            query = quote(f"{self.symbol} stock")
            url = f"https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"
            feed = feedparser.parse(url)
            for entry in feed.entries[:15]:
                title = entry.get("title", "")
                if title and title.lower() not in seen_titles:
                    seen_titles.add(title.lower())
                    published, published_ts = parse_feed_time(entry)
                    items.append({
                        "source": "Google News",
                        "title": title,
                        "summary": entry.get("summary", "")[:200],
                        "link": entry.get("link", ""),
                        "published": published,
                        "published_ts": published_ts,
                        "symbol": self.symbol,
                    })
        except Exception:
            pass

        items.sort(key=lambda x: x.get("published_ts", 0), reverse=True)
        self.done.emit(items, self.symbol)


class NewsFeedWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._items = []
        self._filtered = []
        self._current_row = 0
        self._auto_scroll = True
        self._sym_worker = None
        self._build_ui()

        self._ticker_timer = QTimer()
        self._ticker_timer.timeout.connect(self._scroll_ticker)
        self._ticker_timer.start(80)

        self._highlight_timer = QTimer()
        self._highlight_timer.timeout.connect(self._cycle_highlight)
        self._highlight_timer.start(5000)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header_w = QWidget()
        header_w.setStyleSheet(f"background-color: #151A24; border-bottom: 1px solid {styles.COLOR_BORDER};")
        hl = QHBoxLayout(header_w)
        hl.setContentsMargins(6, 2, 6, 2)
        hl.setSpacing(8)

        lbl = QLabel("  NEWS FEED")
        lbl.setStyleSheet(f"color: {styles.COLOR_ACCENT}; font-size: 11px; font-weight: bold; border: none;")
        hl.addWidget(lbl)

        self.ticker_label = QLabel("  Loading news...")
        self.ticker_label.setStyleSheet(f"color: {styles.COLOR_HIGHLIGHT}; font-size: 11px; border: none;")
        # The marquee text is wider than the bar by design; don't let it drive the
        # layout's size (otherwise the label keeps growing with its own text).
        self.ticker_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.ticker_label.setMinimumWidth(0)
        hl.addWidget(self.ticker_label, 1)

        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText("Filter news...")
        self.filter_input.setFixedWidth(120)
        self.filter_input.setStyleSheet(
            "color: #FFFFFF; background: #0A0D12; border: 1px solid #2E3542; padding: 1px 4px; font-size: 10px;"
        )
        self.filter_input.textChanged.connect(self._apply_filter)
        hl.addWidget(self.filter_input)

        self.refreshed_label = QLabel("")
        self.refreshed_label.setStyleSheet(f"color: {styles.COLOR_DIM}; font-size: 10px; border: none;")
        hl.addWidget(self.refreshed_label)

        layout.addWidget(header_w)

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setStyleSheet("QSplitter::handle { background: #1F2530; height: 2px; }")

        self.news_table = QTableWidget()
        self.news_table.setColumnCount(3)
        self.news_table.setHorizontalHeaderLabels(["TIME", "SOURCE", "HEADLINE"])
        self.news_table.verticalHeader().setVisible(False)
        self.news_table.setShowGrid(False)
        self.news_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.news_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.news_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.news_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self.news_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.news_table.setColumnWidth(0, 90)
        self.news_table.setColumnWidth(1, 100)
        self.news_table.setAlternatingRowColors(False)
        self.news_table.verticalHeader().setDefaultSectionSize(20)
        self.news_table.horizontalHeader().setFixedHeight(22)
        self.news_table.setStyleSheet("""
            QTableWidget { background: #0A0D12; color: #D7DCE5; gridline-color: #1A1F29; border: none; font-size: 11px; font-family: Consolas; }
            QTableWidget::item { padding: 1px 4px; border-bottom: 1px solid #1A1F29; }
            QTableWidget::item:selected { background: #1B212C; color: #FFFFFF; }
            QHeaderView::section { background: #151A24; color: #C76B52; border: none; border-bottom: 1px solid #242A36; padding: 3px 4px; font-size: 10px; font-family: Consolas; }
        """)
        self.news_table.currentItemChanged.connect(lambda cur, prev: self._show_detail(self.news_table.currentRow()))
        self.news_table.doubleClicked.connect(self._open_link)
        splitter.addWidget(self.news_table)

        detail_w = QWidget()
        detail_w.setStyleSheet("background: #12161D;")
        dv = QVBoxLayout(detail_w)
        dv.setContentsMargins(6, 6, 6, 6)
        dv.setSpacing(4)

        self.detail_source = QLabel("")
        self.detail_source.setStyleSheet(f"color: {styles.COLOR_DIM}; font-size: 10px; border: none;")
        dv.addWidget(self.detail_source)

        self.detail_title = QLabel("")
        self.detail_title.setStyleSheet(f"color: {styles.COLOR_HIGHLIGHT}; font-size: 12px; font-weight: bold; border: none;")
        self.detail_title.setWordWrap(True)
        dv.addWidget(self.detail_title)

        self.detail_body = QTextEdit()
        self.detail_body.setReadOnly(True)
        self.detail_body.setStyleSheet("""
            QTextEdit { background: #12161D; color: #D7DCE5; border: none; font-family: 'Segoe UI'; font-size: 11px; }
        """)
        dv.addWidget(self.detail_body)

        open_btn = QPushButton("Open in Browser →")
        open_btn.setStyleSheet("""
            QPushButton { background: #151A24; color: #C76B52; border: 1px solid #2E3542; padding: 3px 12px; font-size: 10px; font-family: 'Segoe UI'; }
            QPushButton:hover { background: #1B212C; border-color: #C76B52; }
        """)
        open_btn.clicked.connect(self._open_current_link)
        dv.addWidget(open_btn)

        splitter.addWidget(detail_w)
        splitter.setSizes([300, 120])
        layout.addWidget(splitter)

        self._ticker_pos = 0
        self._ticker_text = "  Loading market news...  "

    def update_news(self, items):
        self._items = items
        self._apply_filter()
        self._build_ticker()
        self.refreshed_label.setText(f"Updated {datetime.now().strftime('%H:%M:%S')}")

    def _apply_filter(self):
        query = self.filter_input.text().lower()
        if query:
            self._filtered = [x for x in self._items if query in x["title"].lower() or query in x["source"].lower()]
        else:
            self._filtered = list(self._items)
        self._populate_table()

    def _populate_table(self):
        items = self._filtered
        self.news_table.setRowCount(len(items))
        for row, item in enumerate(items):
            time_str = item.get("published", "") or "-"
            t = QTableWidgetItem(time_str)
            t.setForeground(QColor(styles.COLOR_DIM))
            t.setFont(QFont(styles.DATA_FONT_FAMILY, 9))
            self.news_table.setItem(row, 0, t)

            src = QTableWidgetItem(item["source"][:14])
            src.setForeground(QColor(styles.COLOR_ACCENT))
            src.setFont(QFont(styles.DATA_FONT_FAMILY, 9))
            self.news_table.setItem(row, 1, src)

            headline = QTableWidgetItem(item["title"])
            headline.setForeground(QColor(styles.COLOR_WHITE))
            headline.setFont(QFont(styles.UI_FONT_FAMILY, 10))
            self.news_table.setItem(row, 2, headline)

    def _show_detail(self, row):
        if 0 <= row < len(self._filtered):
            item = self._filtered[row]
            self.detail_source.setText(f"{item['source']}  ·  {item.get('published', '')}")
            self.detail_title.setText(item["title"])
            self.detail_body.setPlainText(item.get("summary", ""))
            self._current_row = row

    def _open_link(self, index):
        row = index.row()
        if 0 <= row < len(self._filtered):
            link = self._filtered[row].get("link", "")
            if link:
                QDesktopServices.openUrl(QUrl(link))

    def _open_current_link(self):
        if 0 <= self._current_row < len(self._filtered):
            link = self._filtered[self._current_row].get("link", "")
            if link:
                QDesktopServices.openUrl(QUrl(link))

    def _build_ticker(self):
        parts = []
        for item in self._items[:15]:
            parts.append(f"  ◆ {item['title']}")
        self._ticker_text = "    ".join(parts) + "    " if parts else "  Waiting for news..."
        self._ticker_pos = 0

    def _scroll_ticker(self):
        if not self._ticker_text:
            return
        text = self._ticker_text
        n = len(text)
        pos = self._ticker_pos % n

        # Fill the whole label width regardless of screen size - figure out how
        # many characters that takes from the live font metrics instead of a
        # fixed character count (which left the bar blank on wide monitors).
        fm = self.ticker_label.fontMetrics()
        char_w = max(fm.horizontalAdvance("M"), 6)
        target_w = max(self.ticker_label.width(), 400)
        needed = int(target_w / char_w) + 30
        repeats = (needed // n) + 2
        display = (text * repeats)[pos:pos + needed]

        self.ticker_label.setText(display)
        self._ticker_pos += 1

    def _cycle_highlight(self):
        if self._filtered and self._auto_scroll:
            next_row = (self.news_table.currentRow() + 1) % min(len(self._filtered), 5)
            self.news_table.setCurrentCell(next_row, 0)

    def load_symbol_news(self, symbol):
        symbol = symbol.upper().strip()
        if not symbol:
            return
        self.filter_input.setText("")
        self.ticker_label.setText(f"  Loading {symbol} news...")
        if self._sym_worker and self._sym_worker.isRunning():
            self._sym_worker.quit()
        self._sym_worker = _SymbolNewsWorker(symbol)
        self._sym_worker.done.connect(self._on_symbol_news)
        self._sym_worker.start()

    def _on_symbol_news(self, items, symbol):
        if items:
            self._items = sorted(items + self._items, key=lambda x: x.get("published_ts", 0), reverse=True)
            self._filtered = items
            self._populate_table()
            self._build_ticker()
            self.refreshed_label.setText(f"Updated {datetime.now().strftime('%H:%M:%S')}")
        else:
            self.filter_input.setText(symbol)
            self._apply_filter()
