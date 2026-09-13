"""
forecast_engine.py
--------------------
Simple, explainable forward cash-flow forecasting.

Given a borrower's historical monthly series (income, expenses, or net
cash flow), projects the next N months using a transparent statistical
blend rather than a black-box model:

  - a trend component: a recency-weighted average of the last few months
    (weights increase linearly toward the most recent month), so a
    genuine recent shift matters more than ancient history
  - a seasonal component: this calendar month's average deviation from
    the borrower's own overall mean, added on top of the trend when the
    series has already been flagged as seasonal
  - an uncertainty band derived from the borrower's own historical
    volatility (population stdev), widening with sqrt(horizon) - further
    out months are genuinely less certain, not arbitrarily so

No deep learning, no external forecasting library - every number here
traces back to a statistic computed directly from the borrower's own
history, which is what "explainable" means for this project.
"""

import statistics as stats

CONFIDENCE_Z = 1.28  # ~80% interval for an approximately normal residual


def _weighted_recent_mean(series, window=6):
    """Recency-weighted average of the last `window` months."""
    window = min(window, len(series))
    recent = series[-window:]
    weights = list(range(1, window + 1))
    return sum(v * w for v, w in zip(recent, weights)) / sum(weights)


def _seasonal_deviation(series, target_month_idx):
    """Average deviation of calendar-month `target_month_idx` (0-11) from
    the borrower's overall mean, using every historical occurrence."""
    if not series:
        return 0.0
    overall_mean = stats.mean(series)
    same_month_vals = [series[i] for i in range(len(series)) if i % 12 == target_month_idx]
    if not same_month_vals:
        return 0.0
    return stats.mean(same_month_vals) - overall_mean


def forecast_series(series, months_ahead, seasonal=False):
    """Forecast the next `months_ahead` points of a single numeric series.
    Returns {"point": [...], "lower": [...], "upper": [...]}."""
    if not series:
        flat = [0.0] * months_ahead
        return {"point": flat, "lower": flat, "upper": flat}

    base_trend = _weighted_recent_mean(series, window=min(6, len(series)))
    stdev = stats.pstdev(series) if len(series) > 1 else abs(base_trend) * 0.15

    point, lower, upper = [], [], []
    n = len(series)
    for step in range(1, months_ahead + 1):
        target_month_idx = (n + step - 1) % 12
        seasonal_adj = _seasonal_deviation(series, target_month_idx) if seasonal else 0.0
        forecast_value = base_trend + seasonal_adj

        # Uncertainty widens with sqrt(horizon): a standard, explainable
        # way to say "further out is less certain" without pretending to
        # a specific model's exact error-propagation formula.
        band = CONFIDENCE_Z * stdev * (step ** 0.5) * 0.5

        point.append(round(forecast_value, 2))
        lower.append(round(forecast_value - band, 2))
        upper.append(round(forecast_value + band, 2))

    return {"point": point, "lower": lower, "upper": upper}


def forecast_borrower(borrower, analysis, months_ahead=6):
    """Forecast this borrower's net cash flow (plus income/expenses, kept
    for completeness / future UI use) for the next `months_ahead` months."""
    net_cf = analysis["net_cash_flow"]
    income = borrower["income"]
    expenses = borrower["expenses"]
    is_seasonal = analysis["seasonality"]["is_seasonal"]

    method = "Seasonal weighted moving average" if is_seasonal else "Weighted moving average"

    return {
        "months_ahead": months_ahead,
        "method": method,
        "net_cash_flow": forecast_series(net_cf, months_ahead, seasonal=is_seasonal),
        "income": forecast_series(income, months_ahead, seasonal=is_seasonal),
        "expenses": forecast_series(expenses, months_ahead, seasonal=False),
    }