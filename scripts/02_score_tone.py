"""Step 2: score every document's tone (word list + FinBERT).

Run from the repo root:  python scripts/02_score_tone.py [--no-finbert]

Word-list scoring is pure Python and always runs.  FinBERT requires
``transformers`` + ``torch``; skip it with ``--no-finbert`` until those are
installed.  Writes data/scores/tone_scores.parquet.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src import fomc
from src.config import SCORE_DIR
from src.tone_wordlist import score_dataframe as score_wordlist


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-finbert", action="store_true",
                    help="skip FinBERT scoring (needs transformers+torch)")
    args = ap.parse_args()

    docs = fomc.load_documents()
    print(f"Loaded {len(docs)} documents")

    print("Scoring with word list ...")
    out = score_wordlist(docs)

    if not args.no_finbert:
        print("Scoring with FinBERT (this is the slow step) ...")
        from src.tone_finbert import score_dataframe as score_finbert
        out = score_finbert(out)

    out.to_csv(SCORE_DIR / "tone_scores.csv", index=False)
    print("Saved data/scores/tone_scores.csv")
    print(out[["kind", "date", "chair", "wl_net_share"]].head().to_string())


if __name__ == "__main__":
    main()
