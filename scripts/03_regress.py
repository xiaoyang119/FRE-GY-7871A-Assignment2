"""Step 3: one-day market changes + tone regressions.

Run from the repo root:  python scripts/03_regress.py

Requires steps 00 and 01 (documents + market data) and step 02 (tone scores).
Writes data/scores/event_changes.parquet and data/scores/regressions.csv.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd

from src import fomc
from src.config import SCORE_DIR
from src.market import download_fred, download_yahoo
from src.regress import one_day_change, run_regressions

# Interpretable net-tone columns (word list and FinBERT).  Add more here once
# you have decided which FinBERT variant to use.
TONE_COLS = ["wl_net_share", "wl_net_per_100w", "fb_sim_net", "fb_pos"]


def main() -> None:
    scores = pd.read_csv(SCORE_DIR / "tone_scores.csv")
    fred = download_fred()
    yahoo = download_yahoo()

    tone_cols = [c for c in TONE_COLS if c in scores.columns]

    event = one_day_change(fred, yahoo, scores.set_index("doc_id")["date"])
    event = event.join(scores.set_index("doc_id")[["kind", "chair"] + tone_cols])

    event.to_csv(SCORE_DIR / "event_changes.csv", index=False)
    print("Event changes (one per release):")
    print(event[["release", "dxy_chg", "t10y2y_chg", "dgs1_chg", "gv_chg"]].tail().to_string())

    regs = run_regressions(event, tone_cols)
    regs.to_csv(SCORE_DIR / "regressions.csv", index=False)
    print("\nRegressions (indicator_chg ~ tone + dgs3mo_chg):")
    print(regs.to_string(index=False))


if __name__ == "__main__":
    main()
