"""
data_generator.py
------------------
Generates 24 months of synthetic income/expense/transaction history for a
set of microfinance borrowers, each representing a distinct real-world
cash-flow archetype:

  1. Stable      - regular salaried-style income, low volatility
  2. Seasonal     - farmer/trader with two annual harvest-linked peaks
  3. Gig/Irregular - informal worker, high month-to-month noise, no trend
  4. Temporary Shock - stable borrower who hits a 3-month external shock
                        (medical bill, family event) then recovers
  5. Structural Decline - borrower whose income genuinely erodes over the
                           back half of the window (lost client, market shift)
  6. Growing      - small business on a genuine upward trajectory
  7. Chronic Strain - no trend, no season, just consistently thin margin
                        relative to the installment (scattered stress)
  8. Recovering   - an old, fully-resolved shock followed by genuine growth

Each borrower also gets a simulated month-by-month repayment history
(scheduled vs. actual, missed/partial/on-time, days late) and a
`ground_truth` label used only by evaluate.py to score the classifier -
never fed into the classifier itself.

Reproducible via `python3 data_generator.py --seed <n>` (default 42).
No external libraries are used so this runs with a bare `python3`.
"""

import argparse
import random
import math

MONTHS = 24
_SEED = 42
random.seed(_SEED)


def set_seed(seed):
    """Re-seed and rebuild the borrower list so the whole dataset is
    reproducible for a given --seed, e.g. `python3 data_generator.py --seed 7`."""
    global _SEED
    _SEED = seed
    random.seed(seed)
    BORROWERS.clear()
    _build_all_borrowers()


def _clamp(x, lo):
    return max(lo, x)


def _build_series(base, pattern_fn, noise_pct=0.05):
    series = []
    for m in range(MONTHS):
        val = pattern_fn(m, base)
        noise = val * random.uniform(-noise_pct, noise_pct)
        series.append(round(_clamp(val + noise, 0), 2))
    return series


def _stable(base):
    return _build_series(base, lambda m, b: b, noise_pct=0.04)


def _seasonal(base):
    # Two harvest peaks per year (month 3-4 and month 9-10), lean months between
    def pat(m, b):
        phase = (m % 12)
        peak = math.exp(-((phase - 3.5) ** 2) / 4.0) + math.exp(-((phase - 9.5) ** 2) / 4.0)
        return b * (0.55 + 0.9 * peak)
    return _build_series(base, pat, noise_pct=0.08)


def _gig(base):
    def pat(m, b):
        return b
    return _build_series(base, pat, noise_pct=0.35)


def _temporary_shock(base, shock_start=13, shock_len=3, depth=0.55):
    def pat(m, b):
        if shock_start <= m < shock_start + shock_len:
            return b * (1 - depth)
        return b
    return _build_series(base, pat, noise_pct=0.05)


def _structural_decline(base, decline_start=12, monthly_drop=0.045):
    def pat(m, b):
        if m < decline_start:
            return b
        return b * (1 - monthly_drop) ** (m - decline_start)
    return _build_series(base, pat, noise_pct=0.05)


def _growing(base, monthly_growth=0.03):
    def pat(m, b):
        return b * (1 + monthly_growth) ** m
    return _build_series(base, pat, noise_pct=0.06)


def _flat_expenses(base, noise_pct=0.06):
    return _build_series(base, lambda m, b: b, noise_pct=noise_pct)


def _expenses_with_bump(base, bump_months, factor=1.4, noise_pct=0.06):
    def pat(m, b):
        return b * factor if m in bump_months else b
    return _build_series(base, pat, noise_pct=noise_pct)


def _chronic_strain(base):
    """No trend, no seasonality - just consistently thin margin over the
    installment, so random noise alone produces recurring (but scattered)
    stress clusters throughout the window. This is the archetype that
    should NOT be mistaken for a single shock or a seasonal rhythm."""
    return _build_series(base, lambda m, b: b, noise_pct=0.18)


def _recovering(base, shock_start=2, shock_len=4, depth=0.5, growth_after=0.018):
    """A shock early in the window that fully resolved long ago, followed
    by genuine, sustained improvement - used to check the classifier does
    NOT keep flagging old, resolved stress."""
    def pat(m, b):
        if shock_start <= m < shock_start + shock_len:
            return b * (1 - depth)
        months_since_recovery = max(0, m - (shock_start + shock_len))
        return b * (1 + growth_after) ** months_since_recovery
    return _build_series(base, pat, noise_pct=0.05)


def _simulate_repayment_history(income, expenses, installment, seed_offset=0):
    """Simulates scheduled vs. actual repayment per month. This is used as
    ONE input signal among several (never the sole risk driver) and is
    driven by the same underlying cash flow, not an independent random
    process, so it stays internally consistent with the rest of the
    borrower's story."""
    rng = random.Random(_SEED * 1000 + seed_offset)
    history = []
    for m, (inc, exp) in enumerate(zip(income, expenses)):
        net = inc - exp
        coverage = (net / installment) if installment else 0
        if coverage >= 1.05:
            status, actual, days_late = "on_time", installment, 0
        elif coverage >= 0.85:
            if rng.random() < 0.7:
                status, actual, days_late = "on_time", installment, rng.choice([0, 0, 0, 2, 5])
            else:
                actual = round(installment * rng.uniform(0.6, 0.9), 2)
                status, days_late = "partial", rng.choice([3, 7, 10])
        else:
            roll = rng.random()
            if roll < 0.45:
                status, actual, days_late = "missed", 0.0, 0
            else:
                actual = round(installment * rng.uniform(0.3, 0.7), 2)
                status, days_late = "partial", rng.choice([7, 12, 18])
        history.append({
            "month": m, "scheduled": installment, "actual": actual,
            "status": status, "days_late": days_late,
        })
    return history


BORROWERS = []


def _build_borrower_dict(bid, name, archetype, income, expenses, loan, ground_truth, seed_offset):
    repayment_history = _simulate_repayment_history(income, expenses, loan["installment"],
                                                      seed_offset=seed_offset)
    return {
        "id": bid,
        "name": name,
        "archetype": archetype,
        "income": income,
        "expenses": expenses,
        "loan": loan,
        "ground_truth": ground_truth,  # expected condition label(s), for evaluate.py only
        "repayment_history": repayment_history,
    }


def _add_borrower(bid, name, archetype, income, expenses, loan, ground_truth):
    BORROWERS.append(_build_borrower_dict(bid, name, archetype, income, expenses, loan,
                                           ground_truth, seed_offset=hash(bid) % 1000))


def _build_all_borrowers():
    # 1. Stable salaried-style borrower
    income = _stable(18000)
    expenses = _flat_expenses(11000)
    _add_borrower("B01", "Anitha R. - Tailoring Shop", "stable", income, expenses,
                  {"principal": 120000, "installment": 5500, "tenure_months": 24, "start_month": 0},
                  ground_truth=["stable", "improving"])

    # 2. Seasonal farmer/trader
    income = _seasonal(16000)
    expenses = _flat_expenses(9000)
    _add_borrower("B02", "Manjunath K. - Areca Nut Farmer", "seasonal", income, expenses,
                  {"principal": 150000, "installment": 6250, "tenure_months": 24, "start_month": 0},
                  ground_truth=["seasonal_pattern"])

    # 3. Gig / irregular informal worker
    income = _gig(14000)
    expenses = _flat_expenses(9500)
    _add_borrower("B03", "Farida S. - App-based Delivery", "gig", income, expenses,
                  {"principal": 90000, "installment": 4200, "tenure_months": 24, "start_month": 0},
                  ground_truth=["chronic_strain", "temporary_stress", "stable", "recovering"])

    # 4. Temporary shock (medical event months 13-15), then recovers
    income = _temporary_shock(17000, shock_start=13, shock_len=3, depth=0.5)
    expenses = _expenses_with_bump(9500, bump_months={13, 14}, factor=1.6)
    _add_borrower("B04", "Ravi P. - Auto Rickshaw Owner", "temporary_shock", income, expenses,
                  {"principal": 110000, "installment": 5200, "tenure_months": 24, "start_month": 0},
                  ground_truth=["temporary_stress"])

    # 5. Structural decline (lost a major client from month 12 onward)
    income = _structural_decline(19000, decline_start=12, monthly_drop=0.05)
    expenses = _flat_expenses(10500)
    _add_borrower("B05", "Suresh N. - Small Kirana Store", "structural_decline", income, expenses,
                  {"principal": 140000, "installment": 6100, "tenure_months": 24, "start_month": 0},
                  ground_truth=["structural_decline"])

    # 6. Genuinely growing small business
    income = _growing(13000, monthly_growth=0.028)
    expenses = _flat_expenses(8000)
    _add_borrower("B06", "Deepa M. - Home Catering Business", "growing", income, expenses,
                  {"principal": 80000, "installment": 3800, "tenure_months": 24, "start_month": 0},
                  ground_truth=["improving", "stable"])

    # 7. Chronic strain - installment simply too tight, no trend, no season
    income = _chronic_strain(13200)
    expenses = _flat_expenses(9800)
    _add_borrower("B07", "Yusuf B. - Street Vendor", "chronic_strain", income, expenses,
                  {"principal": 95000, "installment": 4600, "tenure_months": 24, "start_month": 0},
                  ground_truth=["chronic_strain"])

    # 8. Recovering - old resolved shock, then sustained genuine growth
    income = _recovering(15500, shock_start=2, shock_len=4, depth=0.5, growth_after=0.02)
    expenses = _flat_expenses(9200)
    _add_borrower("B08", "Lakshmi V. - Home Catering Startup", "recovering", income, expenses,
                  {"principal": 100000, "installment": 4400, "tenure_months": 24, "start_month": 0},
                  ground_truth=["recovering", "improving", "stable"])


_build_all_borrowers()


def get_borrowers():
    return BORROWERS

def generate_synthetic_cohort(n_per_archetype=20, seed=123):
    """Generates a larger, disposable cohort of synthetic borrower variants,
    for TRAINING/AUGMENTATION purposes only (see
    ml_engine.train_condition_model) - never used by the rule-based engine
    or shown in the dashboard as real borrowers.

    Uses the exact same 8 archetype-generating functions as the real 8
    borrowers above, but randomizes the base income level and each
    archetype's defining parameters (shock depth/timing, growth rate,
    decline rate, etc.) so the model sees more than one instance of each
    pattern. `ground_truth` is fixed per archetype - same convention as
    the real borrowers, never derived from a model.

    Runs on its own local RNG state (saved and restored around
    generation) so it never disturbs the main, reproducible 8-borrower
    dataset used everywhere else in the pipeline.
    """
    saved_state = random.getstate()
    random.seed(seed)
    cohort = []

    archetype_specs = [
        ("stable", ["stable", "improving"],
         lambda inc, exp: (_stable(inc), _flat_expenses(exp))),
        ("seasonal", ["seasonal_pattern"],
         lambda inc, exp: (_seasonal(inc), _flat_expenses(exp))),
        ("gig", ["chronic_strain", "temporary_stress", "stable", "recovering"],
         lambda inc, exp: (_gig(inc), _flat_expenses(exp))),
        ("temporary_shock", ["temporary_stress"],
         lambda inc, exp: (
             _temporary_shock(inc, shock_start=random.randint(10, 16),
                               shock_len=random.choice([2, 3, 4]),
                               depth=random.uniform(0.35, 0.65)),
             _expenses_with_bump(exp, bump_months=set(range(12, 15)),
                                  factor=random.uniform(1.3, 1.8)))),
        ("structural_decline", ["structural_decline"],
         lambda inc, exp: (
             _structural_decline(inc, decline_start=random.randint(8, 14),
                                  monthly_drop=random.uniform(0.03, 0.07)),
             _flat_expenses(exp))),
        ("growing", ["improving", "stable"],
         lambda inc, exp: (_growing(inc, monthly_growth=random.uniform(0.02, 0.04)),
                            _flat_expenses(exp))),
        ("chronic_strain", ["chronic_strain"],
         lambda inc, exp: (_chronic_strain(inc), _flat_expenses(exp))),
        ("recovering", ["recovering", "improving", "stable"],
         lambda inc, exp: (
             _recovering(inc, shock_start=random.randint(1, 4),
                          shock_len=random.choice([3, 4, 5]),
                          depth=random.uniform(0.35, 0.6),
                          growth_after=random.uniform(0.012, 0.025)),
             _flat_expenses(exp))),
    ]

    idx = 0
    for archetype, ground_truth, build_fn in archetype_specs:
        for _ in range(n_per_archetype):
            idx += 1
            base_income = random.uniform(10000, 20000)
            base_expense = base_income * random.uniform(0.55, 0.75)
            income, expenses = build_fn(base_income, base_expense)
            avg_income = sum(income) / len(income)
            installment = round(random.uniform(0.28, 0.4) * avg_income, -2) or 1000.0
            principal = installment * 24
            bid = f"SYN-{archetype}-{idx}"
            repayment_history = _simulate_repayment_history(
                income, expenses, installment, seed_offset=idx * 7 + seed
            )
            cohort.append({
                "id": bid,
                "name": f"Synthetic {archetype} #{idx}",
                "archetype": archetype,
                "income": income,
                "expenses": expenses,
                "loan": {"principal": round(principal, 2), "installment": round(installment, 2),
                         "tenure_months": 24, "start_month": 0},
                "ground_truth": ground_truth,
                "repayment_history": repayment_history,
            })

    random.setstate(saved_state)
    return cohort


def generate_synthetic_cohort(n_per_archetype=20, seed=123):
    """Generates MANY more borrowers per archetype than the 8 hand-picked
    demo cases, by re-running the same pattern generators (`_stable`,
    `_seasonal`, etc.) with randomized bases, noise, shock timing, and loan
    sizing. Used only to give ml_engine.py's condition model enough labeled
    rows to have an honest shot at generalizing - the original 8 borrowers
    stay the system's "real" demo cases everywhere else (dashboard,
    evaluate.py, risk_engine.py).

    Uses a private random.Random-style save/restore of the global `random`
    module state so this never disturbs the reproducibility of the main
    8-borrower dataset built at import time with seed=42.
    """
    saved_state = random.getstate()
    random.seed(seed)
    cohort = []

    archetype_specs = [
        ("stable", lambda base: _stable(base), ["stable", "improving"]),
        ("seasonal", lambda base: _seasonal(base), ["seasonal_pattern"]),
        ("gig", lambda base: _gig(base),
         ["chronic_strain", "temporary_stress", "stable", "recovering"]),
        ("temporary_shock", lambda base: _temporary_shock(
            base, shock_start=random.randint(9, 17), shock_len=random.choice([2, 3, 4]),
            depth=random.uniform(0.35, 0.65)), ["temporary_stress"]),
        ("structural_decline", lambda base: _structural_decline(
            base, decline_start=random.randint(9, 15), monthly_drop=random.uniform(0.03, 0.07)),
         ["structural_decline"]),
        ("growing", lambda base: _growing(base, monthly_growth=random.uniform(0.015, 0.04)),
         ["improving", "stable"]),
        ("chronic_strain", lambda base: _chronic_strain(base), ["chronic_strain"]),
        ("recovering", lambda base: _recovering(
            base, shock_start=random.randint(1, 4), shock_len=random.choice([3, 4, 5]),
            depth=random.uniform(0.35, 0.6), growth_after=random.uniform(0.01, 0.025)),
         ["recovering", "improving", "stable"]),
    ]

    idx = 0
    for archetype, income_fn, ground_truth in archetype_specs:
        for _ in range(n_per_archetype):
            idx += 1
            income_base = random.uniform(11000, 21000)
            expense_base = income_base * random.uniform(0.5, 0.75)
            income = income_fn(income_base)
            expenses = _flat_expenses(expense_base, noise_pct=random.uniform(0.04, 0.09))

            mean_income = sum(income) / len(income)
            typical_net = mean_income - expense_base
            # Randomize how tightly the installment fits typical cash flow
            # so we get a real mix of comfortable and genuinely tight cases
            # within each archetype, not just archetype-level separation.
            installment = round(max(500.0, typical_net * random.uniform(0.35, 0.95)), 2)
            loan = {
                "principal": round(installment * 20, 2), "installment": installment,
                "tenure_months": 24, "start_month": 0,
            }
            bid = f"SYN-{archetype}-{idx:03d}"
            cohort.append(_build_borrower_dict(
                bid, f"Synthetic {archetype} #{idx}", archetype, income, expenses, loan,
                ground_truth, seed_offset=idx
            ))

    random.setstate(saved_state)
    return cohort


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate synthetic microloan borrower data.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility.")
    args = parser.parse_args()
    set_seed(args.seed)
    print(f"Generated {len(BORROWERS)} borrowers with seed={args.seed}.")
    for b in BORROWERS:
        print(f"  {b['id']}: {b['name']} ({b['archetype']}) - expected: {b['ground_truth']}")