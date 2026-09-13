"""Step 1: collect FOMC statements, minutes, Chair speeches + testimony.

Run from the repo root:  python scripts/00_collect_texts.py
Writes data/texts/*.txt and data/market/documents.parquet (manifest without
the raw text; the text lives in the .txt files).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src import fomc
from src.config import TEXT_DIR


def main() -> None:
    print("Collecting statements / minutes / speeches / testimony ...")
    docs = fomc.collect()

    print("Collecting press-conference transcripts ...")
    stmt_dates = docs.loc[docs["kind"] == "statement", "date"]
    presconf = fomc.collect_press_conferences(stmt_dates)

    all_docs = fomc.merge_docs(docs, presconf)
    print(f"Collected {len(all_docs)} documents:")
    print(all_docs.groupby(["kind", "chair"]).size().to_string())

    manifest = fomc.save_texts(all_docs)
    print(f"Saved manifest -> {manifest}")


if __name__ == "__main__":
    main()
