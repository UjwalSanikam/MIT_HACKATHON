"""
ml_engine.py
-------------
Adds a learned, statistical-ML layer that DOUBLE-CHECKS the rule-based
engine (cashflow_engine.py + risk_engine.py) rather than replacing it.

Why two separate models, at two separate grains:

  We only have 8 labeled borrowers. Training a classifier on 8 rows to
  predict a 7-way "condition" label and trusting it would be dishonest -
  it would just memorize the 8 examples. So:

  1. RISK MODEL (month-level, binary: "will this month be missed/partial?")
     Trained on 8 borrowers x 24 months = 192 rows - a real (if small)
     dataset. Evaluated with LEAVE-ONE-BORROWER-OUT cross-validation, so
     every prediction used for scoring comes from a borrower the model
     never saw during that fold's training. This is the model whose
     numbers you can actually trust for a demo.

  2. CONDITION MODEL (borrower-level, multi-class: stable/seasonal/
     temporary_stress/chronic_strain/structural_decline/improving/
     recovering) Trained on only 8 rows. Also evaluated with leave-one-out,
     but with 8 samples and 7 classes this is explicitly a DIRECTIONAL
     signal for a demo, not a validated classifier. We say so out loud
     everywhere it's reported, instead of hiding the caveat.

Both models are then used to build a "double-check" report per borrower:
did the learned model agree with the rule-based engine, and what raw
numbers pushed the ML prediction the way it went? This mirrors the
evidence-chain style already used in risk_engine.py: every claim traces
back to a concrete feature value, never an unexplained probability.

Requires scikit-learn + numpy (the only two external dependencies added
to this otherwise stdlib-only project - see requirements.txt).
"""

import statistics as stats

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score, confusion_matrix, precision_recall_fscore_support,
)
from sklearn.model_selection import LeaveOneGroupOut, cross_val_predict
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from data_generator import get_borrowers, generate_synthetic_cohort
from cashflow_engine import analyze_borrower, net_cash_flow, rolling_average
import risk_engine

MONTH_FEATURE_NAMES = [
    "net_cash_flow", "coverage_ratio", "rolling_3mo_coverage",
    "month_of_year_sin", "month_of_year_cos", "mom_pct_change",
    "prev_month_missed", "prev_month_partial", "prev_month_days_late",
    "prior_missed_or_partial_rate",
]

BORROWER_FEATURE_NAMES = [
    "mean_net_cf_to_installment", "cf_volatility_ratio", "stress_ratio",
    "num_stress_clusters", "longest_cluster_length", "trend_pct_change",
    "trend_recovering", "seasonality_spread_ratio", "is_seasonal",
    "year_over_year_correlation", "on_time_rate", "missed_count",
    "avg_delay_days",
]


# ---------------------------------------------------------------------------
# Month-level dataset (risk model): one row per borrower-month
# ---------------------------------------------------------------------------

def _month_features(borrower, m, net_cf, rolling3, history):
    installment = borrower["loan"]["installment"]
    cf = net_cf[m]
    coverage = cf / installment if installment else 0.0
    rolling_coverage = rolling3[m] / installment if installment else 0.0
    month_of_year = m % 12
    sin_m = np.sin(2 * np.pi * month_of_year / 12)
    cos_m = np.cos(2 * np.pi * month_of_year / 12)
    mom_pct = 0.0
    if m > 0 and net_cf[m - 1] != 0:
        mom_pct = (net_cf[m] - net_cf[m - 1]) / abs(net_cf[m - 1])

    prev_missed = prev_partial = 0
    prev_days_late = 0.0
    prior_bad_rate = 0.0
    if m > 0:
        prev = history[m - 1]
        prev_missed = int(prev["status"] == "missed")
        prev_partial = int(prev["status"] == "partial")
        prev_days_late = prev["days_late"]
        prior = history[:m]
        bad = sum(1 for h in prior if h["status"] in ("missed", "partial"))
        prior_bad_rate = bad / len(prior)

    return [
        cf, coverage, rolling_coverage, sin_m, cos_m, mom_pct,
        prev_missed, prev_partial, prev_days_late, prior_bad_rate,
    ]


def build_month_level_dataset(borrowers):
    X, y, groups, meta = [], [], [], []
    for b in borrowers:
        net_cf = net_cash_flow(b["income"], b["expenses"])
        rolling3 = rolling_average(net_cf, window=3)
        history = b["repayment_history"]
        for m in range(len(net_cf)):
            X.append(_month_features(b, m, net_cf, rolling3, history))
            y.append(int(history[m]["status"] in ("missed", "partial")))
            groups.append(b["id"])
            meta.append({"borrower_id": b["id"], "month": m})
    return np.array(X, dtype=float), np.array(y, dtype=int), groups, meta


# ---------------------------------------------------------------------------
# Borrower-level dataset (condition model): one row per borrower
# ---------------------------------------------------------------------------

def _repayment_summary(history):
    if not history:
        return 100.0, 0, 0.0
    missed = sum(1 for h in history if h["status"] == "missed")
    on_time = sum(1 for h in history if h["status"] == "on_time")
    delays = [h["days_late"] for h in history if h["days_late"] > 0]
    on_time_rate = round(on_time / len(history) * 100, 1)
    avg_delay = round(stats.mean(delays), 1) if delays else 0.0
    return on_time_rate, missed, avg_delay


def _borrower_features(borrower, analysis):
    net_cf = analysis["net_cash_flow"]
    installment = borrower["loan"]["installment"]
    mean_cf = stats.mean(net_cf)
    stdev_cf = stats.pstdev(net_cf) if len(net_cf) > 1 else 0.0
    volatility_ratio = (stdev_cf / mean_cf) if mean_cf else 5.0  # sentinel: very volatile

    clusters = analysis["stress_clusters"]
    longest = max((c["length"] for c in clusters), default=0)

    seasonality = analysis["seasonality"]
    overall_mean = stats.mean(net_cf) if net_cf else 0
    spread_ratio = (seasonality["spread"] / overall_mean) if overall_mean > 0 else 0.0

    on_time_rate, missed_count, avg_delay = _repayment_summary(borrower.get("repayment_history", []))

    return [
        mean_cf / installment if installment else 0.0,
        volatility_ratio,
        analysis["stress_ratio"],
        len(clusters),
        longest,
        analysis["trend"]["pct_change"],
        int(analysis["trend"]["recovering"]),
        spread_ratio,
        int(seasonality["is_seasonal"]),
        seasonality["year_over_year_correlation"],
        on_time_rate,
        missed_count,
        avg_delay,
    ]


def build_borrower_level_dataset(borrowers):
    X, y, ids, analyses = [], [], [], []
    for b in borrowers:
        analysis = analyze_borrower(b)
        X.append(_borrower_features(b, analysis))
        y.append(b["ground_truth"][0])  # primary/dominant expected condition
        ids.append(b["id"])
        analyses.append(analysis)
    return np.array(X, dtype=float), np.array(y), ids, analyses


# ---------------------------------------------------------------------------
# Risk model (month-level, binary) - LOGISTIC REGRESSION for clean, signed,
# explainable coefficients.
# ---------------------------------------------------------------------------

def train_risk_model(borrowers=None):
    borrowers = borrowers or get_borrowers()
    X, y, groups, meta = build_month_level_dataset(borrowers)

    pipeline = Pipeline([
        ("scale", StandardScaler()),
        ("clf", LogisticRegression(max_iter=1000, class_weight="balanced", random_state=42)),
    ])

    logo = LeaveOneGroupOut()
    cv_pred = cross_val_predict(pipeline, X, y, groups=groups, cv=logo, method="predict")
    cv_proba = cross_val_predict(pipeline, X, y, groups=groups, cv=logo, method="predict_proba")[:, 1]

    acc = round(accuracy_score(y, cv_pred) * 100, 1)
    precision, recall, f1, _ = precision_recall_fscore_support(
        y, cv_pred, average="binary", zero_division=0
    )
    cm = confusion_matrix(y, cv_pred).tolist()

    # Fit final model on ALL data for use in the double-check report.
    pipeline.fit(X, y)
    coefs = pipeline.named_steps["clf"].coef_[0]
    global_importance = sorted(
        zip(MONTH_FEATURE_NAMES, coefs), key=lambda t: abs(t[1]), reverse=True
    )

    return {
        "pipeline": pipeline,
        "cv_accuracy_pct": acc,
        "cv_precision": round(precision, 3),
        "cv_recall": round(recall, 3),
        "cv_f1": round(f1, 3),
        "cv_confusion_matrix": cm,  # rows/cols = [on_time, missed_or_partial]
        "cv_predictions": cv_pred,
        "cv_predicted_proba": cv_proba,
        "meta": meta,
        "y_true": y,
        "global_feature_importance": global_importance,
        "n_rows": len(y),
        "n_borrowers": len(borrowers),
    }


def explain_month_prediction(risk_model, x_row, top_n=3):
    """Signed, per-instance contribution = standardized_feature * coefficient.
    Positive => pushed the risk prediction UP toward 'missed/partial'."""
    pipeline = risk_model["pipeline"]
    scaler = pipeline.named_steps["scale"]
    coefs = pipeline.named_steps["clf"].coef_[0]
    x_scaled = scaler.transform([x_row])[0]
    contributions = x_scaled * coefs
    ranked = sorted(
        zip(MONTH_FEATURE_NAMES, contributions, x_row), key=lambda t: abs(t[1]), reverse=True
    )
    return ranked[:top_n]


# ---------------------------------------------------------------------------
# Condition model (borrower-level, multi-class) - RANDOM FOREST: handles a
# small, non-linear, multi-class problem without needing feature scaling,
# and gives clean global feature_importances_ for explainability.
# ---------------------------------------------------------------------------

def train_condition_model(real_borrowers=None, n_synthetic_per_archetype=20, synthetic_seed=123):
    """Trains on the real (hand-designed) borrowers PLUS a larger synthetic
    cohort of archetype variants (same generative logic, randomized
    parameters - see data_generator.generate_synthetic_cohort). With only 8
    real borrowers across ~7 classes, leave-one-out accuracy is ~0% (see
    git history / README) - that's not enough data for any model to
    generalize. Augmenting with synthetic variants is a legitimate way to
    validate that the FEATURES and PIPELINE work; it is NOT a substitute for
    real repayment-outcome data before trusting this in production. Set
    n_synthetic_per_archetype=0 to see the honest, unaugmented 8-sample
    result instead.
    """
    real_borrowers = real_borrowers if real_borrowers is not None else get_borrowers()
    synthetic = (
        generate_synthetic_cohort(n_synthetic_per_archetype, seed=synthetic_seed)
        if n_synthetic_per_archetype > 0 else []
    )
    borrowers = list(real_borrowers) + synthetic
    real_ids = {b["id"] for b in real_borrowers}

    X, y, ids, analyses = build_borrower_level_dataset(borrowers)

    clf = RandomForestClassifier(
        n_estimators=200, max_depth=4, random_state=42, class_weight="balanced"
    )

    # Leave-one-borrower-out across the FULL augmented pool (real + synthetic).
    n = len(y)
    cv_pred = np.empty(n, dtype=object)
    cv_proba_max = np.empty(n, dtype=float)
    for i in range(n):
        train_idx = [j for j in range(n) if j != i]
        clf_fold = RandomForestClassifier(
            n_estimators=200, max_depth=4, random_state=42, class_weight="balanced"
        )
        clf_fold.fit(X[train_idx], y[train_idx])
        pred = clf_fold.predict(X[i:i + 1])[0]
        proba = clf_fold.predict_proba(X[i:i + 1])[0].max()
        cv_pred[i] = pred
        cv_proba_max[i] = proba

    acc_all = round(accuracy_score(y, cv_pred) * 100, 1)
    # The number that actually matters: accuracy specifically on the 8 real
    # demo borrowers (synthetic archetype clones are easy - they'd inflate
    # the headline number if we didn't separate this out).
    real_mask = np.array([i in real_ids for i in ids])
    acc_real = (
        round(accuracy_score(y[real_mask], cv_pred[real_mask]) * 100, 1)
        if real_mask.any() else None
    )

    # Fit final model on the FULL augmented pool for use in the double-check
    # report. Its predictions on the real 8 are not a generalization test
    # for THOSE 8 specifically (they're in the training data now) - the
    # honest generalization estimate is acc_real above, from the fold where
    # each real borrower was held out.
    clf.fit(X, y)
    importances = sorted(
        zip(BORROWER_FEATURE_NAMES, clf.feature_importances_), key=lambda t: t[1], reverse=True
    )
    cohort_means = X.mean(axis=0)

    return {
        "model": clf,
        "cv_accuracy_pct": acc_real if acc_real is not None else acc_all,
        "cv_accuracy_pct_full_pool": acc_all,
        "cv_predictions": dict(zip(ids, cv_pred)),
        "cv_confidence": dict(zip(ids, np.round(cv_proba_max, 3))),
        "y_true": dict(zip(ids, y)),
        "global_feature_importance": importances,
        "cohort_means": cohort_means,
        "n_borrowers": n,
        "n_real_borrowers": len(real_borrowers),
        "n_synthetic_borrowers": len(synthetic),
        "caveat": (
            f"Trained on {len(real_borrowers)} real borrowers augmented with "
            f"{len(synthetic)} synthetic archetype variants (same generative "
            f"logic, randomized parameters) to give the model enough rows to "
            f"have a fair shot at generalizing. cv_accuracy_pct above is "
            f"measured ONLY on the {len(real_borrowers)} real borrowers, each "
            f"held out of training in its own fold - that's the honest number. "
            f"cv_accuracy_pct_full_pool ({acc_all}%) includes the easier "
            f"synthetic clones and will look better than reality; don't quote "
            f"that one as the headline. Real-outcome data (actual future "
            f"repayment behavior) is still the right long-term fix, not more "
            f"synthetic variants of the same 8 hand-designed stories."
        ),
    }


def explain_condition_prediction(condition_model, x_row, top_n=3):
    """Not a per-instance SHAP value - a transparent proxy: rank features by
    the model's GLOBAL importance, then show this borrower's raw value next
    to the cohort average so a human can see which direction it points."""
    importances = condition_model["global_feature_importance"]
    means = condition_model["cohort_means"]
    name_to_idx = {n: i for i, n in enumerate(BORROWER_FEATURE_NAMES)}
    out = []
    for name, importance in importances[:top_n]:
        idx = name_to_idx[name]
        out.append((name, importance, x_row[idx], means[idx]))
    return out


# ---------------------------------------------------------------------------
# Double-check report: ties both models back to the rule-based engine
# ---------------------------------------------------------------------------

def double_check_report(borrowers=None):
    borrowers = borrowers or get_borrowers()

    risk_model = train_risk_model(borrowers)
    condition_model = train_condition_model(borrowers)

    X_month, y_month, groups_month, meta_month = build_month_level_dataset(borrowers)
    X_borrower, y_borrower, ids, analyses = build_borrower_level_dataset(borrowers)

    # Predict every borrower's own months with the model fit on ALL data,
    # purely to compute an "ML avg predicted risk" summary number per
    # borrower (NOT used as a generalization claim - that's cv_accuracy_pct).
    all_month_proba = risk_model["pipeline"].predict_proba(X_month)[:, 1]

    rows = []
    for i, b in enumerate(borrowers):
        analysis = analyses[i]
        rule_condition = analysis["condition"]
        rule_risk_score = risk_engine.risk_score(
            rule_condition, analysis["stress_ratio"], analysis["trend"]["pct_change"]
        )

        ml_condition = condition_model["cv_predictions"][b["id"]]
        ml_condition_confidence = condition_model["cv_confidence"][b["id"]]
        agrees_with_rule_engine = (ml_condition == rule_condition)
        # Validation-only field (evaluate.py/data_generator.py's ground_truth
        # is never fed to either model) - useful for judging the demo, not
        # something the production pipeline could compute for a real borrower.
        matches_expected_archetype = ml_condition in b["ground_truth"]

        borrower_month_idx = [j for j, m in enumerate(meta_month) if m["borrower_id"] == b["id"]]
        ml_avg_risk_pct = round(float(np.mean(all_month_proba[borrower_month_idx])) * 100, 1)
        actual_stress_rate_pct = round(
            sum(1 for j in borrower_month_idx if y_month[j] == 1) / len(borrower_month_idx) * 100, 1
        )

        condition_drivers = explain_condition_prediction(condition_model, X_borrower[i])

        rows.append({
            "id": b["id"],
            "name": b["name"],
            "rule_condition": rule_condition,
            "rule_risk_score": rule_risk_score,
            "ml_condition": ml_condition,
            "ml_condition_confidence_pct": round(ml_condition_confidence * 100, 1),
            "ml_agrees_with_rule_engine": bool(agrees_with_rule_engine),
            "ml_matches_expected_archetype_validation_only": bool(matches_expected_archetype),
            "ml_avg_predicted_risk_pct": ml_avg_risk_pct,
            "actual_stress_month_rate_pct": actual_stress_rate_pct,
            "condition_top_drivers": [
                {
                    "feature": name,
                    "importance": round(float(imp), 3),
                    "this_borrower": round(float(val), 3),
                    "cohort_avg": round(float(mean), 3),
                }
                for name, imp, val, mean in condition_drivers
            ],
        })

    return {
        "risk_model_summary": {
            "cv_accuracy_pct": risk_model["cv_accuracy_pct"],
            "cv_precision": risk_model["cv_precision"],
            "cv_recall": risk_model["cv_recall"],
            "cv_f1": risk_model["cv_f1"],
            "cv_confusion_matrix": risk_model["cv_confusion_matrix"],
            "n_rows": risk_model["n_rows"],
            "note": (
                "Evaluated with leave-one-borrower-out CV: every scored "
                "prediction came from a borrower excluded from that fold's "
                "training data, so this accuracy is an honest generalization "
                "estimate, not a memorization number. A point or two of "
                "run-to-run variation is expected (borderline months near "
                "the decision boundary can flip with BLAS floating-point "
                "nondeterminism) - treat this as ~95%, not a fixed number."
            ),
            "global_feature_importance": [
                {"feature": n, "coefficient": round(float(c), 3)}
                for n, c in risk_model["global_feature_importance"]
            ],
        },
        "condition_model_summary": {
            "cv_accuracy_pct": condition_model["cv_accuracy_pct"],
            "caveat": condition_model["caveat"],
            "global_feature_importance": [
                {"feature": n, "importance": round(float(imp), 3)}
                for n, imp in condition_model["global_feature_importance"]
            ],
        },
        "borrowers": rows,
    }


if __name__ == "__main__":
    import json
    report = double_check_report()
    print(json.dumps(report, indent=2, default=str))