"""
cashflow_engine.py
-------------------
Turns raw monthly income/expense series into the signals the rest of the
system reasons about:

  - net cash flow per month (before loan installment)
  - a rolling 3-month average to smooth noise without hiding real shifts
  - a seasonality index per calendar-month-of-year (does this borrower have
    a recurring rhythm, e.g. harvest months?)
  - a trend comparison between the most recent segment and the prior
    baseline segment, used to tell a temporary dip from a structural slide
  - explicit "stress months": months where net cash flow, after the
    existing installment, would go below a safety buffer
"""

import statistics as stats

BUFFER_MONTHS_FOR_TREND = 6  # compare last 6 months vs the 6 before that
SAFETY_BUFFER = 0.10  # borrower should keep >=10% of net cash flow as buffer


def net_cash_flow(income, expenses):
    return [round(i - e, 2) for i, e in zip(income, expenses)]


def rolling_average(series, window=3):
    out = []
    for i in range(len(series)):
        lo = max(0, i - window + 1)
        chunk = series[lo:i + 1]
        out.append(round(sum(chunk) / len(chunk), 2))
    return out


def _pearson(a, b):
    if len(a) != len(b) or len(a) < 2:
        return 0.0
    mean_a, mean_b = stats.mean(a), stats.mean(b)
    num = sum((x - mean_a) * (y - mean_b) for x, y in zip(a, b))
    den_a = math_sqrt(sum((x - mean_a) ** 2 for x in a))
    den_b = math_sqrt(sum((y - mean_b) ** 2 for y in b))
    if den_a == 0 or den_b == 0:
        return 0.0
    return num / (den_a * den_b)


def math_sqrt(x):
    return x ** 0.5


def seasonality_index(series):
    """Average deviation from overall mean, grouped by calendar month (0-11).
    A large spread alone can happen from pure noise with only ~2 samples per
    bucket, so we additionally require that the pattern actually *repeats*
    across the observed years (correlation between year-over-year detrended
    values) before calling it seasonal rather than volatility."""
    overall_mean = stats.mean(series) if series else 0
    buckets = {m: [] for m in range(12)}
    for i, v in enumerate(series):
        buckets[i % 12].append(v - overall_mean)
    index = {m: round(stats.mean(vals), 2) if vals else 0 for m, vals in buckets.items()}
    spread = (max(index.values()) - min(index.values())) if index else 0

    n_years = len(series) // 12
    year_over_year_corr = 0.0
    if n_years >= 2:
        chunks = [series[y * 12:(y + 1) * 12] for y in range(n_years)]
        detrended = [[v - stats.mean(chunk) for v in chunk] for chunk in chunks]
        pairs = [(detrended[i], detrended[i + 1]) for i in range(len(detrended) - 1)]
        corrs = [_pearson(a, b) for a, b in pairs]
        year_over_year_corr = stats.mean(corrs) if corrs else 0.0

    is_seasonal = (
        overall_mean > 0
        and (spread / overall_mean) > 0.30
        and year_over_year_corr > 0.45
    )
    return {
        "by_month": index,
        "spread": round(spread, 2),
        "year_over_year_correlation": round(year_over_year_corr, 2),
        "is_seasonal": bool(is_seasonal),
    }


def trend_shift(series, window=BUFFER_MONTHS_FOR_TREND):
    """Compare the mean of the most recent `window` months against the
    `window` months before that. Returns pct_change and whether the drop
    has *continued* across the whole recent window (structural) vs just a
    short dip inside it that has already started recovering (temporary)."""
    if len(series) < window * 2:
        window = len(series) // 2
    recent = series[-window:]
    baseline = series[-2 * window:-window]
    if not baseline or stats.mean(baseline) == 0:
        return {"pct_change": 0, "recovering": True, "baseline_mean": 0, "recent_mean": 0}

    baseline_mean = stats.mean(baseline)
    recent_mean = stats.mean(recent)
    pct_change = round((recent_mean - baseline_mean) / baseline_mean * 100, 1)

    # Is the second half of the "recent" window higher than the first half?
    # That's the signature of a bounce-back (temporary), vs a flat/falling
    # second half (structural / still deteriorating).
    half = max(1, window // 2)
    first_half_recent = stats.mean(recent[:half])
    second_half_recent = stats.mean(recent[half:]) if recent[half:] else first_half_recent
    recovering = second_half_recent >= first_half_recent * 0.97

    return {
        "pct_change": pct_change,
        "recovering": recovering,
        "baseline_mean": round(baseline_mean, 2),
        "recent_mean": round(recent_mean, 2),
    }


def stress_months(net_cf, installment):
    """Months where paying the fixed installment would eat into the
    borrower's safety buffer (i.e. leave less than SAFETY_BUFFER of their
    own net cash flow, or push them negative)."""
    stressed = []
    for i, cf in enumerate(net_cf):
        remaining = cf - installment
        buffer_needed = cf * SAFETY_BUFFER if cf > 0 else 0
        if remaining < buffer_needed:
            stressed.append({
                "month": i,
                "net_cash_flow": cf,
                "installment": installment,
                "shortfall": round(buffer_needed - remaining, 2),
            })
    return stressed


def stress_clusters(stressed_months, total_months, max_gap=0):
    """Group stressed months into genuinely contiguous episodes (back-to-back
    months only, by default) so we can reason about 'one shock that ended'
    vs 'ongoing strain' rather than treating scattered, non-adjacent tight
    months as if they were a single event."""
    months = sorted(s["month"] for s in stressed_months)
    clusters = []
    for m in months:
        if clusters and m - clusters[-1][-1] <= max_gap + 1:
            clusters[-1].append(m)
        else:
            clusters.append([m])
    return [{"start": c[0], "end": c[-1], "length": c[-1] - c[0] + 1} for c in clusters]


def classify_condition(trend, seasonality, stressed_months, total_months):
    """High-level read on the borrower's financial trajectory. Stress
    clusters are treated as the primary evidence (they're grounded directly
    in "did the installment fit the buffer that month"); the trend and
    seasonality signals disambiguate *why* the cluster happened and whether
    it has resolved."""
    stress_ratio = len(stressed_months) / total_months if total_months else 0
    # a single isolated tight month is normal noise, not a "stress episode" -
    # only clusters of 2+ consecutive/near-consecutive months count as real evidence
    clusters = [c for c in stress_clusters(stressed_months, total_months) if c["length"] >= 2]

    if seasonality["is_seasonal"] and stress_ratio > 0.10:
        return "seasonal_pattern", stress_ratio

    if clusters:
        last_cluster = clusters[-1]
        distance_from_end = (total_months - 1) - last_cluster["end"]

        if distance_from_end > 8:
            # The stress episode is old history relative to the window, not
            # a current risk signal. If the trajectory since then is
            # genuinely positive, that's worth calling "recovering" rather
            # than either dragging old stress forward as "temporary_stress"
            # or silently relabeling it as plain "stable"/"improving" as if
            # nothing had ever happened.
            if trend["pct_change"] > 0:
                return "recovering", stress_ratio
            # otherwise fall through to the general trend-based rules below

        elif distance_from_end >= 4 and last_cluster["length"] <= 6:
            # the most recent stress episode ended somewhat before the end of
            # the observed window and the tail since then is clean -> recovered
            return "temporary_stress", stress_ratio

        elif distance_from_end <= 2:
            # stress is current / still ongoing at the edge of the window
            if trend["pct_change"] <= -12 and not trend["recovering"]:
                return "structural_decline", stress_ratio
            return "chronic_strain", stress_ratio

    if trend["pct_change"] <= -20 and not trend["recovering"]:
        return "structural_decline", stress_ratio

    if stress_ratio > 0.20:
        return "chronic_strain", stress_ratio

    if trend["pct_change"] >= 12:
        return "improving", stress_ratio

    return "stable", stress_ratio


def analyze_borrower(borrower):
    income = borrower["income"]
    expenses = borrower["expenses"]
    loan = borrower["loan"]

    net_cf = net_cash_flow(income, expenses)
    rolling = rolling_average(net_cf, window=3)
    seasonality = seasonality_index(net_cf)
    trend = trend_shift(net_cf)
    stressed = stress_months(net_cf, loan["installment"])
    condition, stress_ratio = classify_condition(trend, seasonality, stressed, len(net_cf))
    clusters = [c for c in stress_clusters(stressed, len(net_cf), max_gap=0) if c["length"] >= 2]

    return {
        "net_cash_flow": net_cf,
        "rolling_average": rolling,
        "seasonality": seasonality,
        "trend": trend,
        "stressed_months": stressed,
        "stress_clusters": clusters,
        "stress_ratio": round(stress_ratio, 3),
        "condition": condition,
    }