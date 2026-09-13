"""
risk_engine.py
---------------
Converts the cash-flow analysis into:
  - an affordability score (can they plausibly sustain the CURRENT plan?)
  - a risk score (how likely is default / how much lender attention needed?)
  - an evidence chain: a short list of concrete, numeric statements that
    justify the score and the condition label. This is the explainability
    layer - every claim below is traced back to a computed statistic, never
    an unexplained black-box number.
"""

import statistics as stats

CONDITION_RISK_WEIGHT = {
    "stable": 0.15,
    "improving": 0.05,
    "recovering": 0.20,
    "seasonal_pattern": 0.30,
    "temporary_stress": 0.40,
    "chronic_strain": 0.65,
    "structural_decline": 0.85,
}


def affordability_score(net_cf, installment):
    """0-100. How comfortably the current fixed installment fits typical
    cash flow, penalized by volatility (a volatile borrower needs more
    headroom on average to be equally 'affordable')."""
    mean_cf = stats.mean(net_cf)
    stdev_cf = stats.pstdev(net_cf) if len(net_cf) > 1 else 0

    if mean_cf <= 0:
        return 0.0

    coverage_ratio = mean_cf / installment  # how many times over they can cover it
    volatility_penalty = min(0.6, (stdev_cf / mean_cf) * 0.5) if mean_cf else 0.6

    raw = min(1.0, coverage_ratio / 2.5) * (1 - volatility_penalty)
    return round(max(0.0, raw) * 100, 1)


def risk_score(condition, stress_ratio, trend_pct_change):
    """0-100, higher = riskier. Blends the qualitative condition with the
    raw stress ratio and trend magnitude so two borrowers in the same
    condition bucket can still be differentiated."""
    base = CONDITION_RISK_WEIGHT.get(condition, 0.5) * 100
    stress_component = stress_ratio * 30
    trend_component = max(0, -trend_pct_change) * 0.4
    score = base + stress_component + trend_component
    return round(min(100, score), 1)


def build_evidence_chain(borrower, analysis):
    """Every bullet here cites an actual number from `analysis`, mirroring
    an evidence-linked reasoning chain rather than a templated verdict."""
    loan = borrower["loan"]
    trend = analysis["trend"]
    seasonality = analysis["seasonality"]
    stressed = analysis["stressed_months"]
    condition = analysis["condition"]

    chain = []

    chain.append(
        f"Average monthly net cash flow (income minus expenses) over the "
        f"observed window is Rs.{stats.mean(analysis['net_cash_flow']):.0f}, "
        f"against a fixed installment of Rs.{loan['installment']:.0f}."
    )

    if stressed:
        months_list = ", ".join(str(s["month"] + 1) for s in stressed[:6])
        more = f" (+{len(stressed) - 6} more)" if len(stressed) > 6 else ""
        chain.append(
            f"{len(stressed)} of {len(analysis['net_cash_flow'])} months "
            f"(month(s) {months_list}{more}) would leave the borrower "
            f"below a safe {int(10)}% cash buffer after paying the current installment."
        )
    else:
        chain.append("No months in the observed window breach the safety buffer under the current installment.")

    net_cf = analysis["net_cash_flow"]
    clusters = analysis.get("stress_clusters", [])

    if condition in ("temporary_stress", "chronic_strain") and clusters:
        c = clusters[-1]
        during = stats.mean(net_cf[c["start"]:c["end"] + 1])
        before_window = net_cf[max(0, c["start"] - 6):c["start"]]
        after_window = net_cf[c["end"] + 1:c["end"] + 7]
        before = stats.mean(before_window) if before_window else None
        after = stats.mean(after_window) if after_window else None
        distance_from_end = (len(net_cf) - 1) - c["end"]

        span = f"months {c['start'] + 1}-{c['end'] + 1}" if c["end"] > c["start"] else f"month {c['start'] + 1}"
        parts = [f"During {span}, average net cash flow fell to Rs.{during:.0f}"]
        if before is not None:
            parts.append(f"down from Rs.{before:.0f} in the months before")
        if after is not None and distance_from_end > 0:
            parts.append(f"and has since averaged Rs.{after:.0f} over the following "
                         f"{min(6, distance_from_end)} month(s)")
        chain.append(", ".join(parts) + ".")

        if condition == "chronic_strain" and len(clusters) > 1:
            chain.append(
                f"This is not an isolated event: {len(clusters)} separate stress episodes "
                f"were detected across the observed window with no single dominant shock, "
                f"suggesting the installment itself is tight relative to typical cash flow."
            )

    elif condition == "structural_decline" and trend["pct_change"] <= -15:
        chain.append(
            f"Recent 6-month average income (Rs.{trend['recent_mean']:.0f}) is "
            f"{abs(trend['pct_change']):.1f}% below the prior 6-month baseline "
            f"(Rs.{trend['baseline_mean']:.0f}), and cash flow has not recovered by the "
            f"end of the observed window, consistent with an ongoing structural decline."
        )

    elif condition == "improving" and trend["pct_change"] >= 10:
        chain.append(
            f"Recent 6-month average income (Rs.{trend['recent_mean']:.0f}) is "
            f"{trend['pct_change']:.1f}% above the prior 6-month baseline "
            f"(Rs.{trend['baseline_mean']:.0f}), indicating genuine growth rather than volatility."
        )

    elif condition == "recovering" and clusters:
        c = clusters[-1]
        distance_from_end = (len(net_cf) - 1) - c["end"]
        chain.append(
            f"A stress episode around month(s) {c['start'] + 1}-{c['end'] + 1} resolved "
            f"{distance_from_end} months ago and has not recurred since, while the recent "
            f"trend is positive ({trend['pct_change']:.1f}% vs. the prior baseline) - this "
            f"reads as genuine recovery, not lingering current-period stress."
        )

    if seasonality["is_seasonal"] and condition == "seasonal_pattern":
        by_month = seasonality["by_month"]
        peak_month = max(by_month, key=by_month.get)
        low_month = min(by_month, key=by_month.get)
        chain.append(
            f"Income shows a recurring annual rhythm: calendar month "
            f"{peak_month + 1} runs Rs.{by_month[peak_month]:.0f} above the borrower's "
            f"own average, while month {low_month + 1} runs Rs.{abs(by_month[low_month]):.0f} "
            f"below it, repeating across the two observed years - this is seasonality, "
            f"not instability."
        )

    condition_label = {
        "stable": "financially stable under the current plan",
        "improving": "on an improving trajectory",
        "recovering": "past a resolved stress episode and now trending positively",
        "seasonal_pattern": "structurally sound but seasonally mismatched to a flat repayment schedule",
        "temporary_stress": "experiencing a temporary shock with signs of recovery",
        "chronic_strain": "under sustained (non-seasonal) strain without a clear one-off cause",
        "structural_decline": "in genuine structural decline with no recovery signal yet",
    }.get(condition, condition)

    chain.append(f"Overall read: this borrower is best classified as '{condition}' - {condition_label}.")

    return chain