# Assignment 2 — Evaluating the Impact of FOMC Communications on Asset Prices

**FRE-GY 7871 A · NLP and the Investment Process · Fall 2026**

> Draft for review. Tables/figures are referenced by name; insert them from
> `outputs/` (Table 1–3 CSVs and `figure1_tone_over_time.png`). The forecast
> numbers in §6 are a first draft to be reviewed.

---

## 1. Task and approach

Kevin Warsh became Fed Chair on 22 May 2026. This report analyses how the tone
of Federal Reserve communication changed since he took office, how markets
reacted to it, and forecasts the September 2026 FOMC meeting, using Jerome
Powell's Chair term (February 2018 – May 2026) as the baseline.

I collected 311 FOMC documents from federalreserve.gov — post-meeting
statements, meeting minutes, and the Chair's speeches (including congressional
testimony and press-conference transcripts) — each with its release date and
time. I scored each document hawkish/dovish with **two methods** (a
monetary-policy word list, and FinBERT used both as sentence-sentiment and as
key-sentence similarity). I then measured the one-day change in four market
indicators around each release and regressed those changes on each tone score,
**controlling for the change in the 3-month Treasury bill yield (DGS3MO)** so
that the words are not credited with the rate decision itself.

## 2. Data

**Table 1 — documents collected, by type and by Chair.**

| kind | Powell | Warsh | Total |
|---|---|---|---|
| statement | 68 | 2 | 70 |
| minutes | 67 | 2 | 69 |
| speech | 78 | 1 | 79 |
| testimony | 26 | 1 | 27 |
| presconf | 64 | 2 | 66 |
| **Total** | **303** | **8** | **311** |

The Warsh-era sample is small (8 documents, of which only 2 statements and 2
minutes), which is a central limitation discussed in §8.

## 3. Methods

**Method 1 — word list.** A lexicon of hawkish phrases ("higher inflation",
"inflation pressures", "rate hike", …) and dovish phrases ("inflation has
eased", "rate cut", "softening", …). Each document gets a net score
`(n_hawk − n_dove)/(n_hawk + n_dove)` in [−1, +1], positive = hawkish.

**Method 2 — FinBERT (ProsusAI/finbert).** Two sub-variants, both allowed by the
assignment: (a) **sentence sentiment** — the average positive/negative/neutral
probability over the document's sentences; and (b) **factor similarity** —
cosine similarity of the document embedding to the key sentences
"Interest rates will rise" / "Inflation will rise" (hawkish) versus "Interest
rates will fall" / "Inflation will ease" (dovish), following "Parsing the Fed".

## 4. Results

### 4.1 Tone trend — Warsh is more hawkish

**Figure 1 — hawkish/dovish tone over time by document type (Warsh term marked).**

By the word list, Warsh's documents average a net share of **+0.61** versus
Powell's **−0.07**; Warsh's two statements score a maximal **+1.0** (no dovish
phrases at all) against Powell's statement average of **+0.40**. FinBERT's
factor-similarity score is essentially zero for every Warsh document (−0.01),
so it does not discriminate here; FinBERT's positive-sentiment probability is
also higher for Warsh (0.30 vs 0.24), and — consistent with "Parsing the Fed" —
positive sentiment in this sample tracks *hawkish* rather than dovish language.

### 4.2 Market validation

**Table 2 — one-day change in the four indicators after each Warsh-era release,
beside that release's tone scores.**

**Table 3 — each indicator's one-day change regressed on each tone score,
controlling for the 3M bill change (n = 293).**

The word list has significant explanatory power:

- 10s2s change ~ word-list hawkishness: **−0.011 pp, p = 0.016** — a more
  hawkish tone is associated with a *flatter* curve (the spread narrows).
- Growth-minus-value change ~ word-list hawkishness: **+0.40 pp, p = 0.028** —
  a more hawkish tone is associated with growth outperforming value.

FinBERT's two scores are **not** significant for any indicator (all p > 0.05).
The control variable DGS3MO is highly significant — most clearly for the 1-year
yield, which moves almost one-for-one with the 3-month bill (coef ≈ 0.97). This
confirms that the rate decision itself drives short rates and that separating
"wording" from "the rate decision" is necessary, exactly as the assignment
requires.

## 5. Comparison with the readings

- **Doh, Kim & Yang (2021)** identify tone by comparing each statement to the
  Board staff's alternative statements (Alt A/C/D) using the Universal Sentence
  Encoder. Those alternatives are released only after five years, so they are
  unavailable for the recent (and Warsh-era) sample; this is why I used the word
  list and FinBERT instead, as the assignment directs.
- **"Parsing the Fed" (2021)** compares factor similarity, a word list, and
  FinBERT sentiment, and reports that the word list "consistently outperformed"
  other methods in some categories. My results agree: the word list is the only
  method with significant explanatory power, while FinBERT's factor-similarity
  scores were near-zero and uninformative.
- **Doh, Song & Yang (2020)** regress standardized tone surprises on asset-price
  changes over short windows. My one-day-change regression with the 3-month-bill
  control follows the same spirit on daily data, and the strong DGS3MO loading
  parallels their finding that the policy-rate component is a large share of the
  market's reaction.

## 6. Forecast — September 2026 FOMC meeting

*(Draft numbers — review before submitting.)*

**Rate decision** (must sum to 100%): **cut 5% · hold 70% · hike 25%.**
Both of Warsh's meetings maintained the target range, his statements are
maximally hawkish ("inflation remains elevated"), and in July three voters
dissented in favour of *raising* the range — so the risk is skewed to a hike,
not a cut.

**Statement tone:** **35%** probability the September statement is *more*
hawkish than July's. July was already at the top of the word-list scale, leaving
little room to become more hawkish.

**Market reaction** (probability the indicator rises on the day, and expected
size):

| Indicator | P(rise) | Expected size |
|---|---|---|
| DXY | 45% | ±0.3% |
| 10s2s | 35% | −0.04 pp |
| 1Y yield | 50% | +0.01 pp |
| Growth − Value | 60% | +0.4 pp |

The 10s2s and Growth−Value forecasts lean on the two significant coefficients
(hawkish → spread narrows, growth beats value); DXY and 1Y are held near 50/50
because neither has a significant tone relationship (the 1Y is dominated by the
rate decision, which is expected to be a hold).

## 7. Recommendation

**Position: a curve-flattening trade — short the 2-year, long the 10-year
Treasury (i.e., position for the 10s2s spread to narrow).**

The reasoning is the significant result in Table 3: a hawkish tone is associated
with a flatter curve. My forecast is a hold with a hawkish statement (70% hold,
35% more-hawkish), which — via that coefficient — points to a narrowing 10s2s.
**What would prove this wrong:** a dovish surprise — a rate *cut* and/or a
statement that pivots toward easing — which would steepen the curve (widen the
spread) and move the position against me.

## 8. Limitations

- **Tiny Warsh sample.** Eight documents (two statements) cannot support
  statistical inference for the Warsh era; the "Warsh is more hawkish" finding
  and the September forecast are case observations, not estimates.
- **FinBERT factor similarity failed** (near-zero scores, no significance); the
  word list was the informative method.
- **Same-day statement + press conference** share the same one-day market move
  (e.g., both July 29 releases show −0.57% DXY), so those observations are not
  independent in Table 3.
