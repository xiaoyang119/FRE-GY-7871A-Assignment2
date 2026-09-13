"""Collect FOMC communications from federalreserve.gov.

Three (plus one) document types, all free on federalreserve.gov:

    * statements  -- post-meeting FOMC statements ("press releases")
    * minutes     -- FOMC meeting minutes (full text, not the announcement page)
    * speeches    -- the Chair's speeches
    * testimony   -- the Chair's congressional testimony
    * presconf    -- the Chair's post-meeting press conference transcripts

The Chair changes from Powell to Warsh on 22 May 2026, so every document is
labelled with the chair in office at its release and each release date carries
its *time* (FOMC statements/minutes go out at 2:00 p.m. ET), as the assignment
requires.

The three source JSON feeds (ne-press / ne-speeches / ne-testimony) carry a
``d`` field like ``"7/29/2026 2:00:00 PM"`` -- date and time together.  Minutes
are announced in the press feed but the full text lives at a separate URL
(``/monetarypolicy/fomcminutes{yyyymmdd}.htm``), so we follow that link.
"""

from __future__ import annotations

import json
import re
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup

from .config import (
    DATA,
    FED_BASE,
    FEEDS,
    POWELL_START,
    REQUEST_TIMEOUT,
    TEXT_DIR,
    USER_AGENT,
    WARSH_START,
)

_HEADERS = {"User-Agent": USER_AGENT}


# ---------------------------------------------------------------------------
# Fetching the feeds
# ---------------------------------------------------------------------------
def fetch_feed(name: str) -> list[dict]:
    """Return the raw list of items from a Fed JSON feed (BOM-stripped)."""
    url = FEEDS[name]
    r = requests.get(url, timeout=REQUEST_TIMEOUT, headers=_HEADERS)
    r.raise_for_status()
    return json.loads(r.content.decode("utf-8-sig"))


# ---------------------------------------------------------------------------
# Date parsing
# ---------------------------------------------------------------------------
def parse_fed_dt(s: str | None) -> pd.Timestamp | None:
    """Parse a Fed ``d`` field into a timezone-naive Timestamp (US/Eastern).

    Examples: ``"7/29/2026 2:00:00 PM"`` or ``"4/14/2008"`` (no time).
    """
    if not s:
        return None
    s = s.strip()
    for fmt in ("%m/%d/%Y %I:%M:%S %p", "%m/%d/%Y"):
        try:
            return pd.Timestamp(datetime.strptime(s, fmt))
        except ValueError:
            continue
    return None


def chair_at(dt: pd.Timestamp) -> str:
    """Assign the chair in office at ``dt`` (used for FOMC-level documents)."""
    if dt is None:
        return "unknown"
    return "Warsh" if dt >= pd.Timestamp(WARSH_START) else "Powell"


def speaker_chair(speaker: str, dt: pd.Timestamp | None) -> str | None:
    """Return the chair for a *speaker-attributed* document, or None to drop.

    A speech/testimony counts as "the Chair's" only if the speaker is the
    sitting Chair at the time.  Powell is Chair until Warsh's oath (22 May
    2026); afterwards Powell's remarks are as Governor and are dropped.
    """
    if dt is None:
        return None
    if "Warsh" in speaker and dt >= pd.Timestamp(WARSH_START):
        return "Warsh"
    if "Powell" in speaker and pd.Timestamp(POWELL_START) <= dt < pd.Timestamp(WARSH_START):
        return "Powell"
    return None


# ---------------------------------------------------------------------------
# HTML text extraction
# ---------------------------------------------------------------------------
def extract_article_text(url: str) -> str:
    """Pull the main body text of a federalreserve.gov page (``div#article``)."""
    r = requests.get(url, timeout=REQUEST_TIMEOUT, headers=_HEADERS)
    r.raise_for_status()
    r.encoding = "utf-8"
    soup = BeautifulSoup(r.text, "html.parser")
    art = soup.select_one("div#article") or soup.select_one("div[role=main]")
    if art is None:
        return ""
    paras = [p.get_text(" ", strip=True) for p in art.find_all("p")]
    # Drop the boilerplate header lines and empty paragraphs.
    skip_prefixes = (
        "For release at",
        "Share",
        "For media inquiries",
    )
    kept = []
    for p in paras:
        if not p:
            continue
        if p.startswith(skip_prefixes):
            continue
        kept.append(p)
    return "\n\n".join(kept)


def _resolve_minutes_url(press_url: str) -> str | None:
    """From a minutes announcement page, find the full-minutes HTML link."""
    r = requests.get(press_url, timeout=REQUEST_TIMEOUT, headers=_HEADERS)
    r.raise_for_status()
    r.encoding = "utf-8"
    soup = BeautifulSoup(r.text, "html.parser")
    for a in soup.find_all("a", href=True):
        if "fomcminutes" in a["href"]:
            href = a["href"]
            return href if href.startswith("http") else FED_BASE + href
    return None


# ---------------------------------------------------------------------------
# Classification of the press feed
# ---------------------------------------------------------------------------
def classify_press(items: list[dict]) -> tuple[list[dict], list[dict]]:
    """Split the press feed into (statements, minutes) announcements."""
    statements, minutes = [], []
    for it in items:
        title = it.get("t", "")
        if title == "Federal Reserve issues FOMC statement":
            statements.append(it)
        elif title.startswith("Minutes of the Federal Open Market Committee"):
            minutes.append(it)
    return statements, minutes


def _in_window(dt: pd.Timestamp | None) -> bool:
    if dt is None:
        return False
    return pd.Timestamp(POWELL_START) <= dt


def classify_chair(items: list[dict]) -> list[dict]:
    """Keep only the *sitting* Chair's speeches/testimony; tag each with chair."""
    out = []
    for it in items:
        speaker = f"{it.get('s', '')} {it.get('a', '')}"
        dt = parse_fed_dt(it.get("d"))
        chair = speaker_chair(speaker, dt)
        if chair is not None:
            it = dict(it)
            it["_chair"] = chair
            out.append(it)
    return out


# ---------------------------------------------------------------------------
# Document collection
# ---------------------------------------------------------------------------
def _item_to_doc(kind: str, it: dict, text: str) -> dict:
    dt = parse_fed_dt(it.get("d"))
    # Speaker-attributed docs (speech/testimony) carry an explicit chair tag;
    # FOMC-level docs (statement/minutes) fall back to the date-based chair.
    chair = it.get("_chair") or chair_at(dt)
    return {
        "kind": kind,
        "date": dt,
        "chair": chair,
        "title": it.get("t", ""),
        "url": (it.get("l", "") if it.get("l", "").startswith("http")
                else FED_BASE + it.get("l", "")),
        "text": text,
    }


def collect() -> pd.DataFrame:
    """Collect statements, minutes, speeches and testimony into a DataFrame.

    Returns one row per document with columns: kind, date, chair, title, url,
    text.  Also caches the result as ``data/texts/documents.parquet`` and the
    individual texts as ``data/texts/{kind}/{doc_id}.txt``.
    """
    docs: list[dict] = []

    press = fetch_feed("press")
    statements, minutes_ann = classify_press(press)

    for it in statements:
        dt = parse_fed_dt(it.get("d"))
        if not _in_window(dt):
            continue
        url = FED_BASE + it["l"]
        docs.append(_item_to_doc("statement", it, extract_article_text(url)))

    for it in minutes_ann:
        dt = parse_fed_dt(it.get("d"))
        if not _in_window(dt):
            continue
        ann_url = FED_BASE + it["l"]
        full_url = _resolve_minutes_url(ann_url)
        if full_url:
            text = extract_article_text(full_url)
            docs.append(_item_to_doc("minutes", it, text))

    for it in classify_chair(fetch_feed("speeches")):
        url = FED_BASE + it["l"]
        docs.append(_item_to_doc("speech", it, extract_article_text(url)))

    for it in classify_chair(fetch_feed("testimony")):
        url = FED_BASE + it["l"]
        docs.append(_item_to_doc("testimony", it, extract_article_text(url)))

    df = pd.DataFrame(docs).sort_values("date").reset_index(drop=True)
    df["doc_id"] = [f"{r.kind}_{r.date:%Y%m%d_%H%M}_{i:02d}"
                    for i, r in enumerate(df.itertuples(), 1)]
    return df


def _extract_presconf_pdf(dt: pd.Timestamp) -> str | None:
    """Download and text-extract a press-conference transcript PDF.

    The transcript is published as a PDF (``/mediacenter/files/FOMCpresconf
    {yyyymmdd}.pdf``); the HTML page at ``/monetarypolicy/fomcpresconf*.htm``
    is only a video player and does NOT contain the transcript.
    """
    try:
        import io
        from pypdf import PdfReader
    except ImportError:
        return None  # pypdf missing; skip rather than store the boilerplate page
    url = f"{FED_BASE}/mediacenter/files/FOMCpresconf{dt:%Y%m%d}.pdf"
    try:
        r = requests.get(url, timeout=REQUEST_TIMEOUT, headers=_HEADERS)
        if r.status_code != 200:
            return None
        reader = PdfReader(io.BytesIO(r.content))
        text = "\n\n".join((p.extract_text() or "") for p in reader.pages)
        return text.strip() or None
    except Exception:
        return None


def collect_press_conferences(statement_dates: pd.Series | list) -> pd.DataFrame:
    """Collect post-meeting press-conference transcripts (PDF text).

    Keyed on the *meeting* (statement) date.  Meetings without a press
    conference have no PDF and are skipped.
    """
    docs = []
    for d in statement_dates:
        dt = pd.Timestamp(d)
        text = _extract_presconf_pdf(dt)
        if text:
            docs.append({
                "kind": "presconf",
                "date": dt,
                "chair": chair_at(dt),
                "title": f"FOMC press conference {dt:%B %d, %Y}",
                "url": f"{FED_BASE}/mediacenter/files/FOMCpresconf{dt:%Y%m%d}.pdf",
                "text": text,
            })
        time.sleep(0.3)  # be polite
    return pd.DataFrame(docs)


def merge_docs(docs: pd.DataFrame, extra: pd.DataFrame) -> pd.DataFrame:
    """Concatenate main docs with extras (e.g. press conferences), dedupe."""
    if extra is None or extra.empty:
        return docs.reset_index(drop=True)
    merged = pd.concat([docs, extra], ignore_index=True)
    merged = merged.sort_values("date").reset_index(drop=True)
    merged["doc_id"] = [f"{r.kind}_{r.date:%Y%m%d_%H%M}_{i:02d}"
                        for i, r in enumerate(merged.itertuples(), 1)]
    return merged


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------
def save_texts(df: pd.DataFrame) -> Path:
    """Persist documents: full text in data/documents.csv (gitignored),
    plus one readable .txt per document under data/texts/{kind}/."""
    for row in df.itertuples():
        if not row.text:
            continue
        kind_dir = TEXT_DIR / row.kind
        kind_dir.mkdir(parents=True, exist_ok=True)
        (kind_dir / f"{row.doc_id}.txt").write_text(row.text, encoding="utf-8")
    csv_path = DATA / "documents.csv"
    df.to_csv(csv_path, index=False)
    return csv_path


def load_documents(path: Path | None = None) -> pd.DataFrame:
    """Reload the collected documents (with text) from the cached CSV."""
    path = Path(path or DATA / "documents.csv")
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found -- run scripts/00_collect_texts.py first"
        )
    df = pd.read_csv(path)
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
    return df
