"""Step 1b: download market data (FRED + Yahoo).

Run from the repo root:  python scripts/01_collect_market.py
Caches to data/market/fred.csv and data/market/yahoo.csv.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.market import build_market_data


def main() -> None:
    data = build_market_data()
    print("FRED series:", list(data["fred"].columns))
    print(data["fred"].tail(3).to_string())
    print("Yahoo tickers:", list(data["yahoo"].columns))
    print(data["yahoo"].tail(3).to_string())


if __name__ == "__main__":
    main()
