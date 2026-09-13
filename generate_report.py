"""
generate_report.py
--------------------
Runs the full pipeline for every synthetic borrower:

    data -> cash-flow analysis -> forecast -> risk/affordability scoring
         -> financial health score -> repayment stress index
         -> scenario simulation (5 strategies) -> optimizer pick
         -> evidence chain -> early warnings -> "why not current plan"
         -> [optional] ML double-check (ml_engine.py), if scikit-learn/numpy
            are installed - see requirements.txt

...and writes a single JS file (dashboard/data.js) that the static
dashboard loads directly via a <script> tag - no server, no build step.

Usage:
    python3 generate_report.py [--seed N] [--forecast-months N]
"""

import argparse
import json
import os
import statistics as stats

from data_generator import get_borrowers, set_seed
from cashflow_engine import analyze_borrower
from risk_engine import affordability_score, risk_score, build_evidence_chain
from repayment_engine import build_plan
from forecast_engine import forecast_borrower
from scenario_engine import build_scenarios
from health_engine import (
    financial_health_score, repayment_stress_index, classification_confidence,
    build_warnings, intervention_for_condition, why_not_current_plan,
)
import evaluate as evaluation_module

try:
    from ml_engine import double_check_report
    _ML_AVAILABLE = True
except ImportError:
    _ML_AVAILABLE = False

OUT_DIR = os.path.join(os.path.dirname(__file__), "dashboard")
OUT_FILE = os.path.join(OUT_DIR, "data.js")


def _repayment_history_summary(history):
    if not history:
        return {"on_time_rate": 100.0, "missed_count": 0, "partial_count": 0, "avg_delay_days": 0.0}
    missed = sum(1 for h in history if h["status"] == "missed")
    partial = sum(1 for h in history if h["status"] == "partial")
    on_time = sum(1 for h in history if h["status"] == "on_time")
    delays = [h["days_late"] for h in history if h["days_late"] > 0]
    return {
        "on_time_rate": round(on_time / len(history) * 100, 1),
        "missed_count": missed,
        "partial_count": partial,
        "avg_delay_days": round(stats.mean(delays), 1) if delays else 0.0,
    }


def run(forecast_months=6):
    borrowers = get_borrowers()
    report = []

    ml_by_id = {}
    ml_validation = None
    if _ML_AVAILABLE:
        print("Training ML double-check layer (risk model + condition model)... "
              "this takes ~30-40s due to leave-one-out cross-validation.")
        try:
            ml_report = double_check_report(borrowers)
            ml_by_id = {row["id"]: row for row in ml_report["borrowers"]}
            ml_validation = {
                "risk_model": ml_report["risk_model_summary"],
                "condition_model": ml_report["condition_model_summary"],
            }
        except Exception as e:  # noqa: BLE001 - never let the ML layer break the core report
            print(f"WARNING: ML double-check layer failed ({e}); continuing without it.")

    for b in borrowers:
        analysis = analyze_borrower(b)
        affordability = affordability_score(analysis["net_cash_flow"], b["loan"]["installment"])
        risk = risk_score(analysis["condition"], analysis["stress_ratio"], analysis["trend"]["pct_change"])
        evidence = build_evidence_chain(b, analysis)
        plan = build_plan(b, analysis)
        forecast = forecast_borrower(b, analysis, months_ahead=forecast_months)
        scenarios = build_scenarios(b, analysis)
        health = financial_health_score(b, analysis)
        stress_index = repayment_stress_index(analysis, b["loan"]["installment"])
        confidence = classification_confidence(analysis)
        warnings = build_warnings(b, analysis)
        intervention = intervention_for_condition(analysis["condition"])
        comparison_narrative = why_not_current_plan(b, analysis, scenarios)
        repayment_summary = _repayment_history_summary(b.get("repayment_history", []))

        report.append({
            "id": b["id"],
            "name": b["name"],
            "archetype": b["archetype"],
            "loan": b["loan"],
            "income": b["income"],
            "expenses": b["expenses"],
            "net_cash_flow": analysis["net_cash_flow"],
            "rolling_average": analysis["rolling_average"],
            "seasonality": analysis["seasonality"],
            "trend": analysis["trend"],
            "stressed_months": analysis["stressed_months"],
            "stress_clusters": analysis["stress_clusters"],
            "stress_ratio": analysis["stress_ratio"],
            "condition": analysis["condition"],
            "affordability_score": affordability,
            "risk_score": risk,
            "evidence_chain": evidence,
            "repayment_plan": plan,
            "forecast": forecast,
            "scenarios": scenarios,
            "financial_health": health,
            "repayment_stress_index": stress_index,
            "classification_confidence": confidence,
            "warnings": warnings,
            "intervention": intervention,
            "comparison_narrative": comparison_narrative,
            "repayment_history": b.get("repayment_history", []),
            "repayment_history_summary": repayment_summary,
            "ml_check": ml_by_id.get(b["id"]),  # None if ML layer unavailable/failed
        })

    condition_counts = {}
    for r in report:
        condition_counts[r["condition"]] = condition_counts.get(r["condition"], 0) + 1

    intervention_needed = sum(1 for r in report if r["condition"] not in ("stable", "improving", "recovering"))
    seasonal_mismatch = sum(1 for r in report if r["repayment_stress_index"]["seasonal_mismatch"])
    high_risk = sum(1 for r in report if r["risk_score"] >= 60)

    portfolio_summary = {
        "total_borrowers": len(report),
        "total_outstanding": round(sum(r["loan"]["principal"] for r in report), 2),
        "avg_risk_score": round(sum(r["risk_score"] for r in report) / len(report), 1),
        "avg_affordability_score": round(sum(r["affordability_score"] for r in report) / len(report), 1),
        "avg_financial_health": round(sum(r["financial_health"]["score"] for r in report) / len(report), 1),
        "avg_repayment_stress": round(sum(r["repayment_stress_index"]["index"] for r in report) / len(report), 1),
        "condition_counts": condition_counts,
        "borrowers_needing_intervention": intervention_needed,
        "borrowers_with_seasonal_mismatch": seasonal_mismatch,
        "borrowers_high_risk": high_risk,
        "estimated_recovery_pct": round(
            sum(r["comparison_narrative"]["recommended"]["recovery_pct"] for r in report) / len(report), 1
        ),
    }

    validation = evaluation_module.run()

    os.makedirs(OUT_DIR, exist_ok=True)
    payload = {
        "borrowers": report,
        "portfolio_summary": portfolio_summary,
        "validation": {
            "classifier_accuracy_pct": validation["classifier"]["accuracy_pct"],
            "classifier_rows": validation["classifier"]["rows"],
            "forecast_income_mae": validation["forecast"]["overall_income_mae"],
            "forecast_netcf_mae": validation["forecast"]["overall_netcf_mae"],
            "forecast_rows": validation["forecast"]["rows"],
            "holdout_months": validation["forecast"]["holdout_months"],
        },
        "meta": {
            "forecast_months": forecast_months,
            "safety_buffer_pct": 10,
        },
        "ml_validation": ml_validation,  # None if the ML layer wasn't available
    }

    with open(OUT_FILE, "w") as f:
        f.write("// Auto-generated by generate_report.py - do not edit by hand.\n")
        f.write("const REPORT_DATA = ")
        json.dump(payload, f, indent=2)
        f.write(";\n")

    print(f"Wrote {OUT_FILE} with {len(report)} borrowers.")
    print(f"Classifier accuracy on synthetic ground truth: {validation['classifier']['accuracy_pct']}%")
    if ml_validation:
        print(f"ML risk model CV accuracy: {ml_validation['risk_model']['cv_accuracy_pct']}% "
              f"| ML condition model CV accuracy: {ml_validation['condition_model']['cv_accuracy_pct']}%")
    else:
        print("ML double-check layer not included (scikit-learn/numpy unavailable or it failed) - "
              "run `pip install -r requirements.txt` to enable it.")
    print("Open dashboard/index.html in a browser to view the prototype.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the full microloan decision-engine pipeline.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for synthetic data.")
    parser.add_argument("--forecast-months", type=int, default=6, help="Forward forecast horizon in months.")
    args = parser.parse_args()
    if args.seed != 42:
        set_seed(args.seed)
    run(forecast_months=args.forecast_months)