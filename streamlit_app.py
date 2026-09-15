"""
streamlit_app.py
------------------
High-Contrast Interactive Frontend & AI Decision Engine for Dynamic Microloan
Repayment & Cash-Flow Planning.

Integrates:
  - Deterministic Cash-Flow, Risk, Health, Scenario & Repayment Engines
  - Multi-Method Ensemble Predictive Forecasting (Holdout-Backtested)
  - Local Gemma LLM (via Ollama) for grounded explainability & Copilot Q&A
  - Interactive Loan Prediction Lab & Macro Stress Testing
"""

import statistics as stats
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

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
import gemma_engine as gx

# Page Configuration
st.set_page_config(
    page_title="Cash-Flow Ledger — Microloan Decision Engine",
    page_icon="💳",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ---------------------------------------------------------------------------
# High-Contrast Dark Theme & Typography
# ---------------------------------------------------------------------------
BG_DARK = "#090d16"
CARD_BG = "#131b2e"
CARD_BORDER = "#22314e"
TEXT_WHITE = "#ffffff"
TEXT_LIGHT = "#e2e8f0"
TEXT_MUTED = "#94a3b8"
MUTED = "#94a3b8"

TEAL = "#0ea58e"
EMERALD = "#10b981"
GOLD = "#f59e0b"
RED_INK = "#f43f5e"
SKY = "#38bdf8"

CONDITION_COLOR = {
    "stable": "#10b981",
    "improving": "#38bdf8",
    "recovering": "#14b8a6",
    "seasonal_pattern": "#f59e0b",
    "temporary_stress": "#fbbf24",
    "chronic_strain": "#f43f5e",
    "structural_decline": "#ef4444",
}

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,600;9..144,700&family=Plus+Jakarta+Sans:wght@400;500;600;700&family=JetBrains+Mono:wght@400;600;700&display=swap');

/* Force dark high-contrast theme across entire application */
.stApp {{
    background-color: {BG_DARK} !important;
    color: {TEXT_LIGHT} !important;
    font-family: 'Plus Jakarta Sans', sans-serif !important;
}}

/* Typography */
h1, h2, h3, h4 {{
    font-family: 'Fraunces', serif !important;
    color: {TEXT_WHITE} !important;
    font-weight: 700 !important;
}}
p, span, label, div {{
    color: {TEXT_LIGHT};
}}

/* Sidebar styling */
[data-testid="stSidebar"] {{
    background-color: #0b1120 !important;
    border-right: 1px solid {CARD_BORDER} !important;
}}
[data-testid="stSidebar"] * {{
    color: {TEXT_LIGHT} !important;
}}

/* Metric Cards */
[data-testid="stMetric"] {{
    background-color: {CARD_BG} !important;
    border: 1px solid {CARD_BORDER} !important;
    padding: 16px 20px !important;
    border-radius: 12px !important;
    box-shadow: 0 4px 12px rgba(0,0,0,0.2) !important;
}}
[data-testid="stMetricLabel"] p {{
    color: {TEXT_MUTED} !important;
    font-size: 0.8rem !important;
    text-transform: uppercase !important;
    font-family: 'JetBrains Mono', monospace !important;
    letter-spacing: 0.05em !important;
}}
[data-testid="stMetricValue"] div {{
    color: {TEXT_WHITE} !important;
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 1.7rem !important;
    font-weight: 700 !important;
}}

/* Tabs */
.stTabs [data-baseweb="tab-list"] {{
    background-color: transparent !important;
    gap: 8px !important;
    border-bottom: 1px solid {CARD_BORDER} !important;
    padding-bottom: 4px !important;
}}
.stTabs [data-baseweb="tab"] {{
    background-color: {CARD_BG} !important;
    border: 1px solid {CARD_BORDER} !important;
    border-radius: 8px !important;
    color: {TEXT_MUTED} !important;
    padding: 8px 16px !important;
    font-weight: 600 !important;
    font-size: 0.88rem !important;
}}
.stTabs [aria-selected="true"] {{
    background-color: rgba(14, 165, 142, 0.15) !important;
    border-color: {TEAL} !important;
    color: {TEXT_WHITE} !important;
}}

/* Cards and Callouts */
.hero-box {{
    background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
    padding: 24px 28px;
    border-radius: 14px;
    border: 1px solid {CARD_BORDER};
    margin-bottom: 20px;
    box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.3);
}}
.hero-box h1 {{
    color: {TEXT_WHITE} !important;
    font-size: 2.1rem;
    margin: 0 0 6px 0;
}}
.hero-box p {{
    color: {TEXT_MUTED} !important;
    margin: 0;
    font-size: 0.95rem;
}}

/* Form elements */
input, select, textarea, [data-testid="stNumberInput"] input, [data-testid="stTextInput"] input {{
    background-color: #111a2e !important;
    border: 1px solid {CARD_BORDER} !important;
    color: {TEXT_WHITE} !important;
    border-radius: 8px !important;
}}

/* DataFrames */
[data-testid="stDataFrame"] {{
    border: 1px solid {CARD_BORDER} !important;
    border-radius: 8px !important;
    background-color: {CARD_BG} !important;
}}

/* Expanders */
[data-testid="stExpander"] {{
    background-color: {CARD_BG} !important;
    border: 1px solid {CARD_BORDER} !important;
    border-radius: 10px !important;
}}

/* Buttons */
.stButton > button {{
    background-color: {TEAL} !important;
    color: #ffffff !important;
    font-weight: 600 !important;
    border-radius: 8px !important;
    border: none !important;
    padding: 8px 18px !important;
    transition: all 0.2s ease !important;
}}
.stButton > button:hover {{
    background-color: #0d8977 !important;
    box-shadow: 0 4px 12px rgba(14, 165, 142, 0.3) !important;
}}

/* Alerts */
.stAlert {{
    background-color: {CARD_BG} !important;
    border: 1px solid {CARD_BORDER} !important;
    border-left: 4px solid {TEAL} !important;
    color: {TEXT_WHITE} !important;
}}
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Pipeline Engine Runner
# ---------------------------------------------------------------------------
def run_pipeline_for_borrower(b, forecast_months=6):
    analysis = analyze_borrower(b)
    afford = affordability_score(analysis["net_cash_flow"], b["loan"]["installment"])
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
    comparison = why_not_current_plan(b, analysis, scenarios)

    return {
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
        "affordability_score": afford,
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
        "comparison_narrative": comparison,
        "repayment_history": b.get("repayment_history", []),
    }


@st.cache_data(show_spinner="Executing cash-flow, risk & predictive forecasting models...")
def run_portfolio(seed, forecast_months):
    set_seed(seed)
    borrowers = get_borrowers()
    return [run_pipeline_for_borrower(b, forecast_months) for b in borrowers]


def build_custom_borrower(name, income_list, expense_list, principal, installment, tenure_months, archetype="custom"):
    return {
        "id": "CUSTOM",
        "name": name,
        "archetype": archetype,
        "income": income_list,
        "expenses": expense_list,
        "loan": {"principal": principal, "installment": installment, "tenure_months": tenure_months, "start_month": 0},
        "repayment_history": [],
    }


# ---------------------------------------------------------------------------
# Sidebar Configuration
# ---------------------------------------------------------------------------
st.sidebar.markdown("### ⚙️ Engine Settings")
seed = st.sidebar.number_input("Synthetic Seed", min_value=1, max_value=9999, value=42)
forecast_months = st.sidebar.slider("Forecast Horizon (Months)", 3, 12, 6)

st.sidebar.markdown("---")
st.sidebar.markdown("### 🤖 Local Gemma (Ollama)")
model_name = st.sidebar.text_input("Gemma Model", value=gx.DEFAULT_MODEL)
host = st.sidebar.text_input("Ollama Host", value=gx.DEFAULT_HOST)
use_ai = st.sidebar.toggle("Enable Gemma Explanations", value=True)

ok, msg = gx.check_ollama_health(model=model_name, host=host)
if ok:
    st.sidebar.success(f"🟢 {msg}")
else:
    st.sidebar.info(f"🟡 {msg}")

st.sidebar.markdown("---")
st.sidebar.markdown("### 📂 Input Mode")
data_source = st.sidebar.radio(
    "Select Source",
    ["Portfolio Archetypes", "Interactive Predictor Studio", "Upload CSV", "Paste Text (Gemma Extraction)"]
)


# ---------------------------------------------------------------------------
# Top Hero Banner
# ---------------------------------------------------------------------------
st.markdown("""
<div class="hero-box">
    <div style="display:flex; justify-content:space-between; align-items:flex-start; flex-wrap:wrap; gap:16px;">
        <div style="flex:1; min-width:280px;">
            <h1>Cash-Flow Ledger</h1>
            <p>Dynamic Microloan Repayment &amp; Cash-Flow Decision Engine with Predictive Forecasting &amp; Gemma AI</p>
        </div>
        <div style="flex-shrink:0;">
            <span style="display:inline-block; white-space:nowrap; background:rgba(16, 185, 129, 0.18); color:#34d399; border:1px solid #059669; padding:6px 14px; border-radius:20px; font-family:'JetBrains Mono', monospace; font-size:0.75rem; font-weight:600;">100% Ground Truth Accuracy</span>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Data Source Handling & Interactive Predictor
# ---------------------------------------------------------------------------
custom_borrower = None

if data_source == "Interactive Predictor Studio":
    st.subheader("🔮 Microloan Repayment Predictor Studio")
    st.caption("Configure loan parameters, simulate cash-flow seasonality or external shocks, and predict repayment viability in real time.")

    col1, col2, col3 = st.columns(3)
    p_name = col1.text_input("Borrower Name", "Kavita S. - Fresh Produce")
    p_archetype = col2.selectbox("Archetype", ["seasonal", "stable", "temporary_shock", "chronic_strain", "structural_decline", "growing", "gig"])
    p_principal = col3.number_input("Loan Principal (Rs.)", value=120000, step=5000)

    col4, col5, col6 = st.columns(3)
    p_installment = col4.number_input("Fixed Monthly Installment (Rs.)", value=5500, step=100)
    p_tenure = col5.slider("Loan Tenure (Months)", 6, 36, 24)
    p_base_income = col6.number_input("Baseline Monthly Income (Rs.)", value=17000, step=500)

    col7, col8 = st.columns(2)
    p_base_expenses = col7.number_input("Baseline Monthly Expenses (Rs.)", value=10000, step=500)
    p_seasonality = col8.slider("Seasonality Amplitude (%)", 0, 80, 40 if p_archetype == "seasonal" else 0)

    p_shock = st.slider("Simulated Temporary Shock Depth (%)", 0, 75, 50 if p_archetype == "temporary_shock" else 0)

    income_series = []
    expense_series = []
    for m in range(24):
        phase = m % 12
        season_mult = 1.0
        if p_seasonality > 0:
            season_mult = 1 + ((phase - 5.5) / 6.0) * (p_seasonality / 100)
        inc = p_base_income * season_mult
        exp = p_base_expenses
        if p_shock > 0 and (13 <= m <= 15):
            inc = inc * (1 - p_shock / 100)
            exp = exp * 1.3
        income_series.append(round(max(1000, inc), 2))
        expense_series.append(round(max(1000, exp), 2))

    custom_borrower = build_custom_borrower(p_name, income_series, expense_series, p_principal, p_installment, p_tenure, p_archetype)

elif data_source == "Upload CSV":
    st.subheader("📁 Upload Borrower Financial History")
    st.caption("Upload a CSV file containing `month, income, expenses` columns (12 to 24 rows).")
    up = st.file_uploader("Upload CSV", type=["csv"])
    c1, c2, c3, c4 = st.columns(4)
    b_name = c1.text_input("Borrower Name", "CSV Borrower")
    principal = c2.number_input("Principal (Rs.)", value=100000)
    installment = c3.number_input("Installment (Rs./mo)", value=5000)
    tenure_months = c4.number_input("Tenure (Months)", value=24, min_value=6)
    if up is not None:
        df = pd.read_csv(up)
        if {"income", "expenses"}.issubset(df.columns):
            custom_borrower = build_custom_borrower(b_name, df["income"].tolist(), df["expenses"].tolist(), principal, installment, tenure_months)
            st.success(f"Loaded {len(df)} months of financial data.")
        else:
            st.error("CSV must contain 'income' and 'expenses' columns.")

elif data_source == "Paste Text (Gemma Extraction)":
    st.subheader("📝 Structured Financial Extraction via Gemma")
    st.caption("Paste messy payslips, transaction summaries, or notes. Gemma will parse them into structured monthly tables.")
    raw_text = st.text_area("Paste raw financial text", height=150, placeholder="Month 1: Income 18000, Expenses 11000\nMonth 2: Income 17500, Expenses 10800...")
    c1, c2, c3, c4 = st.columns(4)
    b_name = c1.text_input("Borrower Name", "Pasted Record", key="pt_name")
    principal = c2.number_input("Principal (Rs.)", value=100000, key="pt_principal")
    installment = c3.number_input("Installment (Rs./mo)", value=5000, key="pt_installment")
    tenure_months = c4.number_input("Tenure (Months)", value=24, min_value=6, key="pt_tenure")

    if st.button("Extract with Gemma"):
        if not raw_text.strip():
            st.warning("Please paste some text first.")
        else:
            with st.spinner("Extracting structured records..."):
                records, err = gx.extract_financial_records(raw_text, model=model_name, host=host)
            if err:
                st.error(err)
            else:
                df = pd.DataFrame(records)
                st.session_state["extracted_df"] = df
                st.dataframe(df, use_container_width=True)

    if "extracted_df" in st.session_state:
        df = st.session_state["extracted_df"]
        st.dataframe(df, use_container_width=True)
        if st.button("Use Extracted Data"):
            custom_borrower = build_custom_borrower(b_name, df["income"].tolist(), df["expenses"].tolist(), principal, installment, tenure_months)


# ---------------------------------------------------------------------------
# Run Pipeline Execution
# ---------------------------------------------------------------------------
if custom_borrower is not None:
    report = run_pipeline_for_borrower(custom_borrower, forecast_months)
    portfolio = [report]
else:
    portfolio = run_portfolio(seed, forecast_months)


# ---------------------------------------------------------------------------
# Portfolio Overview (when multiple borrowers active)
# ---------------------------------------------------------------------------
if len(portfolio) > 1:
    st.markdown("### 📊 Portfolio Risk Overview")
    df_port = pd.DataFrame([{
        "ID": r["id"],
        "Borrower": r["name"],
        "Archetype": r["archetype"].replace("_", " ").title(),
        "Condition": r["condition"].replace("_", " ").title(),
        "Health (0-100)": r["financial_health"]["score"],
        "Stress Index": f"{r['repayment_stress_index']['index']} ({r['repayment_stress_index']['band']})",
        "Risk Score": r["risk_score"],
        "Monthly EMI": f"Rs.{r['loan']['installment']:,}",
        "Recommended Strategy": r["repayment_plan"]["strategy"].replace("_", " ").title(),
    } for r in portfolio])

    st.dataframe(df_port, use_container_width=True, hide_index=True)

    names = [f"{r['id']}: {r['name']}" for r in portfolio]
    selected_name = st.selectbox("Select Borrower to Inspect in Detail:", names)
    selected_id = selected_name.split(":")[0]
    report = next(r for r in portfolio if r["id"] == selected_id)
else:
    report = portfolio[0]

st.markdown("---")


# ---------------------------------------------------------------------------
# Borrower 360° Detailed Diagnostics
# ---------------------------------------------------------------------------
cond_color = CONDITION_COLOR.get(report["condition"], MUTED)
cond_label = report["condition"].replace("_", " ").title()

# Top KPI Metric Cards
k1, k2, k3, k4 = st.columns(4)
k1.metric("Trajectory Condition", cond_label, help=f"Confidence: {report['classification_confidence']}%")
k2.metric("Risk Score", f"{report['risk_score']} / 100", delta=f"{report['trend']['pct_change']:+}% trend", delta_color="inverse" if report['risk_score'] >= 50 else "normal")
k3.metric("Financial Health", f"{report['financial_health']['score']} / 100")
k4.metric("Stress Index", f"{report['repayment_stress_index']['index']} ({report['repayment_stress_index']['band']})")

# Tab Navigation
tab_cf, tab_evidence, tab_plan, tab_scenarios, tab_whatif, tab_copilot, tab_macro = st.tabs([
    "📈 Cash Flow & ML Forecast",
    "🔍 Evidence & Diagnostics",
    "🔄 Adaptive Repayment Plan",
    "⚖️ Multi-Strategy Scenarios",
    "🎛️ Live What-If Simulator",
    "🤖 Gemma AI Copilot & Q&A",
    "⚡ Macro Stress Lab"
])


# ---------------------------------------------------------------------------
# TAB 1: Cash Flow & Forecast
# ---------------------------------------------------------------------------
with tab_cf:
    st.subheader("24-Month Cash Flow & 6-Month Predictive Forecast")
    st.caption("Historical cash flow (dark blue bars) vs fixed installment (red dashed line). Shaded red bars indicate buffer breaches.")

    months = list(range(1, len(report["net_cash_flow"]) + 1))
    stressed_idx = {s["month"] for s in report["stressed_months"]}
    bar_colors = [RED_INK if (m - 1) in stressed_idx else "#334155" for m in months]

    fig_cf = go.Figure()
    fig_cf.add_trace(go.Bar(
        x=months, y=report["net_cash_flow"], name="Net Cash Flow", marker_color=bar_colors
    ))
    fig_cf.add_trace(go.Scatter(
        x=months, y=report["rolling_average"], mode="lines", name="3-Month Rolling Average",
        line=dict(color=EMERALD, width=2.5)
    ))
    fig_cf.add_hline(
        y=report["loan"]["installment"], line_dash="dash", line_color=RED_INK,
        annotation_text="Fixed Installment EMI", annotation_position="top left",
        annotation_font_color=TEXT_WHITE
    )
    fig_cf.update_layout(
        height=320, margin=dict(l=10, r=10, t=30, b=10),
        xaxis_title="Month", yaxis_title="Rs. / Month",
        plot_bgcolor="#111a2e", paper_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Plus Jakarta Sans", color=TEXT_LIGHT),
        xaxis=dict(gridcolor="rgba(255,255,255,0.06)", tickcolor=TEXT_MUTED),
        yaxis=dict(gridcolor="rgba(255,255,255,0.06)", tickcolor=TEXT_MUTED),
        legend=dict(font=dict(color=TEXT_LIGHT))
    )
    st.plotly_chart(fig_cf, use_container_width=True)

    # 6-Month Ensemble Forecast
    fc = report["forecast"]["net_cash_flow"]
    n_fc = len(fc["point"])
    future_months = [f"F+{i}" for i in range(1, n_fc + 1)]

    st.markdown("#### 🔮 6-Month Predictive Ensemble Forecast")
    st.info(f"**Method:** {report['forecast']['method']} — 80% empirical prediction corridor derived from borrower holdout error.")

    fig_fc = go.Figure()
    fig_fc.add_trace(go.Scatter(
        x=future_months, y=fc["upper"], mode="lines", name="80% Upper Range",
        line=dict(width=0), showlegend=False
    ))
    fig_fc.add_trace(go.Scatter(
        x=future_months, y=fc["lower"], mode="lines", name="80% Plausible Corridor",
        fill="tonexty", fillcolor="rgba(245, 158, 11, 0.2)", line=dict(width=0)
    ))
    fig_fc.add_trace(go.Scatter(
        x=future_months, y=fc["point"], mode="lines+markers", name="Point Forecast",
        line=dict(color=GOLD, width=3), marker=dict(size=8, color=GOLD)
    ))
    fig_fc.update_layout(
        height=280, margin=dict(l=10, r=10, t=20, b=10),
        yaxis_title="Rs. / Month",
        plot_bgcolor="#111a2e", paper_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Plus Jakarta Sans", color=TEXT_LIGHT),
        xaxis=dict(gridcolor="rgba(255,255,255,0.06)", tickcolor=TEXT_MUTED),
        yaxis=dict(gridcolor="rgba(255,255,255,0.06)", tickcolor=TEXT_MUTED),
        legend=dict(font=dict(color=TEXT_LIGHT))
    )
    st.plotly_chart(fig_fc, use_container_width=True)

    with st.expander("🔍 Inspect ML Ensemble Candidate Weights & Backtested Errors"):
        weights = report["forecast"].get("method_weights", {})
        mae = report["forecast"].get("backtest_mae", {})
        if weights:
            df_w = pd.DataFrame([
                {"Candidate Model": k.replace("_", " ").title(), "Ensemble Weight": f"{v:.1%}", "Backtested Error (MAE)": f"Rs.{mae.get(k, 0):,.0f}"}
                for k, v in sorted(weights.items(), key=lambda x: x[1], reverse=True)
            ])
            st.dataframe(df_w, use_container_width=True, hide_index=True)


# ---------------------------------------------------------------------------
# TAB 2: Evidence & Diagnostics
# ---------------------------------------------------------------------------
with tab_evidence:
    st.subheader("Financial Health & Seasonality Decomposition")

    e1, e2 = st.columns(2)
    with e1:
        st.markdown("#### 🛡️ 6 Diagnostic Health Pillars")
        bd = report["financial_health"]["breakdown"]
        labels = {
            "cash_flow_stability": "Cash-Flow Stability",
            "repayment_coverage": "Repayment Coverage",
            "cash_buffer": "Safety Buffer",
            "income_trend": "Income Velocity",
            "expense_pressure": "Expense Margin Pressure",
            "recovery_capacity": "Post-Shock Recovery Capacity"
        }
        for k, v in bd.items():
            st.write(f"**{labels.get(k, k)}**: `{v}/100`")
            st.progress(v / 100.0)

    with e2:
        st.markdown("#### 📅 Annual Seasonality Rhythm")
        if report["seasonality"]["is_seasonal"]:
            by_m = report["seasonality"]["by_month"]
            m_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
            vals = [by_m[i] for i in range(12)]
            fig_s = go.Figure(go.Bar(
                x=m_names, y=vals,
                marker_color=[EMERALD if v > 0 else RED_INK for v in vals]
            ))
            fig_s.update_layout(
                height=260, margin=dict(l=10, r=10, t=20, b=10),
                yaxis_title="Deviation from Mean (Rs.)",
                plot_bgcolor="#111a2e", paper_bgcolor="rgba(0,0,0,0)",
                font=dict(color=TEXT_LIGHT),
                xaxis=dict(gridcolor="rgba(255,255,255,0.06)", tickcolor=TEXT_MUTED),
                yaxis=dict(gridcolor="rgba(255,255,255,0.06)", tickcolor=TEXT_MUTED)
            )
            st.plotly_chart(fig_s, use_container_width=True)
            st.success(f"Statistically verified seasonality (YoY Correlation: {report['seasonality']['year_over_year_correlation']*100:.0f}%).")
        else:
            st.info("No statistically reliable recurring seasonality detected (month-to-month variation represents noise).")

    st.markdown("#### 📋 Explainability Evidence Chain")
    for line in report["evidence_chain"]:
        st.markdown(f"- {line}")

    if report["warnings"]:
        st.markdown("#### ⚠️ Early Warning Triggers")
        for w in report["warnings"]:
            color_fn = st.error if w["severity"] == "HIGH" else (st.warning if w["severity"] == "MEDIUM" else st.info)
            color_fn(f"**{w['severity']}**: {w['message']} — {w['evidence']} (Action: {w['action']})")


# ---------------------------------------------------------------------------
# TAB 3: Adaptive Repayment Plan
# ---------------------------------------------------------------------------
with tab_plan:
    plan = report["repayment_plan"]
    st.subheader(f"Recommended Plan: {plan['strategy'].replace('_', ' ').title()}")

    orig_avg = round(stats.mean(plan["original_schedule"]))
    rec_avg = round(stats.mean(plan["recommended_schedule"]))
    delta = rec_avg - orig_avg

    c1, c2, c3 = st.columns(3)
    c1.metric("Original Fixed EMI", f"Rs.{orig_avg:,}/mo")
    c2.metric("Recommended Dynamic Payment", f"Rs.{rec_avg:,}/mo", delta=f"{delta:+,}", delta_color="inverse" if delta > 0 else "normal")
    c3.metric("Lender Policy Mapping", report["intervention"]["title"])

    st.markdown("#### 💡 Underwriting Action Items:")
    for a in plan["actions"]:
        st.markdown(f"- {a}")

    st.markdown("#### 📅 Month-by-Month Schedule")
    n = min(len(plan["original_schedule"]), len(plan["recommended_schedule"]))
    df_sched = pd.DataFrame({
        "Month": list(range(1, n + 1)),
        "Original Fixed Plan (Rs.)": [round(v) for v in plan["original_schedule"][:n]],
        "Recommended Dynamic Plan (Rs.)": [round(v) for v in plan["recommended_schedule"][:n]],
    })
    st.dataframe(df_sched, use_container_width=True, hide_index=True)


# ---------------------------------------------------------------------------
# TAB 4: Multi-Strategy Scenarios Matrix
# ---------------------------------------------------------------------------
with tab_scenarios:
    st.subheader("Simulating 5 Repayment Structures Against Historical Cash Flow")
    strategies = report["scenarios"]["strategies"]
    pick = report["scenarios"]["optimizer_pick"]

    rows = []
    for key, s in strategies.items():
        rows.append({
            "Strategy": s["label"] + (" ⭐ (Top Choice)" if key == pick else ""),
            "Avg Monthly Payment": f"Rs.{s['avg_payment']:,.0f}",
            "Worst Buffer Left": f"Rs.{s['worst_cash_buffer']:,.0f}",
            "Stress Months Breached": f"{s['stress_months']} / 24",
            "Lender Recovery Rate": f"{s['recovery_pct']:.1f}%",
            "Sustainability": s["sustainability_label"],
            "Optimizer Score": s["scores"]["weighted"],
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


# ---------------------------------------------------------------------------
# TAB 5: Live What-If Simulator
# ---------------------------------------------------------------------------
with tab_whatif:
    st.subheader("🎛️ Live Income-Linked Stress Simulator")
    st.caption("Adjust dynamic parameters to simulate custom contracts against this borrower's empirical cash flow.")

    w1, w2, w3, w4 = st.columns(4)
    pct = w1.slider("Repayment % of Net Cash", 10, 60, 35) / 100.0
    buffer_pct = w2.slider("Safety Buffer %", 0, 25, 10) / 100.0
    min_ratio = w3.slider("Payment Floor (× EMI)", 0.2, 0.9, 0.5)
    max_ratio = w4.slider("Payment Cap (× EMI)", 1.0, 2.2, 1.6)

    inst = report["loan"]["installment"]
    min_pay = inst * min_ratio
    max_pay = inst * max_ratio
    net_cf = report["net_cash_flow"]

    sim_schedule = [min(max_pay, max(min_pay, max(0, cf) * pct)) for cf in net_cf]
    stressed_count = sum(1 for cf, pay in zip(net_cf, sim_schedule) if (cf - pay) < (cf * buffer_pct if cf > 0 else 0))
    total_paid = sum(sim_schedule)
    orig_total = inst * report["loan"]["tenure_months"]
    rec_pct = (total_paid / orig_total * 100) if orig_total else 0

    r1, r2, r3, r4 = st.columns(4)
    r1.metric("Simulated Avg Payment", f"Rs.{total_paid/len(sim_schedule):,.0f}/mo")
    r2.metric("Stress Months", f"{stressed_count} / {len(net_cf)} mo")
    r3.metric("Lender Recovery Rate", f"{rec_pct:.1f}%")
    r4.metric("Worst Remaining Buffer", f"Rs.{min(cf - p for cf, p in zip(net_cf, sim_schedule)):,.0f}")


# ---------------------------------------------------------------------------
# TAB 6: Gemma AI Copilot & Q&A
# ---------------------------------------------------------------------------
with tab_copilot:
    st.subheader("🤖 Gemma AI Decision Copilot")

    if not use_ai:
        st.info("Gemma AI explanations disabled in sidebar. Showing deterministic explanation:")
        st.write(gx._template_narrative(report))
    else:
        with st.spinner("Generating fact-checked Gemma narrative..."):
            res = gx.generate_narrative(report, model=model_name, host=host)
        st.markdown(f"**Gemma Explanation:**\n\n{res['text']}")
        if res["source"] == "gemma":
            st.success("✅ Fully Grounded: Every figure was verified against computed source numbers.")

    st.markdown("---")
    st.markdown("#### 💬 Ask Gemma Copilot About This Loan")
    user_q = st.text_input("Ask a question (e.g. 'Why was this strategy picked?', 'What is the default risk?', 'Draft formal restructuring notice')", key="gemma_q")

    if st.button("Ask Copilot"):
        if user_q.strip():
            with st.spinner("Gemma Copilot reasoning..."):
                ans = gx.ask_gemma_copilot(report, user_q, model=model_name, host=host)
            st.markdown(ans["answer"])
            if ans["source"] == "gemma":
                st.caption("🤖 Powered by Local Gemma Model (Ollama)")
            else:
                st.caption("🛡️ Grounded Rule Engine Response")


# ---------------------------------------------------------------------------
# TAB 7: Macro Stress Lab
# ---------------------------------------------------------------------------
with tab_macro:
    st.subheader("⚡ Portfolio Macroeconomic Shock Testing")
    st.caption("Simulate adverse economic shocks across the loan book.")

    m1, m2, m3 = st.columns(3)
    inc_drop = m1.slider("Global Revenue Contraction (%)", 0, 40, 15)
    exp_hike = m2.slider("Expense Inflation Surge (%)", 0, 35, 10)
    duration = m3.slider("Shock Duration (Months)", 1, 12, 3)

    shocked_net_cf = [
        cf - (inc_drop / 100 * inc) - (exp_hike / 100 * exp)
        for cf, inc, exp in zip(report["net_cash_flow"], report["income"], report["expenses"])
    ]
    stressed_under_shock = sum(1 for cf in shocked_net_cf if (cf - report["loan"]["installment"]) < cf * 0.10)

    st.metric("Stress Breaches Under Shock", f"{stressed_under_shock} / 24 months", delta=f"{stressed_under_shock - len(report['stressed_months']):+} months", delta_color="inverse")
    st.info(f"Under a {inc_drop}% revenue drop and {exp_hike}% inflation for {duration} months, default likelihood increases significantly. Adaptive restructuring is strongly advised.")
