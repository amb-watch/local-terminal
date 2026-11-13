import threading
import time
import queue
import calendar
import yfinance as yf
import pandas as pd
import feedparser
from datetime import datetime, timezone

# yfinance's download session is not safe under concurrent calls from multiple
# threads (the terminal's price loop, the screener, the heatmap, and every
# Analysis Workbench tool all fetch independently) - without this lock, two
# simultaneous yf.download() calls can occasionally cross-contaminate and
# return the wrong tickers' data to the wrong caller. Every yf.download call
# site in the app should acquire this before calling.
YFINANCE_LOCK = threading.Lock()


DEFAULT_WATCHLIST = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA",
    "META", "TSLA", "BRK-B", "JPM", "V",
    "SPY", "QQQ", "BTC-USD", "ETH-USD",
    "EURUSD=X", "GC=F", "CL=F",
]

MARKET_SYMBOLS = {
    "Indices": [
        ("S&P 500", "^GSPC"),
        ("NASDAQ", "^IXIC"),
        ("DOW", "^DJI"),
        ("WIG20", "WIG20.WA"),
        ("DAX", "^GDAXI"),
        ("FTSE100", "^FTSE"),
        ("Nikkei", "^N225"),
    ],
    "Forex": [
        ("EUR/USD", "EURUSD=X"),
        ("USD/PLN", "PLN=X"),
        ("GBP/USD", "GBPUSD=X"),
        ("USD/JPY", "JPY=X"),
        ("USD/CHF", "CHF=X"),
    ],
    "Commodities": [
        ("Gold", "GC=F"),
        ("Silver", "SI=F"),
        ("Oil WTI", "CL=F"),
        ("Brent", "BZ=F"),
        ("Natural Gas", "NG=F"),
    ],
    "Crypto": [
        ("Bitcoin", "BTC-USD"),
        ("Ethereum", "ETH-USD"),
        ("BNB", "BNB-USD"),
        ("Solana", "SOL-USD"),
    ],
}

def parse_feed_time(entry):
    """Return (display_string, sort_timestamp) for an RSS entry's publish time,
    converted from UTC to local time. Falls back to (\"\", 0) if unparseable."""
    parsed = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
    if not parsed:
        return "", 0.0
    try:
        dt_utc = datetime.fromtimestamp(calendar.timegm(parsed), tz=timezone.utc)
        dt_local = dt_utc.astimezone()
        return dt_local.strftime("%d %b  %H:%M"), dt_local.timestamp()
    except Exception:
        return "", 0.0


NEWS_FEEDS = [
    ("Reuters Business", "https://feeds.reuters.com/reuters/businessNews"),
    ("Reuters Markets", "https://feeds.reuters.com/reuters/companyNews"),
    ("Yahoo Finance", "https://finance.yahoo.com/news/rss"),
    ("Investing.com", "https://www.investing.com/rss/news.rss"),
    ("MarketWatch", "https://feeds.marketwatch.com/marketwatch/topstories"),
    ("CNBC Markets", "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=15839069"),
    ("SeekingAlpha", "https://seekingalpha.com/market_currents.xml"),
    ("Google News - Business", "https://news.google.com/rss/headlines/section/topic/BUSINESS?hl=en-US&gl=US&ceid=US:en"),
    ("Google News - Markets", "https://news.google.com/rss/search?q=stock+market+OR+wall+street+OR+federal+reserve+OR+earnings&hl=en-US&gl=US&ceid=US:en"),
]


class DataManager:
    def __init__(self):
        self.update_queue = queue.Queue()
        self.watchlist = list(DEFAULT_WATCHLIST)
        self.prices = {}
        self.news_items = []
        self.last_news_fetch = None
        self.portfolio = {}
        self._running = False
        self._threads = []
        self._lock = threading.Lock()

    def start(self):
        self._running = True
        t1 = threading.Thread(target=self._price_loop, daemon=True)
        t2 = threading.Thread(target=self._news_loop, daemon=True)
        t1.start()
        t2.start()
        self._threads = [t1, t2]

    def stop(self):
        self._running = False

    def _price_loop(self):
        while self._running:
            try:
                self._fetch_prices()
            except Exception:
                pass
            time.sleep(30)

    def _fetch_prices(self):
        all_syms = list(self.watchlist)
        for cat_syms in MARKET_SYMBOLS.values():
            for _, sym in cat_syms:
                if sym not in all_syms:
                    all_syms.append(sym)

        if not all_syms:
            return

        try:
            with YFINANCE_LOCK:
                data = yf.download(
                    all_syms,
                    period="5d",
                    interval="1d",
                    progress=False,
                    threads=True,
                    auto_adjust=True,
                )
            results = {}
            if not data.empty:
                if len(all_syms) == 1:
                    sym = all_syms[0]
                    col = data["Close"].dropna()
                    if len(col) >= 2:
                        prev = float(col.iloc[-2])
                        curr = float(col.iloc[-1])
                        chg = curr - prev
                        pct = (chg / prev * 100) if prev else 0
                        results[sym] = {"price": curr, "change": chg, "pct": pct, "prev": prev}
                else:
                    close = data["Close"] if "Close" in data.columns else data.xs("Close", axis=1, level=0)
                    for sym in all_syms:
                        try:
                            col = close[sym].dropna()
                            if len(col) >= 2:
                                prev = float(col.iloc[-2])
                                curr = float(col.iloc[-1])
                                chg = curr - prev
                                pct = (chg / prev * 100) if prev else 0
                                results[sym] = {"price": curr, "change": chg, "pct": pct, "prev": prev}
                        except Exception:
                            pass

            with self._lock:
                self.prices.update(results)
            self.update_queue.put(("prices", results))

            # Self-heal: any symbol the bulk download couldn't resolve gets a
            # per-ticker retry immediately, so a single flaky symbol doesn't
            # stay stuck at "---" forever.
            missing = [s for s in all_syms if s not in results]
            if missing:
                self._fetch_prices_fallback(missing)
        except Exception:
            self._fetch_prices_fallback(all_syms)

    def _fetch_prices_fallback(self, symbols):
        results = {}
        for sym in symbols:
            try:
                t = yf.Ticker(sym)
                info = t.fast_info
                price = getattr(info, "last_price", None) or getattr(info, "regularMarketPrice", None)
                prev = getattr(info, "previous_close", None) or getattr(info, "regularMarketPreviousClose", None)
                if price and prev:
                    chg = price - prev
                    pct = (chg / prev * 100) if prev else 0
                    results[sym] = {"price": price, "change": chg, "pct": pct, "prev": prev}
            except Exception:
                pass
        with self._lock:
            self.prices.update(results)
        if results:
            self.update_queue.put(("prices", results))

    def _news_loop(self):
        while self._running:
            try:
                self._fetch_news()
            except Exception:
                pass
            time.sleep(90)

    def _fetch_news(self):
        items = []
        for source, url in NEWS_FEEDS:
            try:
                feed = feedparser.parse(url)
                for entry in feed.entries[:8]:
                    published, published_ts = parse_feed_time(entry)
                    items.append({
                        "source": source,
                        "title": entry.get("title", ""),
                        "summary": entry.get("summary", "")[:200],
                        "link": entry.get("link", ""),
                        "published": published,
                        "published_ts": published_ts,
                    })
            except Exception:
                pass

        items.sort(key=lambda x: x.get("published_ts", 0), reverse=True)
        with self._lock:
            self.news_items = items[:150]
        self.last_news_fetch = datetime.now()
        self.update_queue.put(("news", items[:150]))

    def get_chart_data(self, symbol, period="1mo", interval="1d"):
        try:
            t = yf.Ticker(symbol)
            df = t.history(period=period, interval=interval, auto_adjust=True)
            return df
        except Exception:
            return pd.DataFrame()

    def get_ticker_info(self, symbol):
        try:
            t = yf.Ticker(symbol)
            return t.info
        except Exception:
            return {}

    def add_to_watchlist(self, symbol):
        symbol = symbol.upper().strip()
        if symbol and symbol not in self.watchlist:
            self.watchlist.append(symbol)
            threading.Thread(target=self._fetch_prices, daemon=True).start()

    def remove_from_watchlist(self, symbol):
        if symbol in self.watchlist:
            self.watchlist.remove(symbol)

    def add_position(self, symbol, qty, avg_price):
        self.portfolio[symbol.upper()] = {"qty": qty, "avg_price": avg_price}

    def remove_position(self, symbol):
        self.portfolio.pop(symbol.upper(), None)

    def get_portfolio_weights(self):
        """Current holdings' market-value weights (falls back to avg cost if a
        live price isn't in yet), for the Analysis Workbench to run real
        strategies against the user's actual saved portfolio."""
        weights = {}
        for sym, pos in self.portfolio.items():
            price = self.prices.get(sym, {}).get("price") or pos.get("avg_price", 0)
            value = pos.get("qty", 0) * price
            if value > 0:
                weights[sym] = value
        total = sum(weights.values())
        if total <= 0:
            return {}
        return {sym: v / total for sym, v in weights.items()}
