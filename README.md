# Dynamic Microloan Repayment & Cash-Flow Planning — Prototype

A working, end-to-end prototype for the hackathon problem statement: given a
borrower's irregular income/expense history and an existing fixed loan
installment, the system reasons about cash-flow stress, tells a temporary
dip apart from a genuine structural decline, and proposes a concrete
alternative repayment structure — with every recommendation traced back to
specific numbers.

## What's actually implemented

- **`data_generator.py`** — synthesizes 24 months of income/expenses for 6
  borrowers, each a distinct real-world archetype: stable salaried-style,
  seasonal (harvest-linked), gig/irregular, a temporary shock that recovers,
  a genuine structural decline, and a growing small business. (No real
  financial data is used or required — swap this module out for a real
  data source without touching anything downstream.)
- **`cashflow_engine.py`** — computes net cash flow, a 3-month rolling
  average, a seasonality index (year-over-year correlation, not just
  variance, so random noise doesn't get mistaken for a seasonal rhythm),
  a trend comparison (recent 6 months vs. prior 6), and detects "stress
  clusters" — contiguous months where the existing installment would eat
  into the borrower's safety buffer. The classifier (`classify_condition`)
  uses those clusters as primary evidence to label each borrower: stable,
  improving, seasonal_pattern, temporary_stress, chronic_strain, or
  structural_decline.
- **`risk_engine.py`** — turns that analysis into an affordability score,
  a risk score, and an **evidence chain**: a short list of plain-language
  statements, each one citing a specific computed number, that justifies
  the classification. This is the explainability layer the problem
  statement asks for.
- **`repayment_engine.py`** — proposes a concrete alternative repayment
  schedule per condition: keep the plan (stable), an optional accelerated
  track (improving), a step schedule aligned to income peaks/troughs
  (seasonal), a moratorium on the shock months with the deferred amount
  re-amortized (temporary stress), a lightened/extended plan (chronic
  strain), or a full restructuring flagged for manual lender review
  (structural decline).
- **`generate_report.py`** — runs the pipeline for every borrower and
  writes `dashboard/data.js`.
- **`dashboard/index.html`** — a static, single-page dashboard (no server,
  no build step) that visualizes the portfolio: a borrower list, cash-flow
  charts, the evidence trail, and a side-by-side original-vs-recommended
  repayment schedule chart.

## How to run it

1. Unzip this folder.
2. (Optional — a `dashboard/data.js` is already included) regenerate the
   data with:
   ```
   python3 generate_report.py
   ```
   Requires only the Python standard library — no `pip install` needed.
3. Open `dashboard/index.html` directly in any browser (double-click it).
   It needs an internet connection only to load the Chart.js library and
   Google Fonts from their CDNs — everything else is local.

## Known limitations (be ready to say these out loud to judges)

- **Data is synthetic.** It's built to be realistic and clearly labeled by
  archetype, but it hasn't been validated against real microfinance
  transaction data. That's the natural next step.
- **Thresholds are heuristic, not learned.** The 10% safety buffer, the
  6-month trend window, and the classification cut-offs are reasonable
  starting points, not the output of a fitted model. For a real deployment
  you'd want to calibrate these against historical repayment outcomes
  (did borrowers we called "temporary_stress" actually recover?).
- **Six archetypes, not a general classifier.** The system handles the
  patterns it was designed to distinguish (seasonal, one-off shock,
  structural decline). Real borrowers will show blended or noisier
  patterns; the classifier's thresholds will need tuning on real data
  before this generalizes.
- **No lender-side constraints modeled.** The repayment engine currently
  only reasons about borrower affordability, not the lender's own
  liquidity or portfolio-level risk limits — a fuller system would
  balance both sides.

## Suggested framing for the pitch

Lead with the evidence trail — it's the differentiator. Anyone can compute
a risk score; showing your work (which months, which numbers, why this is
a dip and not a decline) is what makes the recommendation trustworthy to
both the lender and the borrower.
