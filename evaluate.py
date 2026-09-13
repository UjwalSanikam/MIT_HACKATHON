"""
evaluate.py
------------
Answers the question every judge asks a hackathon team: "how do you know
your system actually works?"

Two independent checks, both driven off data the pipeline never sees as
ground truth (the classifier and forecaster only ever see income/expense
numbers - never the `ground_truth` label or the held-out tail used here):

1. CLASSIFIER VALIDATION
   Each synthetic borrower carries a `ground_truth` list of acceptable
   condition labels (set once in data_generator.py, by construction of the
   archetype - never fed into cashflow_engine). We report whether the
   classifier's actual output falls inside that acceptable set, plus a
   confusion-style breakdown of predicted vs. archetype.

2. FORECAST BACKTEST
   We hide the last N months of each borrower's real history, forecast
   them from only the months before that, then compare the forecast
   against the real (held-out) values: MAE, RMSE, and MAPE.

Usage:
    python3 evaluate.py
"""

import statistics as stats

from data_generator import get_borrowers
from cashflow_engine import analyze_borrower
from forecast_engine import forecast_series

HOLDOUT_MONTHS = 6


def evaluate_classifier():
    borrowers = get_borrowers()
    rows = []
    correct = 0
    predicted_counts = {}

    for b in borrowers:
        analysis = analyze_borrower(b)
        predicted = analysis["condition"]
        expected = b["ground_truth"]
        is_correct = predicted in expected
        correct += int(is_correct)
        predicted_counts[predicted] = predicted_counts.get(predicted, 0) + 1
        rows.append({
            "id": b["id"], "name": b["name"], "archetype": b["archetype"],
            "predicted": predicted, "acceptable": expected, "correct": is_correct,
        })

    accuracy = round(correct / len(borrowers) * 100, 1) if borrowers else 0
    return {
        "accuracy_pct": accuracy,
        "correct": correct,
        "total": len(borrowers),
        "predicted_distribution": predicted_counts,
        "rows": rows,
    }


def _errors(predicted, actual):
    abs_err = [abs(p - a) for p, a in zip(predicted, actual)]
    sq_err = [(p - a) ** 2 for p, a in zip(predicted, actual)]
    pct_err = [abs(p - a) / abs(a) for p, a in zip(predicted, actual) if a != 0]
    return {
        "mae": round(stats.mean(abs_err), 1),
        "rmse": round(stats.mean(sq_err) ** 0.5, 1),
        "mape": round(stats.mean(pct_err) * 100, 1) if pct_err else None,
    }


def evaluate_forecast(months_ahead=HOLDOUT_MONTHS):
    """Backtests both INCOME (always positive - MAPE is meaningful) and NET
    CASH FLOW (can cross zero for volatile/seasonal borrowers, so MAPE is
    reported as None rather than the misleadingly huge number you get from
    dividing by a near-zero actual - MAE/RMSE are the honest metrics there)."""
    borrowers = get_borrowers()
    all_income_errors, all_netcf_errors = [], []
    rows = []

    for b in borrowers:
        income_full = b["income"]
        if len(income_full) <= months_ahead + 6:
            continue
        net_cf_full = analyze_borrower(b)["net_cash_flow"]

        income_train, income_holdout = income_full[:-months_ahead], income_full[-months_ahead:]
        netcf_train, netcf_holdout = net_cf_full[:-months_ahead], net_cf_full[-months_ahead:]

        analysis_train = analyze_borrower({**b, "income": income_train,
                                            "expenses": b["expenses"][:-months_ahead]})
        is_seasonal = analysis_train["seasonality"]["is_seasonal"]

        income_pred = forecast_series(income_train, months_ahead, seasonal=is_seasonal)["point"]
        netcf_pred = forecast_series(netcf_train, months_ahead, seasonal=is_seasonal)["point"]

        income_err = _errors(income_pred, income_holdout)
        netcf_err = _errors(netcf_pred, netcf_holdout)
        netcf_err["mape"] = None  # net cash flow can cross zero - MAPE is not meaningful here

        all_income_errors.append(income_err["mae"])
        all_netcf_errors.append(netcf_err["mae"])
        rows.append({"id": b["id"], "name": b["name"], "income": income_err, "net_cash_flow": netcf_err})

    return {
        "holdout_months": months_ahead,
        "overall_income_mae": round(stats.mean(all_income_errors), 1) if all_income_errors else 0,
        "overall_netcf_mae": round(stats.mean(all_netcf_errors), 1) if all_netcf_errors else 0,
        "rows": rows,
    }


def run():
    print(f"=== Classifier validation ({HOLDOUT_MONTHS and 'ground-truth archetype check'}) ===")
    clf = evaluate_classifier()
    print(f"Accuracy: {clf['correct']}/{clf['total']} ({clf['accuracy_pct']}%)\n")
    for r in clf["rows"]:
        mark = "OK  " if r["correct"] else "MISS"
        print(f"  [{mark}] {r['id']} {r['name']:<38} predicted={r['predicted']:<20} acceptable={r['acceptable']}")

    print(f"\n=== Forecast backtest (holding out last {HOLDOUT_MONTHS} months) ===")
    fc = evaluate_forecast()
    print(f"Overall income MAE: Rs.{fc['overall_income_mae']}   |   Overall net-cash-flow MAE: Rs.{fc['overall_netcf_mae']}\n")
    for r in fc["rows"]:
        i, n = r["income"], r["net_cash_flow"]
        print(f"  {r['id']} {r['name']:<38} income MAE=Rs.{i['mae']:<8} MAPE={i['mape']}%   "
              f"| net-CF MAE=Rs.{n['mae']}")

    return {"classifier": clf, "forecast": fc}


if __name__ == "__main__":
    run()