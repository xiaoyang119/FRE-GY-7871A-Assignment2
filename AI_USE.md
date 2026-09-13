# AI use disclosure

Required by the syllabus. One paragraph is enough. Undisclosed use is an
integrity violation; disclosed use costs you nothing.

---

**Tools used:**

DeepSeek (AI coding agent), used interactively throughout the assignment.
The analysis itself relies on pre-trained open models and public data — FinBERT
(ProsusAI/finbert) for tone scoring, the FRED API, Yahoo Finance, and
federalreserve.gov — but those are analysis inputs, not the "AI assistance"
being disclosed here.

**What I used it for:**

Scaffolding and debugging the full pipeline in the repository: the FOMC
document collector (federalreserve.gov JSON feeds + the press-conference
transcript PDFs), the market-data downloader (FRED, with a U.S. Treasury
yield-curve fallback, and a direct Yahoo chart-API client), the word-list and
FinBERT tone scorers, and the one-day-change + regression module. I also had it
draft the report narrative (Sections 1, 5, 7, 8) and a first pass at the
forecast/recommendation wording.

**What I wrote myself:**

The substantive judgment calls are mine, not the model's: the hawkish/dovish
lexicon design, the decision to use both FinBERT variants (sentiment and key-
sentence similarity), the regression specification (one-day change on tone with
the DGS3MO control, which the assignment requires), the mapping of FinBERT's
"positive" sentiment to hawkish/dovish, the forecast probabilities and the
recommendation. I reviewed and directed every step and verified the outputs
against the assignment brief.

**Anything the model got wrong that I had to correct:**

Several things, all caught by checking against primary sources or the
assignment text rather than the model's own explanation. The most important:
(1) the "one-day change" was initially computed one day late (a release at
2 p.m. must react in *that* day's close, not the next day's); (2) Yahoo data
came back empty through yfinance, and the fix was to call the Yahoo chart API
directly; (3) the press-conference "transcripts" were initially scraped from an
HTML page that contains only the video player, not the transcript — the fix was
to parse the linked PDF; (4) FRED's no-key CSV endpoint was unreachable, which
the model first misdiagnosed as a sandbox-only issue, and the fix was a U.S.
Treasury fallback plus the FRED API; (5) a FinBERT pipeline-argument change in
transformers 5.x meant the sentiment scorer only captured the top label until
it was switched to `top_k=None`.
