"""
ml_evaluate.py
---------------
Human-readable console report for the ML layer added in ml_engine.py.
Mirrors evaluate.py's job for the rule-based engine: answers "how do you
know the ML actually works?" - honestly, including where it doesn't.

Usage:
    python3 ml_evaluate.py
"""

from ml_engine import double_check_report


def _bar(ch="-", width=78):
    print(ch * width)


def main():
    report = double_check_report()
    risk = report["risk_model_summary"]
    cond = report["condition_model_summary"]

    _bar("=")
    print("RISK MODEL (month-level, predicts missed/partial payment)")
    _bar("=")
    print(f"Leave-one-borrower-out CV accuracy : {risk['cv_accuracy_pct']}%  "
          f"(n={risk['n_rows']} borrower-months)")
    print(f"Precision / Recall / F1            : "
          f"{risk['cv_precision']} / {risk['cv_recall']} / {risk['cv_f1']}")
    tn, fp = risk["cv_confusion_matrix"][0]
    fn, tp = risk["cv_confusion_matrix"][1]
    print(f"Confusion matrix  [[TN={tn}, FP={fp}], [FN={fn}, TP={tp}]]")
    print(f"Note: {risk['note']}")
    print("\nTop global drivers (standardized logistic-regression coefficients,")
    print("positive = pushes prediction toward 'missed/partial'):")
    for row in risk["global_feature_importance"][:6]:
        sign = "+" if row["coefficient"] >= 0 else ""
        print(f"  {row['feature']:<30} {sign}{row['coefficient']}")

    print()
    _bar("=")
    print("CONDITION MODEL (borrower-level, predicts stable/seasonal/stress/etc.)")
    _bar("=")
    print(f"Leave-one-out CV accuracy (on the real borrowers, held out one at a "
          f"time from a synthetic-augmented training pool): {cond['cv_accuracy_pct']}%")
    print(f"CAVEAT: {cond['caveat']}")
    print("\nTop global drivers (Random Forest feature importances):")
    for row in cond["global_feature_importance"][:6]:
        print(f"  {row['feature']:<30} {row['importance']}")

    print()
    _bar("=")
    print("PER-BORROWER DOUBLE-CHECK: ML vs. the rule-based engine")
    _bar("=")
    header = (f"{'ID':<5}{'Rule condition':<20}{'ML condition':<20}"
              f"{'Agree?':<8}{'Rule risk':<11}{'ML avg risk':<13}{'Actual stress%':<15}")
    print(header)
    print("-" * len(header))
    for r in report["borrowers"]:
        agree = "YES" if r["ml_agrees_with_rule_engine"] else "no"
        print(f"{r['id']:<5}{r['rule_condition']:<20}{r['ml_condition']:<20}"
              f"{agree:<8}{r['rule_risk_score']:<11}{r['ml_avg_predicted_risk_pct']:<13}"
              f"{r['actual_stress_month_rate_pct']:<15}")

    print()
    for r in report["borrowers"]:
        print(f"[{r['id']}] {r['name']}")
        print(f"    Rule engine says: {r['rule_condition']} (risk score {r['rule_risk_score']}/100)")
        print(f"    ML says:          {r['ml_condition']} "
              f"(confidence {r['ml_condition_confidence_pct']}%) - "
              f"{'agrees' if r['ml_agrees_with_rule_engine'] else 'DISAGREES, review recommended'}")
        print(f"    ML avg predicted monthly stress risk: {r['ml_avg_predicted_risk_pct']}% "
              f"(actual observed: {r['actual_stress_month_rate_pct']}%)")
        print("    Top features behind the ML condition call:")
        for d in r["condition_top_drivers"]:
            print(f"      - {d['feature']}: this borrower = {d['this_borrower']}, "
                  f"cohort avg = {d['cohort_avg']} (importance {d['importance']})")
        print()


if __name__ == "__main__":
    main()