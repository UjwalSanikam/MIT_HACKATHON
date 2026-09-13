"""
scenario_engine.py
---------------------
Builds and scores the repayment-strategy comparison table (Feature 1 & 2):

    Strategy A - Fixed            : the current flat installment
    Strategy B - Seasonal step    : higher in the borrower's own peak
                                     months, lower in lean months, same
                                     total collected as the fixed plan
    Strategy C - Income-linked    : payment = pct * disposable cash,
                                     clamped to [min, max] x installment
                                     (mirrors the dashboard's live
                                     what-if slider defaults exactly)
    Strategy D - Temporary relief : cut payments in the borrower's own
                                     historical stress months, recover the
                                     deferred amount over the remaining
                                     months
    Strategy E - Grace/moratorium : zero payment during the single worst
                                     stress episode, deferred amount
                                     re-amortized afterwards. Evaluated
                                     for every borrower, but only ever
                                     picked as the optimizer's top choice
                                     when the evidence (condition +
                                     stress severity) actually justifies
                                     it.

Every strategy is simulated against the borrower's OWN historical net
cash flow (the same ground truth the rest of the system reasons from),
so "how would this schedule have performed" is directly comparable
across strategies and never hand-tuned per borrower.
"""

import statistics as stats

# Income-linked defaults - kept identical to the dashboard's live
# what-if slider defaults (see dashboard/app.js: simulateIncomeLinked)
# so the two never silently disagree.
INCOME_LINKED_PCT = 0.35
INCOME_LINKED_MIN_RATIO = 0.50
INCOME_LINKED_MAX_RATIO = 1.60
SAFETY_BUFFER_PCT = 0.10

OPTIMIZER_WEIGHTS = {"sustainability": 0.45, "recovery": 0.35, "stability": 0.20}

# Grace/moratorium is only eligible to be the top pick when the
# borrower's condition is one where a payment holiday is actually
# defensible evidence-wise - never just because its raw score is
# highest.
GRACE_ELIGIBLE_CONDITIONS = {"temporary_stress", "structural_decline", "chronic_strain"}


def _clamp(x, lo=0.0, hi=100.0):
    return max(lo, min(hi, x))


def _simulate(schedule, net_cf, installment, tenure_months, buffer_pct=SAFETY_BUFFER_PCT):
    """Run one repayment schedule against the borrower's historical net
    cash flow and return the metrics shown in the comparison table."""
    n = min(len(schedule), len(net_cf))
    stressed = 0
    worst = None
    recoverable = 0.0
    scheduled_total = 0.0

    for i in range(n):
        cf = net_cf[i]
        pay = schedule[i]
        scheduled_total += pay
        remaining = cf - pay
        worst = remaining if worst is None else min(worst, remaining)
        buffer_needed = cf * buffer_pct if cf > 0 else 0
        if remaining < buffer_needed:
            stressed += 1
        recoverable += min(pay, max(0.0, cf))

    original_total = installment * tenure_months
    recovery_pct = round((recoverable / original_total) * 100, 1) if original_total else 100.0
    avg_payment = round(scheduled_total / n, 2) if n else 0.0
    stdev_payment = stats.pstdev(schedule[:n]) if n > 1 else 0.0
    cv_payment = (stdev_payment / avg_payment) if avg_payment else 0.0

    stress_ratio = (stressed / n) if n else 0.0
    sustainability_score = _clamp(100 - stress_ratio * 100)
    stability_score = _clamp(100 - cv_payment * 100)
    recovery_score = _clamp(recovery_pct)

    weighted = round(
        OPTIMIZER_WEIGHTS["sustainability"] * sustainability_score
        + OPTIMIZER_WEIGHTS["recovery"] * recovery_score
        + OPTIMIZER_WEIGHTS["stability"] * stability_score,
        1,
    )

    if stress_ratio == 0:
        sustainability_label = "High"
    elif stress_ratio <= 0.15:
        sustainability_label = "High"
    elif stress_ratio <= 0.35:
        sustainability_label = "Medium"
    else:
        sustainability_label = "Low"

    return {
        "avg_payment": avg_payment,
        "worst_cash_buffer": round(worst, 2) if worst is not None else 0.0,
        "stress_months": stressed,
        "recovery_pct": recovery_pct,
        "sustainability_label": sustainability_label,
        "schedule": [round(v, 2) for v in schedule],
        "scores": {
            "sustainability": round(sustainability_score, 1),
            "recovery": round(recovery_score, 1),
            "stability": round(stability_score, 1),
            "weighted": weighted,
        },
    }


def _fixed_schedule(installment, tenure):
    return [installment] * tenure


def _seasonal_schedule(installment, tenure, seasonality, net_cf):
    by_month = seasonality["by_month"]
    overall_avg_cf = stats.mean(net_cf) if net_cf else 0
    schedule = []
    for m in range(tenure):
        cal_month = m % 12
        deviation = by_month.get(cal_month, 0)
        factor = 1 + max(-0.6, min(0.6, deviation / overall_avg_cf)) if overall_avg_cf > 0 else 1
        schedule.append(installment * factor)
    target_total = installment * tenure
    current_total = sum(schedule)
    if current_total > 0:
        scale = target_total / current_total
        schedule = [v * scale for v in schedule]
    return schedule


def _income_linked_schedule(installment, net_cf, tenure,
                             pct=INCOME_LINKED_PCT,
                             min_ratio=INCOME_LINKED_MIN_RATIO,
                             max_ratio=INCOME_LINKED_MAX_RATIO):
    min_pay = installment * min_ratio
    max_pay = installment * max_ratio
    schedule = []
    for m in range(tenure):
        cf = net_cf[m] if m < len(net_cf) else net_cf[m % len(net_cf)]
        disposable = max(0.0, cf)
        raw = disposable * pct
        schedule.append(min(max_pay, max(min_pay, raw)))
    return schedule


def _relief_schedule(installment, tenure, stressed_months, relief_ratio=0.5):
    """Cut payment to `relief_ratio` x installment in the borrower's own
    historically stressed months, and recover exactly the deferred
    amount by spreading it evenly across the remaining months, so the
    lender still collects the same total over the tenure."""
    stressed_idx = {s["month"] for s in stressed_months if s["month"] < tenure}
    schedule = [installment] * tenure
    deferred = 0.0
    for m in stressed_idx:
        reduced = installment * relief_ratio
        deferred += installment - reduced
        schedule[m] = reduced
    remaining_months = [m for m in range(tenure) if m not in stressed_idx]
    if remaining_months and deferred > 0:
        top_up = deferred / len(remaining_months)
        for m in remaining_months:
            schedule[m] += top_up
    return schedule


def _grace_schedule(installment, tenure, stress_clusters, max_grace_months=3):
    """Zero payment during the single worst (longest) stress episode, up
    to `max_grace_months`, with the deferred amount re-amortized evenly
    across the rest of the tenure."""
    schedule = [installment] * tenure
    if not stress_clusters:
        return schedule
    worst = max(stress_clusters, key=lambda c: c["length"])
    grace_months = [m for m in range(worst["start"], worst["end"] + 1) if m < tenure][:max_grace_months]
    if not grace_months:
        return schedule
    deferred = installment * len(grace_months)
    for m in grace_months:
        schedule[m] = 0.0
    remaining_months = [m for m in range(tenure) if m not in grace_months]
    if remaining_months:
        top_up = deferred / len(remaining_months)
        for m in remaining_months:
            schedule[m] += top_up
    return schedule


def build_scenarios(borrower, analysis):
    loan = borrower["loan"]
    installment = loan["installment"]
    tenure = loan["tenure_months"]
    net_cf = analysis["net_cash_flow"]
    seasonality = analysis["seasonality"]
    stressed_months = analysis["stressed_months"]
    stress_clusters = analysis.get("stress_clusters", [])
    condition = analysis["condition"]

    raw_schedules = {
        "fixed": ("Current Fixed Plan", _fixed_schedule(installment, tenure)),
        "seasonal": ("Seasonal Step Schedule", _seasonal_schedule(installment, tenure, seasonality, net_cf)),
        "income_linked": ("Income-Linked Repayment", _income_linked_schedule(installment, net_cf, tenure)),
        "relief": ("Temporary Relief", _relief_schedule(installment, tenure, stressed_months)),
        "grace": ("Grace / Moratorium", _grace_schedule(installment, tenure, stress_clusters)),
    }

    strategies = {}
    for key, (label, schedule) in raw_schedules.items():
        metrics = _simulate(schedule, net_cf, installment, tenure)
        metrics["label"] = label
        strategies[key] = metrics

    # Pick the optimizer's top choice by weighted score, with grace
    # excluded unless the borrower's condition actually justifies a
    # payment holiday (Feature 1: "only recommend this when justified").
    candidates = {
        k: v for k, v in strategies.items()
        if k != "grace" or condition in GRACE_ELIGIBLE_CONDITIONS
    }
    optimizer_pick = max(candidates, key=lambda k: candidates[k]["scores"]["weighted"])

    return {
        "strategies": strategies,
        "optimizer_pick": optimizer_pick,
        "weights": OPTIMIZER_WEIGHTS,
    }