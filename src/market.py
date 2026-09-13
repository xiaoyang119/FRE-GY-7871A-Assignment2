"""Download market data for the four indicators (plus the control).

Four indicators from the assignment:

    DXY                U.S. dollar index                Yahoo Finance  DX-Y.NYB
    10s2s spread       10Y minus 2Y Treasury yield       FRED           T10Y2Y
    1-year yield       constant-maturity 1Y yield        FRED           DGS1
    growth minus value Russell 1000G minus R2000V        Yahoo Finance  IWF - IWN

Control variable (step 3 of the assignment):

    3-month bill yield FRED DGS3MO -- included so the words are not credited
    with the rate decision itself.

FRED is fetched without an API key from the ``fredgraph.csv`` endpoint; Yahoo
via ``yfinance`` (no key either).  Both are cached to ``data/market``.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .config import (
    FRED_API_KEY,
    FRED_API_URL,
    FRED_CSV_URL,
    FRED_SERIES,
    MARKET_DIR,
    REQUEST_TIMEOUT,
    TODAY,
    TREASURY_CSV_URL,
    USER_AGENT,
    YAHOO_CHART_URL,
    YAHOO_TICKERS,
)

_HEADERS = {"User-Agent": USER_AGENT}


# ---------------------------------------------------------------------------
# Yield data: FRED first, U.S. Treasury yield curve as a no-key fallback.
# Both return the same columns: t10y2y, dgs1, dgs3mo.
# ---------------------------------------------------------------------------
def download_fred(series: dict[str, str] | None = None,
                  start: str = "2018-01-01", end: str = TODAY,
                  cache_path: Path | None = None) -> pd.DataFrame:
    """Download FRED yield series as a wide DataFrame indexed by date.

    Columns use the *short* keys (``t10y2y`` etc.), not the FRED ids.
    Source order: (1) FRED API when ``FRED_API_KEY`` is set, (2) the no-key
    ``fredgraph.csv`` endpoint, (3) the U.S. Treasury daily yield curve.
    """
    import requests

    series = series or FRED_SERIES
    cache_path = Path(cache_path or MARKET_DIR / "fred.csv")
    if cache_path.exists():
        df = pd.read_csv(cache_path, index_col=0, parse_dates=True)
        if set(series) <= set(df.columns):
            return df

    try:
        if FRED_API_KEY:
            df = _download_fred_api(series, start, end)
        else:
            df = _download_fred_graph(series)
    except requests.RequestException as e:
        print(f"FRED unreachable ({type(e).__name__}); "
              f"falling back to U.S. Treasury yield curve.")
        df = download_treasury_yield_curve(start=start, end=end,
                                           cache_path=cache_path)

    df = df.loc[pd.Timestamp(start): pd.Timestamp(end)]
    df = df.astype(float)
    df.to_csv(cache_path)
    return df


def _download_fred_api(series: dict[str, str], start: str, end: str) -> pd.DataFrame:
    """Fetch series via the FRED JSON API (api.stlouisfed.org)."""
    import requests

    frames = {}
    for key, sid in series.items():
        r = requests.get(FRED_API_URL, params={
            "series_id": sid,
            "api_key": FRED_API_KEY,
            "file_type": "json",
            "observation_start": start,
            "observation_end": end,
        }, timeout=REQUEST_TIMEOUT, headers=_HEADERS)
        r.raise_for_status()
        obs = r.json().get("observations", [])
        s = pd.DataFrame(obs)[["date", "value"]]
        s["date"] = pd.to_datetime(s["date"])
        s["value"] = pd.to_numeric(s["value"], errors="coerce")
        frames[key] = s.set_index("date")["value"]
    return pd.concat(frames, axis=1).sort_index()


def _download_fred_graph(series: dict[str, str]) -> pd.DataFrame:
    """Fetch series via the no-key fredgraph.csv endpoint."""
    import requests

    frames = {}
    for key, sid in series.items():
        url = FRED_CSV_URL.format(sid=sid)
        # Short timeout so the Treasury fallback kicks in quickly when
        # fred.stlouisfed.org is unreachable.
        r = requests.get(url, timeout=15, headers=_HEADERS)
        r.raise_for_status()
        s = pd.read_csv(
            pd.io.common.StringIO(r.text),
            parse_dates=[0],
            na_values=".",
        )
        s = s.rename(columns={s.columns[0]: "date", s.columns[1]: key})
        frames[key] = s.set_index("date")[key]
    return pd.concat(frames, axis=1).sort_index()


def download_treasury_yield_curve(start: str = "2018-01-01", end: str = TODAY,
                                  cache_path: Path | None = None) -> pd.DataFrame:
    """U.S. Treasury daily yield curve -> t10y2y / dgs1 / dgs3mo (no key)."""
    import requests

    cache_path = Path(cache_path or MARKET_DIR / "fred.csv")
    if cache_path.exists():
        df = pd.read_csv(cache_path, index_col=0, parse_dates=True)
        if {"t10y2y", "dgs1", "dgs3mo"} <= set(df.columns):
            return df

    colmap = {"3 Mo": "dgs3mo", "1 Yr": "dgs1", "2 Yr": "dgs2", "10 Yr": "dgs10"}
    frames = []
    for year in range(pd.Timestamp(start).year, pd.Timestamp(end).year + 1):
        r = requests.get(TREASURY_CSV_URL.format(year=year),
                         timeout=REQUEST_TIMEOUT, headers=_HEADERS)
        r.raise_for_status()
        y = pd.read_csv(pd.io.common.StringIO(r.text))
        y = y.rename(columns={"Date": "date"})
        y["date"] = pd.to_datetime(y["date"], errors="coerce")
        for src, dst in colmap.items():
            if src in y.columns:
                y[dst] = pd.to_numeric(y[src], errors="coerce")
        keep = [c for c in ("dgs3mo", "dgs1", "dgs2", "dgs10") if c in y.columns]
        if "date" in y.columns and keep:
            frames.append(y.set_index("date")[keep])

    out = pd.concat(frames).sort_index()
    if "dgs10" in out and "dgs2" in out:
        out["t10y2y"] = out["dgs10"] - out["dgs2"]
    out = out[["t10y2y", "dgs1", "dgs3mo"]].loc[pd.Timestamp(start): pd.Timestamp(end)]
    out = out.astype(float)
    out.to_csv(cache_path)
    return out


# ---------------------------------------------------------------------------
# Yahoo Finance
# ---------------------------------------------------------------------------
def download_yahoo(tickers: dict[str, str] | None = None,
                   start: str = "2018-01-01", end: str = TODAY,
                   cache_path: Path | None = None) -> pd.DataFrame:
    """Download adjusted-close prices (columns = short keys) from Yahoo.

    Uses the Yahoo chart API directly (requests) rather than yfinance, which
    proved unreliable here.
    """
    import requests

    tickers = tickers or YAHOO_TICKERS
    cache_path = Path(cache_path or MARKET_DIR / "yahoo.csv")
    if cache_path.exists():
        df = pd.read_csv(cache_path, index_col=0, parse_dates=True)
        if set(tickers) <= set(df.columns) and not df.empty:
            return df

    frames = {}
    for key, tkr in tickers.items():
        frames[key] = _download_yahoo_chart(tkr, start, end)

    df = pd.concat(frames, axis=1).sort_index()
    df.to_csv(cache_path)
    return df


def _download_yahoo_chart(ticker: str, start: str, end: str) -> pd.Series:
    """Fetch daily adjusted close for one ticker from the Yahoo chart API."""
    import requests

    p1 = int(pd.Timestamp(start).timestamp())
    p2 = int(pd.Timestamp(end).timestamp())
    r = requests.get(YAHOO_CHART_URL.format(ticker=ticker),
                     params={"period1": p1, "period2": p2, "interval": "1d"},
                     timeout=REQUEST_TIMEOUT, headers=_HEADERS)
    r.raise_for_status()
    result = r.json()["chart"]["result"][0]
    ts = result.get("timestamp", [])
    adj = result.get("indicators", {}).get("adjclose", [{}])[0].get("adjclose", [])
    # Yahoo stamps different tickers at different times of day (FX ~04:00 UTC,
    # ETFs ~13:30 UTC); normalize to calendar date so all three align, and keep
    # one bar per date.
    dates = pd.to_datetime(ts, unit="s").normalize()
    s = pd.Series(adj, index=dates, name=ticker).astype(float)
    return s[~s.index.duplicated(keep="last")]


# ---------------------------------------------------------------------------
# Combined
# ---------------------------------------------------------------------------
def build_market_data(start: str = "2018-01-01", end: str = TODAY) -> dict[str, pd.DataFrame]:
    """Download and cache both sources; return {'fred': df, 'yahoo': df}."""
    fred = download_fred(start=start, end=end)
    yahoo = download_yahoo(start=start, end=end)
    return {"fred": fred, "yahoo": yahoo}
