import numpy as np
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
from data_manager import YFINANCE_LOCK

TRADING_DAYS = 252

LAZY_PORTFOLIOS = {
    "Classic 60/40": {"VTI": 0.60, "BND": 0.40},
    "Three-Fund Portfolio": {"VTI": 0.60, "VXUS": 0.20, "BND": 0.20},
    "Permanent Portfolio": {"VTI": 0.25, "TLT": 0.25, "GLD": 0.25, "BIL": 0.25},
    "All Weather": {"VTI": 0.30, "TLT": 0.40, "IEF": 0.15, "GLD": 0.075, "DBC": 0.075},
    "100% Equities (SPY)": {"SPY": 1.0},
}


def get_multi_history(tickers, start=None, end=None, period=None):
    """Fetch aligned adjusted-close price history for many tickers at once."""
    tickers = sorted(set(t.upper().strip() for t in tickers if t.strip()))
    if not tickers:
        return pd.DataFrame()

    kwargs = dict(progress=False, threads=True, auto_adjust=True, group_by="column")
    with YFINANCE_LOCK:
        if period:
            data = yf.download(tickers, period=period, **kwargs)
        else:
            data = yf.download(tickers, start=start, end=end, **kwargs)

    if data.empty:
        return pd.DataFrame()

    if len(tickers) == 1:
        close = data[["Close"]].copy()
        close.columns = tickers
    else:
        close = data["Close"] if "Close" in data.columns.get_level_values(0) else data.xs("Close", axis=1, level=0)

    close = close.dropna(how="all").ffill().dropna()
    return close


def daily_returns(prices):
    return prices.pct_change().dropna(how="all")


def cagr(value_series):
    if len(value_series) < 2:
        return 0.0
    total_return = value_series.iloc[-1] / value_series.iloc[0]
    years = (value_series.index[-1] - value_series.index[0]).days / 365.25
    if years <= 0 or total_return <= 0:
        return 0.0
    return total_return ** (1 / years) - 1


def annualized_vol(returns):
    if len(returns) < 2:
        return 0.0
    freq = _infer_annualization_factor(returns)
    return float(returns.std() * np.sqrt(freq))


def sharpe_ratio(returns, rf=0.0):
    vol = annualized_vol(returns)
    if vol == 0:
        return 0.0
    freq = _infer_annualization_factor(returns)
    ann_ret = float(returns.mean() * freq)
    return (ann_ret - rf) / vol


def sortino_ratio(returns, rf=0.0):
    freq = _infer_annualization_factor(returns)
    downside = returns[returns < 0]
    if len(downside) < 2:
        return 0.0
    downside_dev = float(downside.std() * np.sqrt(freq))
    if downside_dev == 0:
        return 0.0
    ann_ret = float(returns.mean() * freq)
    return (ann_ret - rf) / downside_dev


def max_drawdown(value_series):
    if len(value_series) < 2:
        return 0.0
    cummax = value_series.cummax()
    drawdown = value_series / cummax - 1
    return float(drawdown.min())


def best_worst_year(value_series):
    if len(value_series) < 2:
        return None, None
    yearly = value_series.resample("YE").last()
    yearly_returns = yearly.pct_change().dropna()
    if yearly_returns.empty:
        return None, None
    return float(yearly_returns.max()), float(yearly_returns.min())


def _infer_annualization_factor(returns):
    if len(returns) < 2:
        return TRADING_DAYS
    avg_gap = (returns.index[-1] - returns.index[0]).days / max(len(returns) - 1, 1)
    if avg_gap <= 3:
        return TRADING_DAYS
    if avg_gap <= 10:
        return 52
    return 12


def run_backtest(prices, weight_schedule, initial=10000.0, rebalance="monthly"):
    """Simulate portfolio growth given a fixed or dynamic weight schedule.

    weight_schedule: either a dict {ticker: weight} (static), or a callable
    (date, available_tickers) -> {ticker: weight} evaluated at each rebalance date.
    """
    if prices.empty:
        return pd.Series(dtype=float), {}

    tickers = list(prices.columns)
    rets = daily_returns(prices)
    if rets.empty:
        return pd.Series(dtype=float), {}

    rebalance_dates = _rebalance_dates(rets.index, rebalance)

    def weights_for(date):
        if callable(weight_schedule):
            w = weight_schedule(date, tickers)
        else:
            w = dict(weight_schedule)
        total = sum(w.values())
        if total <= 0:
            return {t: 0.0 for t in tickers}
        return {t: w.get(t, 0.0) / total for t in tickers}

    current_weights = weights_for(rets.index[0])
    holdings = {t: initial * w for t, w in current_weights.items()}
    values = []
    idx = []

    for date in rets.index:
        if date in rebalance_dates:
            total_value = sum(holdings.values())
            current_weights = weights_for(date)
            holdings = {t: total_value * w for t, w in current_weights.items()}

        for t in tickers:
            r = rets.at[date, t] if t in rets.columns and not pd.isna(rets.at[date, t]) else 0.0
            holdings[t] = holdings.get(t, 0.0) * (1 + r)

        values.append(sum(holdings.values()))
        idx.append(date)

    value_series = pd.Series(values, index=idx)

    best_yr, worst_yr = best_worst_year(value_series)
    port_returns = value_series.pct_change().dropna()
    stats = {
        "cagr": cagr(value_series),
        "vol": annualized_vol(port_returns),
        "sharpe": sharpe_ratio(port_returns),
        "sortino": sortino_ratio(port_returns),
        "max_drawdown": max_drawdown(value_series),
        "best_year": best_yr,
        "worst_year": worst_yr,
        "final_value": float(value_series.iloc[-1]) if len(value_series) else initial,
        "total_return": float(value_series.iloc[-1] / initial - 1) if len(value_series) else 0.0,
    }
    return value_series, stats


def _rebalance_dates(date_index, rebalance):
    if rebalance in (None, "none", "None"):
        return {date_index[0]}
    dates = set()
    dates.add(date_index[0])
    period_map = {"monthly": "ME", "quarterly": "QE", "annually": "YE"}
    freq = period_map.get(rebalance, "ME")
    marker = pd.Series(date_index, index=date_index).resample(freq).last().dropna()
    dates.update(marker.values)
    return dates


def get_fama_french_factors(model="FF3", start=None, end=None):
    """Fetch real Fama-French factor data from the Ken French Data Library.

    Returns (DataFrame in decimal form indexed by month-end date, error_message).
    """
    try:
        from pandas_datareader import data as pdr
    except ImportError:
        return None, "pandas-datareader not installed"

    dataset_map = {
        "CAPM": "F-F_Research_Data_Factors",
        "FF3": "F-F_Research_Data_Factors",
        "FF5": "F-F_Research_Data_5_Factors_2x3",
        "Carhart": "F-F_Research_Data_Factors",
    }
    dataset = dataset_map.get(model, "F-F_Research_Data_Factors")

    try:
        raw = pdr.DataReader(dataset, "famafrench", start=start, end=end)
        factors = raw[0].copy()
        factors.index = factors.index.to_timestamp(how="end").normalize()
        factors = factors / 100.0
        factors.columns = [c.strip() for c in factors.columns]

        if model == "Carhart":
            mom_raw = pdr.DataReader("F-F_Momentum_Factor", "famafrench", start=start, end=end)
            mom = mom_raw[0].copy()
            mom.index = mom.index.to_timestamp(how="end").normalize()
            mom = mom / 100.0
            mom.columns = [c.strip() for c in mom.columns]
            factors = factors.join(mom, how="inner")

        return factors, None
    except Exception as e:
        return None, f"Could not fetch Fama-French data: {e}"


def ols_regress(y, X):
    """Plain OLS via lstsq. X should NOT include an intercept column; one is added.
    Returns dict with coef (incl. intercept as first), se, tstat, r2, names order = ['alpha', *X.columns]
    """
    X = np.asarray(X, dtype=float)
    y = np.asarray(y, dtype=float)
    n, k = X.shape
    design = np.column_stack([np.ones(n), X])

    coef, residuals, rank, _ = np.linalg.lstsq(design, y, rcond=None)
    fitted = design @ coef
    resid = y - fitted
    dof = max(n - design.shape[1], 1)
    sigma2 = float(np.sum(resid ** 2) / dof)

    try:
        xtx_inv = np.linalg.inv(design.T @ design)
    except np.linalg.LinAlgError:
        xtx_inv = np.linalg.pinv(design.T @ design)

    se = np.sqrt(np.diag(sigma2 * xtx_inv))
    tstats = coef / np.where(se == 0, np.nan, se)

    ss_tot = np.sum((y - y.mean()) ** 2)
    r2 = 1 - np.sum(resid ** 2) / ss_tot if ss_tot > 0 else 0.0

    return {"coef": coef, "se": se, "tstat": tstats, "r2": float(r2), "n": n}


def portfolio_stats_from_returns(returns, weights):
    """weights: array aligned to returns.columns"""
    w = np.asarray(weights, dtype=float)
    mean_ann = returns.mean().values * TRADING_DAYS
    cov_ann = returns.cov().values * TRADING_DAYS
    ret = float(w @ mean_ann)
    vol = float(np.sqrt(w @ cov_ann @ w))
    return ret, vol, mean_ann, cov_ann


def default_date_range(years=10):
    end = datetime.now()
    start = end - timedelta(days=int(years * 365.25))
    return start, end


def black_litterman(cov_ann, market_weights, views, tau=0.05, risk_aversion=2.5):
    """Single/multi absolute-view Black-Litterman blend.

    cov_ann: NxN annualized covariance matrix.
    market_weights: length-N array, the prior ("market") portfolio.
    views: list of (index, annual_return_view) tuples, one absolute view per asset.
    Returns (posterior_returns, prior_returns) both length-N arrays.
    """
    cov_ann = np.asarray(cov_ann, dtype=float)
    w_mkt = np.asarray(market_weights, dtype=float)
    n = len(w_mkt)

    prior = risk_aversion * cov_ann @ w_mkt

    if not views:
        return prior.copy(), prior.copy()

    k = len(views)
    P = np.zeros((k, n))
    Q = np.zeros(k)
    for row, (idx, view_return) in enumerate(views):
        P[row, idx] = 1.0
        Q[row] = view_return

    tau_cov = tau * cov_ann
    omega = np.diag(np.diag(P @ tau_cov @ P.T))

    middle = np.linalg.inv(P @ tau_cov @ P.T + omega)
    posterior = prior + tau_cov @ P.T @ middle @ (Q - P @ prior)
    return posterior, prior


def rolling_annualized_vol(returns, window=20):
    """Rolling annualized volatility per column of a returns DataFrame."""
    return returns.rolling(window).std() * np.sqrt(TRADING_DAYS)


def inverse_vol_weights(vols):
    """Risk-parity-style weights inversely proportional to volatility."""
    vols = np.asarray(vols, dtype=float)
    vols = np.where(vols <= 0, np.nan, vols)
    inv = 1.0 / vols
    inv = np.nan_to_num(inv, nan=0.0)
    total = inv.sum()
    if total <= 0:
        n = len(vols)
        return np.ones(n) / n
    return inv / total
