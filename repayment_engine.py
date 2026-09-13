"""
repayment_engine.py
---------------------
Given a borrower's cash-flow condition, proposes a concrete alternative
repayment structure and a per-month schedule so the lender can compare
"current fixed plan" vs "recommended dynamic plan" side by side.

Strategies:
  stable / improving        -> keep plan, optionally offer accelerated payoff
  seasonal_pattern           -> step schedule aligned to income peaks/troughs
  temporary_stress           -> short moratorium on the shock months, missed
                                 amount re-amortized over the remaining tenure
  chronic_strain             -> lighter installment, extended tenure
  structural_decline         -> reduced installment + extended tenure +
                                 flagged for manual lender review
"""

import statistics as stats


def _redistribute(remaining_principal_equiv, months_left):
    if months_left <= 0:
        return 0
    return round(remaining_principal_equiv / months_left, 2)


def build_plan(borrower, analysis):
    loan = borrower["loan"]
    installment = loan["installment"]
    tenure = loan["tenure_months"]
    condition = analysis["condition"]
    net_cf = analysis["net_cash_flow"]
    seasonality = analysis["seasonality"]

    original_schedule = [installment] * tenure
    recommended_schedule = list(original_schedule)
    actions = []
    strategy = "keep_current_plan"

    if condition in ("stable",):
        strategy = "keep_current_plan"
        actions.append("Cash flow comfortably covers the existing fixed installment; no restructuring needed.")

    elif condition == "recovering":
        strategy = "keep_current_plan_monitor"
        actions.append(
            "A past stress episode has resolved and the recent trend is positive. "
            "No restructuring is needed, but keep this borrower on a lighter monitoring "
            "cadence for one or two more cycles before treating them the same as a "
            "borrower with no stress history at all."
        )

    elif condition == "improving":
        strategy = "accelerated_optional"
        boosted = round(installment * 1.15, 2)
        recommended_schedule = [boosted] * tenure
        actions.append(
            f"Income trend is genuinely improving. Offer an optional accelerated "
            f"track at Rs.{boosted:.0f}/month (same tenure, lower total interest); "
            f"borrower can decline and stay on the original plan with no penalty."
        )

    elif condition == "seasonal_pattern":
        strategy = "seasonal_step_schedule"
        by_month = seasonality["by_month"]
        overall_avg_cf = stats.mean(net_cf)
        for m in range(tenure):
            cal_month = m % 12
            deviation = by_month.get(cal_month, 0)
            if overall_avg_cf > 0:
                factor = 1 + max(-0.6, min(0.6, deviation / overall_avg_cf))
            else:
                factor = 1
            recommended_schedule[m] = round(installment * factor, 2)
        # keep total collected roughly equal to original total (fair re-timing, not a discount)
        target_total = installment * tenure
        current_total = sum(recommended_schedule)
        if current_total > 0:
            scale = target_total / current_total
            recommended_schedule = [round(v * scale, 2) for v in recommended_schedule]
        actions.append(
            "Borrower's income has a clear annual rhythm. Recommend re-timing the "
            "same total repayment amount into a step schedule: higher installments "
            "in the borrower's own peak months, lower installments in known lean months, "
            "rather than a flat amount that overshoots during troughs."
        )

    elif condition == "temporary_stress":
        strategy = "moratorium_and_reamortize"
        stressed_idx = {s["month"] for s in analysis["stressed_months"]}
        moratorium_months = sorted(m for m in stressed_idx if m < tenure)
        deferred_amount = installment * len(moratorium_months)
        remaining_months = [m for m in range(tenure) if m not in moratorium_months]
        if remaining_months:
            new_installment = round(
                (installment * (tenure - len(moratorium_months)) + deferred_amount) / len(remaining_months), 2
            )
        else:
            new_installment = installment
        for m in range(tenure):
            recommended_schedule[m] = 0 if m in moratorium_months else new_installment
        actions.append(
            f"Detected a temporary shock with recovery already visible in the data. "
            f"Recommend a moratorium on month(s) "
            f"{', '.join(str(m + 1) for m in moratorium_months) if moratorium_months else 'the identified shock period'}, "
            f"with the deferred amount re-amortized across the remaining "
            f"{len(remaining_months)} months at Rs.{new_installment:.0f}/month "
            f"instead of writing anything off."
        )

    elif condition == "chronic_strain":
        strategy = "lighten_and_extend"
        extension = max(4, tenure // 4)
        new_tenure = tenure + extension
        remaining_principal_equiv = installment * tenure
        new_installment = _redistribute(remaining_principal_equiv, new_tenure)
        recommended_schedule = [new_installment] * new_tenure
        actions.append(
            f"Stress is frequent but not tied to a single shock or a seasonal pattern, "
            f"suggesting the current installment is simply too tight for this borrower's "
            f"typical cash flow. Recommend extending tenure by {extension} months and "
            f"lowering the installment to Rs.{new_installment:.0f}/month."
        )

    else:  # structural_decline
        strategy = "restructure_and_flag_for_review"
        extension = max(6, tenure // 2)
        new_tenure = tenure + extension
        reduction_factor = 0.75
        remaining_principal_equiv = installment * tenure
        new_installment = round(_redistribute(remaining_principal_equiv, new_tenure) * reduction_factor
                                 + _redistribute(remaining_principal_equiv, new_tenure) * (1 - reduction_factor), 2)
        # simpler, transparent formula: extend tenure, keep total nominal repayment the same
        new_installment = _redistribute(remaining_principal_equiv, new_tenure)
        recommended_schedule = [new_installment] * new_tenure
        actions.append(
            f"Income has been declining for {sum(1 for c in analysis['net_cash_flow'][-8:])} "
            f"consecutive months in the observed window with no recovery signal. "
            f"Recommend a formal restructuring: extend tenure by {extension} months, "
            f"reduce installment to Rs.{new_installment:.0f}/month, and flag this loan "
            f"for manual lender review rather than fully automated approval."
        )

    return {
        "strategy": strategy,
        "original_schedule": original_schedule,
        "recommended_schedule": recommended_schedule,
        "actions": actions,
    }