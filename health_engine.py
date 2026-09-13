"""
health_engine.py
------------------
Everything in this module turns the cash-flow analysis into scores and
messages meant to be read directly by a human (lender or borrower):

  - financial_health_score(): a 0-100 composite, broken into named
    components, deliberately framed as a decision-support score rather
    than a credit score
  - repayment_stress_index(): a single 0-100 "how hard is the CURRENT
    schedule relative to this borrower's cash flow" number, banded into
    plain-language severity
  - classification_confidence(): how much the system should trust its own
    condition label, given how much evidence supports it
  - build_warnings(): a short list of concrete, evidence-cited early
    warning signals with a severity and a recommended action
  - intervention_for_condition(): the one-line policy mapping from
    condition -> recommended type of intervention
"""

import statistics as stats

HEALTH_WEIGHTS = {
    "cash_flow_stability": 0.20,
    "repayment_coverage": 0.20,
    "cash_buffer": 0.15,
    "income_trend": 0.15,
    "expense_pressure": 0.15,
    "recovery_capacity": 0.15,
}

INTERVENTIONS = {
    "stable": ("Maintain current plan",
               "Cash flow comfortably supports the existing schedule; no action needed."),
    "improving": ("Offer optional accelerated track",
                  "Genuine upward trend; borrower may benefit from paying down faster, but this must stay optional."),
    "recovering": ("Keep current plan, monitor",
                   "Past stress has resolved and the trend is positive; no restructuring needed, just a lighter watch."),
    "seasonal_pattern": ("Switch to seasonal repayment schedule",
                         "Align installment size to the borrower's own recurring income cycle instead of a flat amount."),
    "temporary_stress": ("Temporary payment reduction / moratorium",
                         "Shock appears one-off with recovery already visible; bridge the borrower, don't restructure permanently."),
    "chronic_strain": ("Lighten and extend the plan",
                       "Recurring, non-seasonal strain suggests the installment itself is too tight for typical cash flow."),
    "structural_decline": ("Formal restructuring + manual review",
                           "Persistent deterioration with no recovery signal; needs human underwriting judgment, not an automated rule."),
}


def _clamp(x, lo=0.0, hi=100.0):
    return max(lo, min(hi, x))


def financial_health_score(borrower, analysis):
    net_cf = analysis["net_cash_flow"]
    income = borrower["income"]
    expenses = borrower["expenses"]
    installment = borrower["loan"]["installment"]
    trend = analysis["trend"]
    clusters = analysis.get("stress_clusters", [])

    mean_cf = stats.mean(net_cf) if net_cf else 0
    stdev_cf = stats.pstdev(net_cf) if len(net_cf) > 1 else 0

    # 1. Cash-flow stability: inverse of coefficient of variation
    cv = (stdev_cf / mean_cf) if mean_cf > 0 else 1.5
    cash_flow_stability = _clamp(100 - cv * 90)

    # 2. Repayment coverage: how many multiples of the installment the
    #    average cash flow represents
    coverage_ratio = (mean_cf / installment) if installment else 0
    repayment_coverage = _clamp(min(1.0, coverage_ratio / 2.0) * 100)

    # 3. Cash buffer: average remaining cash after installment, relative
    #    to the installment itself
    remaining = [cf - installment for cf in net_cf]
    avg_remaining_ratio = (stats.mean(remaining) / installment) if installment else 0
    cash_buffer = _clamp(50 + avg_remaining_ratio * 60)

    # 4. Income trend: pct_change mapped around a neutral midpoint of 50
    income_trend = _clamp(50 + trend["pct_change"] * 1.4)

    # 5. Expense pressure: compare expense trend to income trend (a rough
    #    proxy using overall means of first vs second half)
    half = len(expenses) // 2 or 1
    inc_growth = (stats.mean(income[half:]) - stats.mean(income[:half])) / (stats.mean(income[:half]) or 1)
    exp_growth = (stats.mean(expenses[half:]) - stats.mean(expenses[:half])) / (stats.mean(expenses[:half]) or 1)
    expense_pressure = _clamp(70 - (exp_growth - inc_growth) * 150)

    # 6. Recovery capacity: did the borrower bounce back after their most
    #    recent stress episode, and how long ago did it resolve?
    if clusters:
        last = clusters[-1]
        distance_from_end = (len(net_cf) - 1) - last["end"]
        recovered_bonus = 30 if trend["recovering"] else 0
        distance_bonus = min(40, distance_from_end * 4)
        recovery_capacity = _clamp(30 + recovered_bonus + distance_bonus)
    else:
        recovery_capacity = 85.0  # no stress episodes to recover from

    breakdown = {
        "cash_flow_stability": round(cash_flow_stability, 1),
        "repayment_coverage": round(repayment_coverage, 1),
        "cash_buffer": round(cash_buffer, 1),
        "income_trend": round(income_trend, 1),
        "expense_pressure": round(expense_pressure, 1),
        "recovery_capacity": round(recovery_capacity, 1),
    }
    overall = sum(breakdown[k] * HEALTH_WEIGHTS[k] for k in HEALTH_WEIGHTS)

    return {
        "score": round(overall, 1),
        "breakdown": breakdown,
        "weights": HEALTH_WEIGHTS,
    }


def repayment_stress_index(analysis, installment):
    net_cf = analysis["net_cash_flow"]
    stressed = analysis["stressed_months"]
    clusters = analysis.get("stress_clusters", [])
    seasonality = analysis["seasonality"]

    mean_cf = stats.mean(net_cf) if net_cf else 0
    stdev_cf = stats.pstdev(net_cf) if len(net_cf) > 1 else 0

    load_component = _clamp((installment / mean_cf) * 45, 0, 45) if mean_cf > 0 else 45
    frequency_component = _clamp((len(stressed) / len(net_cf)) * 25, 0, 25) if net_cf else 0
    severity_component = 0
    if stressed:
        avg_shortfall_ratio = stats.mean(s["shortfall"] for s in stressed) / installment if installment else 0
        severity_component = _clamp(avg_shortfall_ratio * 15, 0, 15)
    duration_component = _clamp((max((c["length"] for c in clusters), default=0)) * 3, 0, 10)
    volatility_component = _clamp((stdev_cf / mean_cf) * 5, 0, 5) if mean_cf > 0 else 5

    index = load_component + frequency_component + severity_component + duration_component + volatility_component
    index = round(_clamp(index, 0, 100), 1)

    if index < 20:
        band = "Very Low"
    elif index < 40:
        band = "Low"
    elif index < 60:
        band = "Moderate"
    elif index < 80:
        band = "High"
    else:
        band = "Severe"

    return {
        "index": index,
        "band": band,
        "components": {
            "installment_load": round(load_component, 1),
            "stress_frequency": round(frequency_component, 1),
            "shortfall_severity": round(severity_component, 1),
            "stress_duration": round(duration_component, 1),
            "volatility": round(volatility_component, 1),
        },
        "seasonal_mismatch": bool(seasonality["is_seasonal"] and len(stressed) > 0),
    }


def classification_confidence(analysis):
    """A prototype confidence estimate for the condition label - explicitly
    NOT a statistical p-value. Rewards more history, a clean/consistent
    pattern, and strong seasonal correlation where relevant; penalizes thin
    or ambiguous evidence."""
    net_cf = analysis["net_cash_flow"]
    seasonality = analysis["seasonality"]
    clusters = analysis.get("stress_clusters", [])
    condition = analysis["condition"]
    trend = analysis["trend"]

    data_length_score = min(30, len(net_cf) / 24 * 30)

    if condition == "seasonal_pattern":
        pattern_score = seasonality["year_over_year_correlation"] * 40
    elif condition in ("temporary_stress", "chronic_strain", "structural_decline"):
        pattern_score = 30 if clusters else 15
        if condition == "structural_decline":
            pattern_score += _clamp(abs(trend["pct_change"]) - 15, 0, 15)
    else:
        pattern_score = 25 if trend["recovering"] or condition == "stable" else 15

    consistency_score = 20 if (clusters and len(clusters) >= 1) or condition in ("stable", "improving") else 12
    ambiguity_penalty = 10 if (seasonality["is_seasonal"] and condition != "seasonal_pattern") else 0

    raw = data_length_score + pattern_score + consistency_score - ambiguity_penalty
    return round(_clamp(raw, 5, 97), 1)


def build_warnings(borrower, analysis):
    net_cf = analysis["net_cash_flow"]
    income = borrower["income"]
    expenses = borrower["expenses"]
    installment = borrower["loan"]["installment"]
    stressed_idx = {s["month"] for s in analysis["stressed_months"]}
    trend = analysis["trend"]
    seasonality = analysis["seasonality"]
    warnings = []

    # consecutive income decline (last 3 months)
    if len(income) >= 4:
        recent = income[-4:]
        if all(recent[i] > recent[i + 1] for i in range(len(recent) - 1)):
            warnings.append({
                "severity": "HIGH",
                "message": "Income has declined for 3 consecutive months.",
                "evidence": f"Income fell each month from Rs.{recent[0]:.0f} to Rs.{recent[-1]:.0f}.",
                "action": "Review whether this is a new shock; avoid assuming recovery without evidence.",
            })

    # repayment coverage below 1.0 recently
    recent_cf = net_cf[-3:]
    if recent_cf and all(cf < installment for cf in recent_cf):
        warnings.append({
            "severity": "HIGH",
            "message": "Repayment coverage has been below 1.0 for the last 3 months.",
            "evidence": f"Net cash flow averaged Rs.{stats.mean(recent_cf):.0f} against an installment of Rs.{installment:.0f}.",
            "action": "Consider temporary repayment relief before the borrower misses a payment.",
        })

    # two consecutive stressed months at the tail
    last_two = [len(net_cf) - 2, len(net_cf) - 1]
    if all(m in stressed_idx for m in last_two):
        warnings.append({
            "severity": "MEDIUM",
            "message": "The two most recent months both breached the safety buffer.",
            "evidence": "Both of the last two observed months required dipping below the 10% safety buffer.",
            "action": "Flag for early outreach before the next installment is due.",
        })

    # cash buffer approaching zero
    if net_cf:
        last_buffer = net_cf[-1] - installment
        if 0 <= last_buffer < installment * 0.1:
            warnings.append({
                "severity": "MEDIUM",
                "message": "Cash buffer after the last installment is near zero.",
                "evidence": f"Only Rs.{last_buffer:.0f} remained after paying the installment in the most recent month.",
                "action": "Monitor closely; a small additional expense could push this borrower into shortfall.",
            })

    # expenses growing faster than income
    half = len(expenses) // 2 or 1
    inc_growth = (stats.mean(income[half:]) - stats.mean(income[:half])) / (stats.mean(income[:half]) or 1)
    exp_growth = (stats.mean(expenses[half:]) - stats.mean(expenses[:half])) / (stats.mean(expenses[:half]) or 1)
    if exp_growth - inc_growth > 0.08:
        warnings.append({
            "severity": "MEDIUM",
            "message": "Expenses are growing faster than income.",
            "evidence": f"Expenses grew {exp_growth*100:.1f}% vs income growth of {inc_growth*100:.1f}% (first half vs second half of the window).",
            "action": "Watch for margin compression even if current cash flow still covers the installment.",
        })

    # informational: seasonal downturn
    if seasonality["is_seasonal"]:
        by_month = seasonality["by_month"]
        low_month = min(by_month, key=by_month.get)
        warnings.append({
            "severity": "INFO",
            "message": f"Seasonal downturn expected around calendar month {low_month + 1}.",
            "evidence": f"This borrower's income has historically run Rs.{abs(by_month[low_month]):.0f} below average in that month.",
            "action": "This is an expected pattern, not a new risk signal - a seasonal schedule already accounts for it.",
        })

    # positive: recovery detected
    if trend["recovering"] and trend["pct_change"] < 0:
        warnings.append({
            "severity": "GOOD",
            "message": "Recent cash flow shows signs of recovery after a dip.",
            "evidence": f"The second half of the recent window improved over the first half despite an overall {trend['pct_change']}% dip vs baseline.",
            "action": "No restructuring needed beyond bridging the already-resolving dip.",
        })

    severity_order = {"HIGH": 0, "MEDIUM": 1, "INFO": 2, "GOOD": 3}
    warnings.sort(key=lambda w: severity_order.get(w["severity"], 9))
    return warnings


def intervention_for_condition(condition):
    title, reason = INTERVENTIONS.get(condition, ("Manual review", "Condition not recognized by the automated mapping."))
    return {"title": title, "reason": reason}


def why_not_current_plan(borrower, analysis, scenarios):
    """Builds the 'why does the fixed schedule fail this borrower' narrative
    (and the mirror-image 'what if we do nothing' comparison), directly from
    the already-computed fixed-plan vs. recommended-plan scenario metrics -
    no separate calculation, so the numbers here can never drift from what's
    shown in the comparison table."""
    fixed = scenarios["strategies"]["fixed"]
    pick_key = scenarios["optimizer_pick"]
    recommended = scenarios["strategies"][pick_key]
    installment = borrower["loan"]["installment"]
    net_cf = analysis["net_cash_flow"]

    if fixed["stress_months"] == 0 or pick_key == "fixed":
        return {
            "current_plan_fails": False,
            "headline": "The current fixed schedule already fits this borrower's cash flow well.",
            "current": fixed,
            "recommended": fixed,
        }

    worst_shortfall = round(installment - fixed["worst_cash_buffer"], 2) if fixed["worst_cash_buffer"] < installment else 0
    repeats = analysis["seasonality"]["is_seasonal"]
    recovers = analysis["trend"]["recovering"]

    reasons = [f"{fixed['stress_months']} of {len(net_cf)} observed months breach the safety buffer under the fixed installment"]
    if worst_shortfall > 0:
        reasons.append(f"the worst month leaves only Rs.{fixed['worst_cash_buffer']:.0f} remaining "
                        f"(a Rs.{worst_shortfall:.0f} shortfall against a safe buffer)")
    if repeats:
        reasons.append("this pattern repeats on a predictable annual cycle rather than being random")
    if recovers:
        reasons.append("cash flow recovers on its own after each stress episode")

    headline = (
        "The borrower appears capable of repaying the loan overall, but the fixed schedule "
        "creates avoidable liquidity stress: " + "; ".join(reasons) + "."
    )

    return {
        "current_plan_fails": True,
        "headline": headline,
        "current": fixed,
        "recommended": recommended,
        "recommended_label": recommended["label"],
        "improvement": {
            "stress_months_before": fixed["stress_months"],
            "stress_months_after": recommended["stress_months"],
            "recovery_before_pct": fixed["recovery_pct"],
            "recovery_after_pct": recommended["recovery_pct"],
        },
    }