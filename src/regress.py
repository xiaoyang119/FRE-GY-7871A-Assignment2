"""Event-window market changes and tone regressions (step 3).

For each document release we compute the *one-day* change in the four
indicators as ``post_close - prev_close`` where ``post`` is the first market
close at or after the release and ``prev`` the last close strictly before it.
FOMC statements/minutes go out at 2:00 p.m. ET (before the 4 p.m. close), so
this captures the same-day reaction; a speech released after the close is
carried to the next trading day automatically.

Indicator definitions (columns produced):

    dxy_chg     pct change in the dollar index            (DXY)
    t10y2y_chg  level change in the 10Y-2Y spread         (percentage points)
    dgs1_chg    level change in the 1Y yield              (percentage points)
    gv_chg      Russell 1000G return - Russell 2000V return (percentage points)
    dgs3mo_chg  level change in the 3M bill yield         (control)

Then each indicator change is regressed on each tone score with the 3-month
bill change as the control, exactly the specification the assignment asks for:

    indicator_chg ~ tone_score + dgs3mo_chg
"""

from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd
import statsmodels.api as sm

INDICATORS = ["dxy_chg", "t10y2y_chg", "dgs1_chg", "gv_chg"]

# U.S. market close, used to decide whether a release reacts in the same
# trading day's close or the next day's.
_MARKET_CLOSE = dt.time(16, 0)


# ---------------------------------------------------------------------------
# One-day changes
# ---------------------------------------------------------------------------
def _prev_post(market_index: pd.DatetimeIndex, release: pd.Timestamp):
    """Return (prev_close_label, post_close_label) around a release.

    ``market_index`` is date-only: each label is that day's *close*.  A release
    at or before 4 p.m. ET reacts in that day's close (prev = prior day); one
    after the close reacts in the next trading day's close (prev = release day).
    """
    idx = market_index
    day = release.normalize()
    if release.time() > _MARKET_CLOSE:
        day = day + pd.Timedelta(days=1)
    prev = idx[idx < day]
    post = idx[idx >= day]
    if len(prev) == 0 or len(post) == 0:
        return None, None
    return prev[-1], post[0]


def one_day_change(fred: pd.DataFrame, yahoo: pd.DataFrame,
                   releases: pd.Series) -> pd.DataFrame:
    """Compute one-day indicator changes for a Series of release timestamps.

    ``releases`` is a ``pd.Series`` indexed by doc_id with Timestamp values.
    ``fred`` has columns t10y2y/dgs1/dgs3mo; ``yahoo`` has dxy/iwf/iwn.
    """
    fred = fred.astype(float).sort_index()
    yahoo = yahoo.astype(float).sort_index()
    idx = fred.index.union(yahoo.index).sort_values()

    rows = []
    for doc_id, rel in releases.items():
        rel = pd.Timestamp(rel)
        prev, post = _prev_post(idx, rel)
        if prev is None:
            continue

        def change(level: bool, series: pd.Series, key: str):
            a, b = series.get(prev), series.get(post)
            if pd.isna(a) or pd.isna(b):
                return np.nan
            return float(b - a) if level else float((b - a) / a * 100.0)

        # growth-minus-value = return spread, so build it from the two ETFs.
        iwf_a, iwf_b = yahoo["iwf"].get(prev), yahoo["iwf"].get(post)
        iwn_a, iwn_b = yahoo["iwn"].get(prev), yahoo["iwn"].get(post)
        gv = np.nan
        if not any(pd.isna(x) for x in (iwf_a, iwf_b, iwn_a, iwn_b)):
            gv = float((iwf_b / iwf_a - 1) * 100 - (iwn_b / iwn_a - 1) * 100)

        rows.append({
            "doc_id": doc_id,
            "release": rel,
            "prev": prev,
            "post": post,
            "dxy_chg": change(False, yahoo["dxy"], "dxy"),
            "t10y2y_chg": change(True, fred["t10y2y"], "t10y2y"),
            "dgs1_chg": change(True, fred["dgs1"], "dgs1"),
            "gv_chg": gv,
            "dgs3mo_chg": change(True, fred["dgs3mo"], "dgs3mo"),
        })
    return pd.DataFrame(rows).set_index("doc_id")


# ---------------------------------------------------------------------------
# Regressions
# ---------------------------------------------------------------------------
def run_regressions(event: pd.DataFrame, tone_cols: list[str],
                    indicators: list[str] | None = None,
                    control: str = "dgs3mo_chg") -> pd.DataFrame:
    """Regress each indicator change on each tone score (+ control).

    Returns a tidy DataFrame: one row per (indicator, tone) with OLS coef,
    std error, t-stat, p-value, R^2 and sample size.
    """
    indicators = indicators or INDICATORS
    results = []
    for y in indicators:
        for tone in tone_cols:
            df = event[[y, tone, control]].dropna()
            if len(df) < 3:
                continue
            X = sm.add_constant(df[[tone, control]])
            fit = sm.OLS(df[y], X).fit()
            results.append({
                "indicator": y,
                "tone": tone,
                "coef": fit.params[tone],
                "se": fit.bse[tone],
                "tstat": fit.tvalues[tone],
                "pvalue": fit.pvalues[tone],
                "r2": fit.rsquared,
                "n": int(fit.nobs),
                "control_coef": fit.params.get(control, np.nan),
            })
    return pd.DataFrame(results)
