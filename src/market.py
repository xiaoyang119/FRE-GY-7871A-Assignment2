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
    FRED_CSV_URL,
    FRED_SERIES,
    MARKET_DIR,
    REQUEST_TIMEOUT,
    TODAY,
    USER_AGENT,
    YAHOO_TICKERS,
)

_HEADERS = {"User-Agent": USER_AGENT}


# ---------------------------------------------------------------------------
# FRED (no key)
# ---------------------------------------------------------------------------
def download_fred(series: dict[str, str] | None = None,
                  start: str = "2018-01-01", end: str = TODAY,
                  cache_path: Path | None = None) -> pd.DataFrame:
    """Download FRED series as a wide DataFrame indexed by date.

    Columns use the *short* keys (``t10y2y`` etc.), not the FRED ids.
    """
    import requests

    series = series or FRED_SERIES
    cache_path = Path(cache_path or MARKET_DIR / "fred.csv")
    if cache_path.exists():
        df = pd.read_csv(cache_path, index_col=0, parse_dates=True)
        if set(series) <= set(df.columns):
            return df

    frames = {}
    for key, sid in series.items():
        url = FRED_CSV_URL.format(sid=sid)
        r = requests.get(url, timeout=REQUEST_TIMEOUT, headers=_HEADERS)
        r.raise_for_status()
        s = pd.read_csv(
            pd.io.common.StringIO(r.text),
            parse_dates=[0],
            na_values=".",
        )
        s = s.rename(columns={s.columns[0]: "date", s.columns[1]: key})
        frames[key] = s.set_index("date")[key]

    df = pd.concat(frames, axis=1).sort_index()
    df = df.loc[pd.Timestamp(start): pd.Timestamp(end)]
    df = df.astype(float)
    df.to_csv(cache_path)
    return df


# ---------------------------------------------------------------------------
# Yahoo Finance
# ---------------------------------------------------------------------------
def download_yahoo(tickers: dict[str, str] | None = None,
                   start: str = "2018-01-01", end: str = TODAY,
                   cache_path: Path | None = None) -> pd.DataFrame:
    """Download adjusted-close prices (columns = short keys) via yfinance."""
    import yfinance as yf

    tickers = tickers or YAHOO_TICKERS
    cache_path = Path(cache_path or MARKET_DIR / "yahoo.csv")
    if cache_path.exists():
        df = pd.read_csv(cache_path, index_col=0, parse_dates=True)
        if set(tickers) <= set(df.columns):
            return df

    raw = yf.download(
        tickers=list(tickers.values()),
        start=start,
        end=end,
        auto_adjust=True,
        progress=False,
        threads=True,
    )
    close = raw["Close"] if isinstance(raw.columns, pd.MultiIndex) else raw[["Close"]]
    close = close.rename(columns={v: k for k, v in tickers.items()})
    close = close.sort_index()
    close.to_csv(cache_path)
    return close


# ---------------------------------------------------------------------------
# Combined
# ---------------------------------------------------------------------------
def build_market_data(start: str = "2018-01-01", end: str = TODAY) -> dict[str, pd.DataFrame]:
    """Download and cache both sources; return {'fred': df, 'yahoo': df}."""
    fred = download_fred(start=start, end=end)
    yahoo = download_yahoo(start=start, end=end)
    return {"fred": fred, "yahoo": yahoo}
