"""Central configuration for the Assignment 2 pipeline.

Assignment 2: Evaluating the Impact of FOMC Communications on Asset Prices
FRE-GY 7871 A, NLP and the Investment Process, Fall 2026.

Everything that defines the *sample* and the *data sources* lives here:
which documents, which window, which FRED series, which Yahoo tickers.
Analysis choices (lexicons, regression spec, forecast) belong in the other
modules / the notebook, not here.
"""

from __future__ import annotations

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
DATA = ROOT / "data"
TEXT_DIR = DATA / "texts"          # raw FOMC statements, minutes, speeches
MARKET_DIR = DATA / "market"       # FRED + Yahoo daily series
SCORE_DIR = DATA / "scores"        # tone scores, joined event tables
OUTPUT_DIR = ROOT / "outputs"      # figures / tables (small, committed)

for _d in (TEXT_DIR, MARKET_DIR, SCORE_DIR, OUTPUT_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Time window
# ---------------------------------------------------------------------------
# Baseline: Jerome Powell's time as Chair. Powell became Chair 5 Feb 2018 and
# served through 15 May 2026 (with an interim period until Warsh was sworn in).
POWELL_START = "2018-02-05"

# Kevin Warsh took the oath of office 22 May 2026.
WARSH_START = "2026-05-22"

# "to today". Fixed here so a run is reproducible; update if you re-run later.
TODAY = "2026-09-13"

# ---------------------------------------------------------------------------
# FRED series  (no API key needed -- fredgraph.csv endpoint)
# ---------------------------------------------------------------------------
#   T10Y2Y : 10-Year minus 2-Year Treasury constant-maturity spread
#   DGS1   : 1-Year Treasury constant-maturity yield
#   DGS3MO : 3-Month Treasury bill secondary-market rate  (control variable)
FRED_SERIES = {
    "t10y2y": "T10Y2Y",
    "dgs1": "DGS1",
    "dgs3mo": "DGS3MO",
}

FRED_CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}"

# ---------------------------------------------------------------------------
# Yahoo Finance tickers
# ---------------------------------------------------------------------------
#   DX-Y.NYB : U.S. dollar index (DXY)
#   IWF      : iShares Russell 1000 Growth ETF  (growth proxy)
#   IWN      : iShares Russell 2000 Value ETF   (value proxy)
YAHOO_TICKERS = {
    "dxy": "DX-Y.NYB",
    "iwf": "IWF",
    "iwn": "IWN",
}

# ---------------------------------------------------------------------------
# Federal Reserve JSON feeds (text sources)
# ---------------------------------------------------------------------------
FED_BASE = "https://www.federalreserve.gov"

FEEDS = {
    "press": f"{FED_BASE}/json/ne-press.json",          # FOMC statements + minutes
    "speeches": f"{FED_BASE}/json/ne-speeches.json",    # Governors' speeches
    "testimony": f"{FED_BASE}/json/ne-testimony.json",  # testimony incl. Chair
}

# The Chair's names as they appear in the "s" (speaker) field of the feeds.
CHAIR_NAMES = ("Powell", "Warsh")

# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------
USER_AGENT = os.environ.get("FED_USER_AGENT", "Mozilla/5.0 (research; NYU FRE-GY 7871)")
REQUEST_TIMEOUT = 60  # seconds
