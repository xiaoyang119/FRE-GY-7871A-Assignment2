"""FinBERT tone scoring (method 2) -- sentiment and factor similarity.

Requires ``transformers`` and ``torch`` (CPU is fine).  Install with:

    pip install "transformers>=4.40" "torch>=2.0"

Two variants, both allowed by the assignment ("either scoring the sentiment of
each sentence or measuring its similarity to key sentences"):

    * sentiment        -- ProsusAI/finbert sentence-level pos/neg/neutral
                          probabilities, averaged over the document.
    * factor similarity-- cosine similarity of the document embedding to key
                          sentences ("Interest rates will rise", ...), mirroring
                          "Parsing the Fed" (Method 1).

The model is loaded once and cached on the module.
"""

from __future__ import annotations

import re

import numpy as np
import pandas as pd

# Key sentences from "Parsing the Fed" (Method 1: Factor Similarity).
KEY_SENTENCES = {
    "hawkish": ["Interest rates will rise", "Inflation will rise"],
    "dovish": ["Interest rates will fall", "Inflation will ease"],
}

_MODEL = None
_PIPE = None


def _get_model():
    """Lazily load FinBERT tokenizer + model (mean-pooling)."""
    global _MODEL
    if _MODEL is None:
        from transformers import AutoModel, AutoTokenizer
        name = "ProsusAI/finbert"
        _MODEL = (AutoTokenizer.from_pretrained(name),
                  AutoModel.from_pretrained(name))
    return _MODEL


def _get_pipeline():
    """Lazily load the FinBERT sentiment-analysis pipeline."""
    global _PIPE
    if _PIPE is None:
        from transformers import pipeline
        _PIPE = pipeline("sentiment-analysis", model="ProsusAI/finbert",
                         truncation=True)
    return _PIPE


def _embed(text: str) -> np.ndarray:
    """Mean-pooled FinBERT embedding of a text (chunked at 512 tokens)."""
    import torch
    tok, model = _get_model()
    chunks = [text[i:i + 4000] for i in range(0, len(text), 4000)] or [""]
    vecs = []
    for chunk in chunks:
        enc = tok(chunk, return_tensors="pt", truncation=True, max_length=512,
                  padding=True)
        with torch.no_grad():
            out = model(**enc)
        # mean pool over tokens (ignore padding)
        mask = enc["attention_mask"].unsqueeze(-1).float()
        pooled = (out.last_hidden_state * mask).sum(1) / mask.sum(1)
        vecs.append(pooled.squeeze(0).numpy())
    return np.mean(vecs, axis=0)


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    denom = (np.linalg.norm(a) * np.linalg.norm(b))
    return float(np.dot(a, b) / denom) if denom else 0.0


# ---------------------------------------------------------------------------
# Variant A: sentence sentiment
# ---------------------------------------------------------------------------
def finbert_sentiment(text: str) -> dict:
    """Average FinBERT pos/neg/neutral probability over sentences."""
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
    if not sentences:
        return {"pos": 0.0, "neg": 0.0, "neu": 0.0, "label": "neutral"}
    pipe = _get_pipeline()
    pos = neg = neu = 0.0
    for s in sentences[:512]:  # cap for speed on very long minutes
        for r in pipe(s[:512]):
            if r["label"] == "positive":
                pos += r["score"]
            elif r["label"] == "negative":
                neg += r["score"]
            else:
                neu += r["score"]
    n = min(len(sentences), 512)
    return {"pos": pos / n, "neg": neg / n, "neu": neu / n,
            "label": "positive" if pos >= neg else "negative"}


# ---------------------------------------------------------------------------
# Variant B: factor similarity to key sentences
# ---------------------------------------------------------------------------
def finbert_similarity(text: str, key_sentences: dict | None = None) -> dict:
    """Cosine similarity to hawkish vs dovish key sentences."""
    key_sentences = key_sentences or KEY_SENTENCES
    doc = _embed(text)
    sim_hawk = np.mean([_cosine(doc, _embed(s)) for s in key_sentences["hawkish"]])
    sim_dove = np.mean([_cosine(doc, _embed(s)) for s in key_sentences["dovish"]])
    return {"sim_hawk": sim_hawk, "sim_dove": sim_dove,
            "sim_net": sim_hawk - sim_dove}


# ---------------------------------------------------------------------------
# DataFrame helpers
# ---------------------------------------------------------------------------
def score_dataframe(docs: pd.DataFrame, text_col: str = "text",
                    method: str = "both") -> pd.DataFrame:
    """Attach FinBERT scores (``finbert_sentiment`` and/or ``finbert_similarity``)."""
    out = docs.copy()
    if method in ("sentiment", "both"):
        s = out[text_col].map(finbert_sentiment)
        for k in ("pos", "neg", "neu"):
            out[f"fb_{k}"] = [x[k] for x in s]
    if method in ("similarity", "both"):
        s = out[text_col].map(finbert_similarity)
        for k in ("sim_hawk", "sim_dove", "sim_net"):
            out[f"fb_{k}"] = [x[k] for x in s]
    return out
