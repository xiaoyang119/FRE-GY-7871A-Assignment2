"""Hawkish / dovish scoring with a monetary-policy word list (method 1).

The assignment asks for a word list "built for monetary policy language"
("higher inflation" is hawkish, "inflation has eased" is dovish).  This module
ships a seed lexicon you are expected to refine against the actual documents --
it is intentionally small and transparent, not a black box.

Scores produced per document (all zero if neither list matches):

    n_hawk, n_dove       raw phrase counts
    net_count            n_hawk - n_dove
    net_share            (n_hawk - n_dove) / (n_hawk + n_dove)  in [-1, 1]
    net_per_100w         (n_hawk - n_dove) / n_words * 100

``net_share`` (+1 = purely hawkish language, -1 = purely dovish) is the most
natural bounded score to feed the regression in step 3.
"""

from __future__ import annotations

import re

import pandas as pd

# ---------------------------------------------------------------------------
# Seed lexicon -- edit freely.  Phrases are matched case-insensitively.
# ---------------------------------------------------------------------------
LEXICON: dict[str, list[str]] = {
    "hawkish": [
        # inflation / prices on the high side
        "higher inflation",
        "elevated inflation",
        "inflation remains elevated",
        "inflation pressures",
        "upside risks to inflation",
        "upside risk",
        "above target",
        "above 2 percent",
        "above the committee's 2 percent",
        "overheating",
        "inflation will rise",
        # policy stance
        "tightening",
        "tighter policy",
        "restrictive",
        "restrictive stance",
        "further increases",
        "additional firming",
        "further firming",
        "rate hike",
        "rate hikes",
        "hiking",
        "raise the target range",
        "raising rates",
        "raise rates",
        "interest rates will rise",
        "will rise",
        "further tightening",
        "premature to ease",
        "need to remain restrictive",
        # activity / labour
        "strong labor market",
        "robust growth",
        "strong growth",
        "solid pace",
        "solid economic growth",
    ],
    "dovish": [
        # inflation / prices on the low side
        "inflation has eased",
        "inflation eased",
        "inflation is coming down",
        "coming down",
        "cooling",
        "disinflation",
        "subdued inflation",
        "below target",
        "below 2 percent",
        "below the committee's 2 percent",
        "progress toward 2 percent",
        "progress on inflation",
        "inflation will ease",
        # policy stance
        "easing",
        "accommodative",
        "policy accommodation",
        "rate cut",
        "rate cuts",
        "cut the target range",
        "lower rates",
        "lowering rates",
        "reducing rates",
        "further easing",
        "interest rates will fall",
        "will fall",
        "neutral rate",
        # activity / labour
        "slack",
        "downside risks",
        "downside risk",
        "softening",
        "moderating",
        "moderated",
        "slowing",
        "slowed",
        "labor market has cooled",
        "cooled",
        "supportive of growth",
        "well anchored",
        "well-anchored",
    ],
}


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------
def _count(text_lower: str, phrases: list[str]) -> int:
    total = 0
    for phrase in phrases:
        total += len(re.findall(re.escape(phrase), text_lower))
    return total


def score_document(text: str, lexicon: dict[str, list[str]] | None = None) -> dict:
    """Return the word-list tone scores for one document's text."""
    lexicon = lexicon or LEXICON
    t = (text or "").lower()
    n_hawk = _count(t, lexicon.get("hawkish", []))
    n_dove = _count(t, lexicon.get("dovish", []))
    n_words = len(t.split())
    total = n_hawk + n_dove
    return {
        "n_hawk": n_hawk,
        "n_dove": n_dove,
        "n_words": n_words,
        "net_count": n_hawk - n_dove,
        "net_share": (n_hawk - n_dove) / total if total else 0.0,
        "net_per_100w": (n_hawk - n_dove) / n_words * 100 if n_words else 0.0,
    }


def score_dataframe(docs: pd.DataFrame, text_col: str = "text") -> pd.DataFrame:
    """Attach the word-list scores as columns to a documents DataFrame."""
    out = docs.copy()
    scores = out[text_col].map(score_document)
    for key in ("n_hawk", "n_dove", "n_words", "net_count", "net_share", "net_per_100w"):
        out[f"wl_{key}"] = [s[key] for s in scores]
    return out
