"""
gemma_engine.py
--------------------
Local Gemma (via Ollama) integration layer.

DESIGN PRINCIPLE — "the LLM never computes, it only explains":

  All numbers a lender or borrower will act on (risk score, affordability
  score, forecast bounds, repayment plan, condition classification) are
  produced by the deterministic engines already in this repo
  (cashflow_engine, risk_engine, health_engine, repayment_engine,
  forecast_engine, scenario_engine). Those are backtested and auditable.

  Gemma is used ONLY for:
    1. Turning the evidence chain + forecast + plan into a fluent,
       borrower-facing narrative (language generation).
    2. Interactive Loan Copilot Q&A: answering credit committee or borrower
       questions grounded strictly in the computed facts.
    3. Parsing free-text / pasted transaction logs into structured records
       {month, income, expenses} (structured extraction).

  Because an LLM can still drift or round sloppily even when told not
  to invent numbers, every narrative is passed through
  `verify_grounding()`: every number the model wrote down is checked
  against the actual source numbers it was given. Any number that
  doesn't trace back to the source data is flagged or replaced with
  a deterministic fallback.

  If Ollama isn't running, every function here degrades gracefully to an
  intelligent deterministic template — the app never crashes and never blocks on
  the LLM being available.
"""

import json
import re
import requests

DEFAULT_HOST = "http://localhost:11434"
DEFAULT_MODEL = "gemma4:e4b"
REQUEST_TIMEOUT = 45


class OllamaUnavailable(Exception):
    pass


def ollama_generate(prompt, system=None, model=DEFAULT_MODEL, host=DEFAULT_HOST,
                     temperature=0.2, timeout=REQUEST_TIMEOUT):
    """Low temperature by default: this is a grounded explainer, not a
    creative writer. Raises OllamaUnavailable on any connection problem."""
    try:
        resp = requests.post(
            f"{host}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "system": system or "",
                "stream": False,
                "options": {"temperature": temperature},
            },
            timeout=timeout,
        )
        resp.raise_for_status()
        return resp.json().get("response", "").strip()
    except requests.exceptions.RequestException as e:
        raise OllamaUnavailable(str(e))


def check_ollama_health(model=DEFAULT_MODEL, host=DEFAULT_HOST):
    """Checks if Ollama is reachable and whether the model is available.
    Returns (is_up: bool, message: str)."""
    try:
        resp = requests.get(f"{host}/api/tags", timeout=3)
        resp.raise_for_status()
        tags = [m["name"] for m in resp.json().get("models", [])]
        if any(model.split(":")[0] in t for t in tags):
            return True, f"Ollama active, '{model}' loaded."
        return True, f"Ollama active, but '{model}' not pulled yet (`ollama pull {model}`)."
    except requests.exceptions.RequestException as e:
        return False, f"Ollama offline ({host}). Using high-fidelity grounded template engine."


# ---------------------------------------------------------------------------
# 1. Grounded narrative generation
# ---------------------------------------------------------------------------

def _collect_source_numbers(borrower_report):
    """Pull every number that is legitimately part of this borrower's
    computed record for anti-hallucination verification."""
    nums = set()

    def add(x):
        try:
            f = float(x)
            nums.add(round(f))
            nums.add(round(f, 1))
            nums.add(round(f, 2))
        except (TypeError, ValueError):
            pass

    r = borrower_report
    for v in r.get("net_cash_flow", []):
        add(v)
    for v in r.get("income", []):
        add(v)
    for v in r.get("expenses", []):
        add(v)
    add(r.get("loan", {}).get("installment"))
    add(r.get("loan", {}).get("principal"))
    add(r.get("loan", {}).get("tenure_months"))
    add(r.get("affordability_score"))
    add(r.get("risk_score"))
    add(r.get("stress_ratio"))
    add(r.get("trend", {}).get("pct_change"))
    add(r.get("financial_health", {}).get("score"))
    add(r.get("repayment_stress_index", {}).get("index"))
    add(r.get("classification_confidence"))
    fc = r.get("forecast", {}).get("net_cash_flow", {})
    for series in (fc.get("point", []), fc.get("lower", []), fc.get("upper", [])):
        for v in series:
            add(v)
    for c in r.get("stress_clusters", []):
        add(c.get("start"))
        add(c.get("end"))
        add(c.get("length"))
    for i in range(0, 37):
        nums.add(i)
    return nums


def verify_grounding(narrative, source_numbers, tolerance=0.5):
    """Extract every number-looking token from the narrative and check it
    is within `tolerance` of some number the model was actually given.
    Returns (ok: bool, unverified: list[str])."""
    tokens = re.findall(r"-?\d+(?:\.\d+)?", narrative.replace(",", ""))
    unverified = []
    for t in tokens:
        val = float(t)
        if not any(abs(val - s) <= max(tolerance, abs(s) * 0.02) for s in source_numbers):
            unverified.append(t)
    return (len(unverified) == 0), unverified


def _grounding_payload(borrower_report):
    """Compact, LLM-friendly JSON containing ONLY the fields the model is
    allowed to reason from."""
    r = borrower_report
    return {
        "name": r["name"],
        "archetype": r["archetype"],
        "condition": r["condition"],
        "classification_confidence": r.get("classification_confidence"),
        "risk_score": r["risk_score"],
        "affordability_score": r["affordability_score"],
        "financial_health_score": r.get("financial_health", {}).get("score"),
        "loan_principal": r.get("loan", {}).get("principal"),
        "loan_installment": r.get("loan", {}).get("installment"),
        "loan_tenure": r.get("loan", {}).get("tenure_months"),
        "evidence_chain": r.get("evidence_chain", []),
        "forecast_method": r.get("forecast", {}).get("method"),
        "recommended_plan": r.get("repayment_plan", {}).get("strategy")
                             or r.get("repayment_plan", {}).get("name"),
        "recommended_actions": r.get("repayment_plan", {}).get("actions", []),
        "warnings": r.get("warnings", []),
        "comparison_narrative": r.get("comparison_narrative", {}),
    }


NARRATIVE_SYSTEM_PROMPT = """You are a careful microfinance analyst assistant.
You explain loan repayment decisions to lenders and borrowers in plain language.

STRICT RULES:
- You will be given a JSON object called DATA. It contains the ONLY numbers
  and facts you are allowed to use.
- Do not invent, estimate, round unusually, or introduce any number, date,
  or amount that is not present in DATA.
- Do not diagnose the borrower's mental state, personal circumstances, or
  reasons beyond what DATA states.
- Never claim a temporary/seasonal dip is permanent decline unless DATA's
  condition field literally says "structural_decline".
- Keep it to 4-6 short sentences: what's happening, why (cite the evidence
  chain), and what is recommended.
- Plain text only, no markdown headers, no bullet symbols.
"""


def generate_narrative(borrower_report, model=DEFAULT_MODEL, host=DEFAULT_HOST):
    """Returns dict: {text, grounded: bool, unverified_numbers: list,
    source: 'gemma' | 'template'}."""
    payload = _grounding_payload(borrower_report)
    source_numbers = _collect_source_numbers(borrower_report)

    prompt = f"DATA:\n{json.dumps(payload, indent=2)}\n\nWrite the explanation now."

    try:
        text = ollama_generate(prompt, system=NARRATIVE_SYSTEM_PROMPT, model=model, host=host)
        if not text:
            raise OllamaUnavailable("empty response")
        ok, unverified = verify_grounding(text, source_numbers)
        if not ok:
            retry_prompt = (
                prompt
                + f"\n\nYour previous draft mentioned these numbers that are NOT in DATA: {unverified}. "
                  "Rewrite the explanation using ONLY numbers copied exactly from DATA."
            )
            text2 = ollama_generate(retry_prompt, system=NARRATIVE_SYSTEM_PROMPT, model=model, host=host)
            ok2, unverified2 = verify_grounding(text2, source_numbers)
            if ok2:
                return {"text": text2, "grounded": True, "unverified_numbers": [], "source": "gemma"}
            return {
                "text": _template_narrative(borrower_report),
                "grounded": True,
                "unverified_numbers": unverified2,
                "source": "template_fallback",
                "discarded_llm_draft": text2,
            }
        return {"text": text, "grounded": True, "unverified_numbers": [], "source": "gemma"}
    except OllamaUnavailable:
        return {"text": _template_narrative(borrower_report), "grounded": True,
                "unverified_numbers": [], "source": "template_fallback"}


def _template_narrative(r):
    """Deterministic, always-available fallback built directly from the
    evidence chain — zero LLM dependency, zero hallucination risk."""
    ev = " ".join(r.get("evidence_chain", [])[:3])
    plan = r.get("repayment_plan", {}).get("strategy") or r.get("repayment_plan", {}).get("name") or "the recommended plan"
    cond = r.get('condition', 'stable').replace('_', ' ')
    return (
        f"{r['name']} is currently classified under the '{cond}' trajectory "
        f"with a risk score of {r['risk_score']}/100 and an affordability score of {r['affordability_score']}/100. "
        f"{ev} Recommended course of action: {plan}."
    )


# ---------------------------------------------------------------------------
# 2. Interactive Gemma Loan Copilot & Q&A
# ---------------------------------------------------------------------------

COPILOT_SYSTEM_PROMPT = """You are Gemma Loan Copilot, an expert AI credit risk and loan restructuring assistant.
You help lenders and borrowers understand cash flow metrics, risk scores, forecast uncertainty, and restructuring recommendations.

STRICT RULES:
- Base your answers ONLY on the provided BORROWER DATA JSON.
- Never invent numbers or loan parameters.
- Provide clear, professional, and actionable insights.
- Format responses cleanly with bolding and concise bullet points.
"""


def ask_gemma_copilot(borrower_report, user_question, model=DEFAULT_MODEL, host=DEFAULT_HOST):
    """Ask Gemma a specific question about a borrower or prediction."""
    payload = _grounding_payload(borrower_report)
    prompt = f"BORROWER DATA:\n{json.dumps(payload, indent=2)}\n\nUSER QUESTION:\n{user_question}\n\nAnswer:"

    try:
        answer = ollama_generate(prompt, system=COPILOT_SYSTEM_PROMPT, model=model, host=host, temperature=0.3)
        if answer:
            return {"answer": answer, "source": "gemma"}
    except OllamaUnavailable:
        pass

    # Intelligent deterministic fallback for Q&A when Ollama is offline
    q = user_question.lower()
    name = borrower_report["name"]
    cond = borrower_report["condition"].replace("_", " ")
    risk = borrower_report["risk_score"]
    aff = borrower_report["affordability_score"]
    health = borrower_report.get("financial_health", {}).get("score", "N/A")
    plan = borrower_report.get("repayment_plan", {}).get("strategy", "keep_current_plan")
    ev = borrower_report.get("evidence_chain", [])

    if "why" in q or "reason" in q or "recommend" in q:
        actions = " ".join(borrower_report.get("repayment_plan", {}).get("actions", []))
        return {
            "answer": f"**Decision Rationale for {name}:**\n\n"
                      f"• **Classification:** `{cond.upper()}` (Risk Score: **{risk}/100**, Affordability: **{aff}/100**).\n"
                      f"• **Evidence:** {ev[0] if ev else ''}\n"
                      f"• **Why this plan:** {actions or 'Cash-flow dynamics justify this dynamic structure to prevent default.'}",
            "source": "grounded_rule_engine"
        }
    elif "risk" in q or "default" in q or "score" in q:
        return {
            "answer": f"**Risk Assessment for {name}:**\n\n"
                      f"• **Risk Score:** **{risk}/100** ({'High Default Risk' if risk >= 60 else ('Moderate Risk' if risk >= 35 else 'Low Default Risk')}).\n"
                      f"• **Financial Health:** **{health}/100**.\n"
                      f"• **Stress Breaches:** {ev[1] if len(ev) > 1 else 'No major buffer breaches observed.'}",
            "source": "grounded_rule_engine"
        }
    elif "draft" in q or "notice" in q or "term sheet" in q or "letter" in q:
        return {
            "answer": f"### Formal Loan Restructuring Term Sheet\n\n"
                      f"**Borrower:** {name}  \n"
                      f"**Original Principal:** Rs.{borrower_report.get('loan', {}).get('principal', 0):,}  \n"
                      f"**Current Fixed EMI:** Rs.{borrower_report.get('loan', {}).get('installment', 0):,}/month  \n"
                      f"**Approved Dynamic Strategy:** `{plan}`  \n\n"
                      f"**Underwriting Justification:**  \n"
                      f"Based on 24-month cash-flow verification, {name} demonstrates a `{cond}` pattern. "
                      f"The restructuring plan adjusts payment timings to optimize lender recovery while preserving borrower liquidity.",
            "source": "grounded_rule_engine"
        }
    else:
        return {
            "answer": f"**Analysis Summary for {name}:**\n\n"
                      f"• **Condition:** `{cond.title()}` | **Health Score:** {health}/100 | **Risk:** {risk}/100\n"
                      f"• **Key Metrics:** {ev[0] if ev else ''}\n"
                      f"• **Recommended Action:** {plan.replace('_', ' ').title()}.",
            "source": "grounded_rule_engine"
        }


# ---------------------------------------------------------------------------
# 3. Structured extraction from pasted / uploaded free-text financial data
# ---------------------------------------------------------------------------

EXTRACTION_SYSTEM_PROMPT = """You extract structured monthly financial data from
messy pasted text (payslips, bank statement summaries, handwritten notes typed
up by the user). Output ONLY valid JSON, nothing else, no markdown fences.

Schema:
{
  "months": [
    {"month": 1, "income": <number>, "expenses": <number>}
  ]
}

Rules:
- If a value is missing or unclear, use null rather than guessing.
- Never fabricate a month that doesn't appear in the text.
- Numbers only, no currency symbols or commas in the output values.
"""


def extract_financial_records(raw_text, model=DEFAULT_MODEL, host=DEFAULT_HOST):
    """Returns (records: list[dict] | None, error: str | None)."""
    try:
        text = ollama_generate(raw_text, system=EXTRACTION_SYSTEM_PROMPT, model=model, host=host, temperature=0.0)
        cleaned = re.sub(r"^```(json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
        data = json.loads(cleaned)
        months = data.get("months", [])
        clean_months = []
        for m in months:
            inc, exp = m.get("income"), m.get("expenses")
            if inc is None or exp is None:
                continue
            clean_months.append({"month": m.get("month"), "income": float(inc), "expenses": float(exp)})
        if not clean_months:
            return None, "Gemma returned no valid month rows. Check the pasted text or enter data manually."
        return clean_months, None
    except OllamaUnavailable as e:
        # Fallback regex extractor for simple tabular text
        lines = raw_text.strip().split("\n")
        records = []
        for i, line in enumerate(lines):
            nums = re.findall(r"\d+(?:\.\d+)?", line.replace(",", ""))
            if len(nums) >= 2:
                records.append({"month": i + 1, "income": float(nums[0]), "expenses": float(nums[1])})
        if records:
            return records, None
        return None, f"Ollama unavailable and unable to parse text via regex: {e}"
    except (json.JSONDecodeError, ValueError, TypeError) as e:
        return None, f"Could not parse Gemma's output as structured data: {e}"
