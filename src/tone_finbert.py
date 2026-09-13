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

from .config import FINBERT_MODEL

# Key sentences from "Parsing the Fed" (Method 1: Factor Similarity).
KEY_SENTENCES = {
    "hawkish": ["Interest rates will rise", "Inflation will rise"],
    "dovish": ["Interest rates will fall", "Inflation will ease"],
}

_MODEL = None
_PIPE = None
_KEY_EMB = None  # cached embeddings of the four key sentences


def _get_model():
    """Lazily load FinBERT tokenizer + model (mean-pooling)."""
    global _MODEL
    if _MODEL is None:
        from transformers import AutoModel, AutoTokenizer
        _MODEL = (AutoTokenizer.from_pretrained(FINBERT_MODEL),
                  AutoModel.from_pretrained(FINBERT_MODEL))
    return _MODEL


def _get_pipeline():
    """Lazily load the FinBERT sentiment-analysis pipeline (all three labels)."""
    global _PIPE
    if _PIPE is None:
        from transformers import pipeline
        # top_k=None -> return positive/negative/neutral together.
        _PIPE = pipeline("sentiment-analysis", model=FINBERT_MODEL, top_k=None)
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


def _key_embeddings() -> dict:
    """Embed the four key sentences once and cache them (they never change)."""
    global _KEY_EMB
    if _KEY_EMB is None:
        _KEY_EMB = {
            "hawkish": [_embed(s) for s in KEY_SENTENCES["hawkish"]],
            "dovish": [_embed(s) for s in KEY_SENTENCES["dovish"]],
        }
    return _KEY_EMB


# ---------------------------------------------------------------------------
# Variant A: sentence sentiment
# ---------------------------------------------------------------------------
def finbert_sentiment(text: str) -> dict:
    """Average FinBERT pos/neg/neutral probability over sentences.

    Sentences are scored in batches of 32 (the pipeline accepts a list and
    returns one [pos, neg, neu] triple per sentence).
    """
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
    sentences = [s[:512] for s in sentences[:512]]  # cap count + length
    if not sentences:
        return {"pos": 0.0, "neg": 0.0, "neu": 0.0, "label": "neutral"}

    pipe = _get_pipeline()
    pos = neg = neu = 0.0
    n = 0
    for i in range(0, len(sentences), 32):
        for row in pipe(sentences[i:i + 32]):   # row = [{pos},{neg},{neu}]
            for r in row:
                if r["label"] == "positive":
                    pos += r["score"]
                elif r["label"] == "negative":
                    neg += r["score"]
                else:
                    neu += r["score"]
        n += len(sentences[i:i + 32])
    return {"pos": pos / n, "neg": neg / n, "neu": neu / n,
            "label": "positive" if pos >= neg else "negative"}


# ---------------------------------------------------------------------------
# Variant B: factor similarity to key sentences
# ---------------------------------------------------------------------------
def finbert_similarity(text: str) -> dict:
    """Cosine similarity to hawkish vs dovish key sentences."""
    doc = _embed(text)
    key = _key_embeddings()  # cached: no per-document re-embedding of key sentences
    sim_hawk = float(np.mean([_cosine(doc, e) for e in key["hawkish"]]))
    sim_dove = float(np.mean([_cosine(doc, e) for e in key["dovish"]]))
    return {"sim_hawk": sim_hawk, "sim_dove": sim_dove,
            "sim_net": sim_hawk - sim_dove}


# ---------------------------------------------------------------------------
# DataFrame helpers
# ---------------------------------------------------------------------------
def score_dataframe(docs: pd.DataFrame, text_col: str = "text",
                    method: str = "both", progress: bool = True) -> pd.DataFrame:
    """Attach FinBERT scores with a progress bar (one pass over documents)."""
    from tqdm.auto import tqdm

    out = docs.copy()
    rows = []
    for text in tqdm(out[text_col].tolist(), desc="FinBERT",
                     disable=not progress, unit="doc"):
        row = {}
        if method in ("sentiment", "both"):
            s = finbert_sentiment(text)
            row.update({f"fb_{k}": s[k] for k in ("pos", "neg", "neu")})
        if method in ("similarity", "both"):
            s = finbert_similarity(text)
            row.update({f"fb_{k}": s[k] for k in ("sim_hawk", "sim_dove", "sim_net")})
        rows.append(row)
    for key in rows[0]:
        out[key] = [r[key] for r in rows]
    return out
