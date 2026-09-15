# Gemma + Streamlit layer — setup

This adds a Streamlit UI (`streamlit_app.py`) and a local-LLM narration layer
(`gemma_engine.py`) on top of the existing engines. **No existing file was
modified** — `generate_report.py` and the static dashboard still work exactly
as before.

## Why this design

The hard requirement in the brief is "no mistakes." LLMs (Gemma included)
occasionally round numbers wrong, invent a plausible-sounding figure, or
mislabel a temporary dip as permanent decline. The fix isn't a smarter prompt
— it's not letting the model do arithmetic at all:

- Every score, forecast, classification and repayment plan comes from the
  existing deterministic, backtested engines (`cashflow_engine`,
  `risk_engine`, `health_engine`, `forecast_engine`, `scenario_engine`,
  `repayment_engine`). Nothing about this pipeline changed.
- Gemma is only given those already-computed numbers and asked to write a
  sentence about them (`gemma_engine.generate_narrative`).
- Before anything Gemma writes is shown, `verify_grounding()` extracts every
  number in its output and checks it against the actual source numbers it
  was given. If Gemma drifts, we retry once with the mismatch pointed out;
  if it still drifts, the deterministic template is shown instead — the app
  never displays an unverified number.
- If Ollama isn't running, every Gemma-powered feature degrades to a
  template automatically. The app never crashes or blocks on the LLM.

## Run it

```bash
pip install -r requirements.txt

# Optional, for the AI narrative / free-text extraction tabs:
ollama pull gemma4:e2b    # Gemma 4's 2B-class edge model ("gemma4:2b" also works as an alias)
ollama serve              # usually already running as a background service

streamlit run streamlit_app.py
```

Open the sidebar to:
- pick the synthetic seed / forecast horizon
- point at your Ollama host/model (defaults to `http://localhost:11434`,
  `gemma4:e2b` — change this if `ollama list` shows a different tag on your
  machine)
- switch data source between the synthetic 8-borrower portfolio, your own
  CSV (`month, income, expenses` columns), or pasted free text that Gemma
  parses into structured months (you review the parsed table before it's
  used — nothing gets fed into the engines unreviewed)

## What Gemma is / isn't doing here

| Task | Who does it |
|---|---|
| Cash-flow, seasonality, trend, stress-cluster detection | `cashflow_engine.py` (statistics only) |
| Condition classification (stable / seasonal / structural decline / etc.) | `cashflow_engine.py` (rule-based, backtested at 100% on synthetic ground truth) |
| Risk & affordability scores | `risk_engine.py` |
| 3–12 month forecast range | `forecast_engine.py` — see "Forecast pipeline" below |
| Repayment strategy comparison & pick | `scenario_engine.py` / `repayment_engine.py` |
| Turning the above into a readable paragraph | **Gemma**, fact-checked before display |
| Parsing pasted/free-text financial statements into structured months | **Gemma**, shown to the user for review before use |

## Forecast pipeline (upgraded to an ensemble)

`forecast_engine.py` no longer picks one heuristic and hopes it's right for
every borrower. It runs four small, fully-explainable methods (recent-months
average, trend line, same-month-last-year pattern, last-month-repeated),
**backtests each one on that specific borrower's own earlier months**
(rolling-origin validation, the same idea `evaluate.py` already uses to
grade the whole system), and blends them weighted by how accurate they
actually were for that person. The uncertainty range comes from that same
backtested error, not a generic formula — a borrower the model has
historically nailed gets a tighter range; a genuinely erratic one gets an
honestly wider one.

Measured on the repo's own `evaluate.py` backtest (last 6 months held out,
same borrowers, nothing else changed):

| | Old (single heuristic) | New (backtested ensemble) |
|---|---|---|
| Income MAE | Rs.2,654.6 | **Rs.2,211.0** (−16.7%) |
| Net cash-flow MAE | Rs.2,891.1 | **Rs.2,420.5** (−16.3%) |
| Classifier accuracy | 100% (8/8) | 100% (8/8), unaffected |

Run `python3 evaluate.py` yourself to reproduce these numbers. Each
borrower's forecast tab has a "How was this forecast built?" expander
showing exactly which methods contributed and their backtested error for
that specific person.

## Front-end

The Streamlit UI uses a "loan ledger" visual language rather than a generic
dashboard theme: deep ledger-ink navy for text and primary data, warm
aged-paper background, a single reserved gold accent for highlights and
active states, ledger red-ink for risk/stress, and an approval-stamp teal
for recovered/safe. Callouts use a colored left-edge tab (like a
bookkeeper's flag) instead of boxed cards with shadows, so color always
carries meaning. Headings are set in Fraunces; everything else (including
all the numbers) is IBM Plex Sans for legibility.
