# Dynamic Microloan Repayment & Cash-Flow Planning — Prototype

## Table of Contents

1. [Overview](#overview)
2. [Problem Statement](#problem-statement)
3. [System Architecture](#system-architecture)
4. [Project Structure](#project-structure)
5. [Technical Components](#technical-components)
6. [How to Run the Project](#how-to-run-the-project)
7. [Detailed Setup Instructions](#detailed-setup-instructions)
8. [Project Workflow](#project-workflow)
9. [Understanding the Output](#understanding-the-output)
10. [Key Features & Innovations](#key-features--innovations)
11. [Limitations](#limitations)
12. [Troubleshooting](#troubleshooting)
13. [Technology Stack](#technology-stack)
14. [Future Enhancements](#future-enhancements)

---

## Overview

This is a **working, end-to-end prototype** for dynamic microloan repayment and cash-flow planning. The system addresses a critical problem in microfinance: distinguishing between temporary cash-flow stress and genuine structural decline in a borrower's finances, then proposing concrete alternative repayment structures backed by evidence.

**Key Innovation:** Every recommendation is traced back to specific numbers and reasoning. The system doesn't just provide a risk score—it explains *which months*, *which numbers*, and *why* a borrower is experiencing stress.

### Who This Is For

- **Lenders:** Make data-driven decisions about loan restructuring
- **Borrowers:** Understand why their loan terms are being adjusted and see alternatives
- **Portfolio Managers:** View a complete portfolio analysis with risk classifications and recommendations

---

## Problem Statement

In microfinance, borrowers often experience irregular income and expense patterns due to:
- **Seasonal income** (agriculture, retail, tourism)
- **Gig work** (inconsistent job availability)
- **Temporary shocks** (medical emergencies, equipment failure)
- **Structural decline** (market downturn, loss of primary income)

Traditional fixed-installment loans don't account for these variations, leading to:
- **Default risk** when income dips
- **Borrower distress** from rigid repayment schedules
- **Lender losses** from poor restructuring decisions

**This system solves this by:**
1. Analyzing 24 months of cash-flow history
2. Identifying patterns (seasonality, trends, stress periods)
3. Classifying the borrower's financial condition
4. Proposing adaptive repayment schedules
5. Providing transparent reasoning for every decision

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    DATA GENERATION LAYER                     │
│              (data_generator.py)                             │
│  Creates 24 months of synthetic income/expense data for      │
│  6 distinct borrower archetypes                              │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                   CASH-FLOW ANALYSIS LAYER                   │
│            (cashflow_engine.py)                              │
│  • Calculates net cash flow                                  │
│  • Detects seasonality patterns                              │
│  • Identifies stress periods                                 │
│  • Classifies borrower condition                             │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                     RISK ASSESSMENT LAYER                    │
│              (risk_engine.py, health_engine.py)              │
│  • Calculates affordability score                            │
│  • Calculates risk score                                     │
│  • Generates evidence chain (explainability)                 │
│  • Provides plain-language reasoning                         │
└────────────────────────┬────────────────────────────────────┘
                         │
                    ┌────┴─────────────────┐
                    │                      │
                    ▼                      ▼
        ┌──────────────────────┐   ┌──────────────────────┐
        │  FORECASTING LAYER   │   │  SCENARIO COMPARISON │
        │ (forecast_engine.py) │   │ (scenario_engine.py) │
        │                      │   │                      │
        │ • Trend projection   │   │ 5 strategy scoring:  │
        │ • Seasonality adj.   │   │ • Fixed              │
        │ • Uncertainty bands  │   │ • Seasonal Step      │
        │ • 24-month forward   │   │ • Income-Linked      │
        │   cash flow forecast │   │ • Temp Relief        │
        │                      │   │ • Grace/Moratorium   │
        └──────────────┬───────┘   └──────────┬───────────┘
                       │                      │
                    ┌──┴──────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────┐
│                  REPAYMENT STRATEGY LAYER                    │
│            (repayment_engine.py)                             │
│  Proposes adaptive repayment schedules based on condition:   │
│  • Stable → Keep existing plan                              │
│  • Improving → Optional accelerated track                   │
│  • Seasonal → Step schedule aligned to income peaks          │
│  • Temporary Stress → Moratorium + re-amortization           │
│  • Chronic Strain → Lightened/extended plan                 │
│  • Structural Decline → Full restructuring (manual review)   │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                  REPORT GENERATION LAYER                     │
│            (generate_report.py)                              │
│  Runs the complete pipeline and outputs analysis results     │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                   VISUALIZATION LAYER                        │
│           (dashboard/index.html, app.js, data.js)            │
│  Interactive single-page dashboard showing:                  │
│  • Borrower portfolio overview                               │
│  • Cash-flow charts and trends                               │
│  • Evidence trails for classifications                       │
│  • Side-by-side repayment comparisons                        │
│  • Strategy comparison matrices                              │
└─────────────────────────────────────────────────────────────┘
```

---

## Project Structure

```
HACKATHON/
│
├── README.md                          # This file - comprehensive project documentation
│
├── data_generator.py                  # Synthetic data generation module
│                                      # Creates realistic 24-month financial histories
│
├── cashflow_engine.py                 # Core cash-flow analysis
│                                      # Calculates metrics, detects patterns, classifies conditions
│
├── risk_engine.py                     # Risk assessment and scoring
│                                      # Generates affordability scores and evidence chains
│
├── health_engine.py                   # Financial health metrics
│                                      # Computes financial health indicators
│
├── forecast_engine.py                 # Forward cash-flow forecasting
│                                      # Projects future cash flow with trend, seasonality, uncertainty
│
├── scenario_engine.py                 # Repayment strategy comparison
│                                      # Evaluates and scores 5 different repayment strategies
│
├── repayment_engine.py                # Adaptive repayment scheduler
│                                      # Proposes alternative repayment structures
│
├── evaluate.py                        # Evaluation and testing utilities
│                                      # Used for validating system outputs
│
├── generate_report.py                 # Pipeline orchestrator
│                                      # Runs the complete analysis and generates dashboard data
│
└── dashboard/
    ├── index.html                     # Main dashboard UI
    │                                  # Static HTML with embedded CSS
    │
    ├── app.js                         # Dashboard JavaScript logic
    │                                  # Handles interactivity, chart rendering, data manipulation
    │
    ├── data.js                        # Generated analysis output
    │                                  # Contains borrower data, classifications, recommendations
    │                                  # Generated by generate_report.py
    │
    └── style.css                      # Dashboard styling (if present)
                                       # CSS for the dashboard UI
```

---

## Technical Components

### 1. **data_generator.py** — Synthetic Data Generation

**Purpose:** Creates realistic 24-month financial histories for 6 distinct borrower archetypes.

**What It Does:**
- Generates monthly income and expense data
- Simulates real-world financial patterns
- Creates 6 different borrower profiles:
  1. **Stable Salaried** — Consistent monthly income (e.g., salary)
  2. **Seasonal/Harvest-Linked** — Income peaks at specific times (e.g., agricultural cycles)
  3. **Gig/Irregular** — Highly variable income (e.g., freelancer, day laborer)
  4. **Temporary Shock** — Normal pattern interrupted by temporary crisis, then recovery
  5. **Structural Decline** — Gradual or sudden decline in earning capacity
  6. **Growing Small Business** — Increasing income trend over time

**Key Features:**
- No real financial data required (entirely synthetic)
- Easily swappable for real data sources
- Includes fixed loan installment obligations
- Realistic seasonality and noise patterns

**Output Format:**
- Dictionary with borrower IDs as keys
- Each borrower has 24 months of income/expense history
- Includes loan principal, rate, and existing installment amount

---

### 2. **cashflow_engine.py** — Cash-Flow Analysis & Classification

**Purpose:** Analyzes borrower cash flow and classifies their financial condition.

**Core Metrics Calculated:**

1. **Net Cash Flow** — Income minus expenses for each month
2. **3-Month Rolling Average** — Smooths monthly volatility to reveal underlying trends
3. **Seasonality Index** — Year-over-year correlation to detect seasonal patterns (not just variance)
4. **Trend Comparison** — Compares recent 6 months vs. prior 6 months
5. **Stress Clusters** — Identifies contiguous months where loan installment would deplete safety buffer

**Safety Buffer:**
- Default: 10% of average monthly income
- Purpose: Ensure borrower maintains financial cushion for emergencies

**Classification System:**

The system assigns each borrower one of 6 conditions:

| Condition | Characteristics | Risk Level |
|-----------|-----------------|-----------|
| **Stable** | Consistent cash flow, no stress clusters | Low |
| **Improving** | Upward trend, no current stress | Low |
| **Seasonal Pattern** | Cyclical income, predictable stress periods | Medium |
| **Temporary Stress** | Short stress clusters (≤3 months), recovery evident | Medium |
| **Chronic Strain** | Ongoing stress clusters, safety buffer frequently compromised | High |
| **Structural Decline** | Declining trend, multiple/extended stress clusters | Critical |

**Evidence-Based Reasoning:**
- Every classification decision is backed by specific computed numbers
- Examples:
  - "Stress in months 4-6 when installment exceeds available cash by $X"
  - "6-month trend shows Y% decline in income"
  - "Seasonality index of Z shows strong harvest-based pattern"

---

### 3. **risk_engine.py** — Risk Assessment & Explainability

**Purpose:** Quantifies risk and generates transparent reasoning for every decision.

**Outputs:**

1. **Affordability Score** (0-100)
   - Higher = better ability to afford loan
   - Based on cash flow, stability, and buffer availability
   
2. **Risk Score** (0-100)
   - Higher = greater default risk
   - Inverse relationship with affordability score
   
3. **Evidence Chain** (Plain-Language Reasoning)
   - List of 3-5 key statements
   - Each statement cites specific numbers
   - Explains *why* this borrower has this risk level
   
**Example Evidence Chain:**
```
"Stress detected in months 4-6 when loan payment ($500) exceeds 
 available cash by average of $150."

"Recent 6-month average income ($2,100) is 15% below prior 6-month 
 average ($2,470), indicating potential structural decline."

"Seasonality index of 0.78 suggests strong seasonal income pattern, 
 with predictable dips in quarters 2 and 3."

"Safety buffer maintained in 18 of 24 months, but at-risk in 6 months, 
 primarily concentrated in Q2."
```

This explainability layer is critical for:
- **Lender trust** — Understanding system reasoning
- **Borrower communication** — Explaining decisions clearly
- **Regulatory compliance** — Auditable decision trails
- **Model improvement** — Identifying when reasoning goes wrong

---

### 4. **health_engine.py** — Financial Health Metrics

**Purpose:** Computes comprehensive financial health indicators.

**Metrics Include:**
- Income stability score
- Expense volatility index
- Debt-to-income ratio
- Cash-flow sustainability index
- Buffer adequacy rating

These metrics feed into the risk engine and provide additional context for decision-making.

---

### 5. **forecast_engine.py** — Forward Cash-Flow Forecasting

**Purpose:** Projects borrower cash flow for the next N months using transparent statistical methods.

**Key Features:**

1. **Trend Component** — Recency-weighted average of recent months
   - Weights increase linearly toward the most recent month
   - Recent significant shifts carry more influence than historical patterns
   - Default window: 6 months
   
2. **Seasonal Component** — Calendar month-based deviations
   - Calculates average deviation for each calendar month (Jan, Feb, etc.)
   - Uses every historical occurrence of that month
   - Applied only if borrower shows seasonal pattern
   - Example: If July averages $500 above borrower's mean, all July projections include this adjustment
   
3. **Uncertainty Band** — Confidence intervals based on historical volatility
   - Derived from population standard deviation of historical data
   - Widens with $\sqrt{\text{horizon}}$ — further months are genuinely less certain
   - Confidence interval: ~80% (Z-score = 1.28)
   - Provides realistic bounds for forecasting accuracy

**Philosophy:**
- No machine learning or external forecasting libraries
- Every number traces back to a statistic from the borrower's own history
- Fully explainable — shows reasoning for every projection
- Suitable for borrowers with 12+ months of data

**Example Forecast Output:**
```
Borrower: Seasonal Farmer
Historical mean income: $2,000/month
Current trend: $2,150/month (recent 6-month weighted avg)
June projection (peak harvest month):
  - Base trend: $2,150
  - Seasonal adjustment: +$800 (June typically strong)
  - Projected: $2,950
  - 80% confidence interval: $2,600 - $3,300

July projection (post-harvest low):
  - Base trend: $2,150
  - Seasonal adjustment: -$600 (July typically low)
  - Projected: $1,550
  - 80% confidence interval: $1,200 - $1,900
```

**Use Cases:**
- Stress-testing recommended repayment schedules
- Forward-looking affordability assessment
- Detecting emerging income trends before they become critical
- Validating seasonal patterns identified by cashflow_engine

---

### 6. **scenario_engine.py** — Repayment Strategy Comparison Engine

**Purpose:** Builds and scores multiple repayment strategy alternatives, enabling data-driven strategy selection.

**Five Repayment Strategies Evaluated:**

| Strategy | Description | Best For | Payment Pattern |
|----------|-------------|----------|-----------------|
| **Strategy A: Fixed** | Current flat installment (baseline) | Baseline comparison | Constant $X/month |
| **Strategy B: Seasonal Step** | Higher payments in peak months, lower in lean months (same total as Fixed) | Seasonal borrowers | Variable, aligned to income |
| **Strategy C: Income-Linked** | Payment = 35% of disposable cash, clamped to 50%-160% of original installment | Irregular income | Truly flexible, income-responsive |
| **Strategy D: Temporary Relief** | Reduced payments during historical stress months, deferred amount recovered over remaining term | Temporary shocks | Low in stress periods, normal elsewhere |
| **Strategy E: Grace/Moratorium** | Zero payment during worst historical stress episode, deferred amount re-amortized after | Severe temporary crisis | Pause followed by longer amortization |

**Strategy Scoring Metrics:**

Each strategy is evaluated on three dimensions (weights: 45% sustainability, 35% recovery, 20% stability):

1. **Sustainability Score** (Affordability during execution)
   - Measures: How often does available cash remain positive?
   - Calculation: Percentage of months where (cash flow - payment) > safety buffer
   - Target: ≥80% of months comfortable
   
2. **Recovery Score** (Loan completion probability)
   - Measures: Total repayment completed, with timeline penalty
   - Calculation: (Amount repaid / Total due) × time-adjustment factor
   - Longer terms reduce recovery score (borrower risk extends)
   - Target: High recovery despite timeline extension

3. **Stability Score** (Payment consistency)
   - Measures: Variance in payment amounts
   - Calculation: 1 / (coefficient of variation + 1)
   - Higher = more predictable
   - Fixed and Seasonal are inherently more stable than income-linked

**Optimization Logic:**

1. Scores all 5 strategies against borrower's **actual historical cash flow**
2. Selects top-scoring strategy as primary recommendation
3. **Eligibility constraint:** Grace/Moratorium only eligible if condition ∈ {temporary_stress, structural_decline, chronic_strain}
   - Prevents offering payment holidays to already-stable borrowers
   - Evidence-based: Only recommended when circumstances justify it

**Income-Linked Defaults:**
- Payment percentage: 35% of disposable cash flow
- Minimum payment: 50% of original installment
- Maximum payment: 160% of original installment
- Safety buffer: 10% of average monthly income
- Synchronized with dashboard's live what-if slider to prevent divergence

**Example Scenario Comparison:**
```
Borrower: Temporary Shock (Factory closure, but temporary)
Original installment: $500/month
24-month history: Stable $3,000 income, then $500/month shock for 3 months, recovery

Strategy Results:
┌─────────────────────┬──────────────────┬────────────────────┐
│ Strategy            │ Sustainability   │ Default Risk       │
├─────────────────────┼──────────────────┼────────────────────┤
│ A: Fixed ($500)     │ 75% comfortable  │ 25% default risk   │
│ B: Seasonal         │ N/A (not seasonal│ No applicable      │
│ C: Income-Linked    │ 88% comfortable  │ 12% default risk   │
│ D: Temp Relief      │ 92% comfortable  │ 8% default risk    │
│ E: Grace/Moratorium │ 95% comfortable  │ 5% default risk    │
├─────────────────────┴──────────────────┴────────────────────┤
│ Recommendation: Strategy E (Grace/Moratorium)              │
│ Reasoning: Eligible + highest sustainability              │
└──────────────────────────────────────────────────────────────┘
```

---

### 7. **repayment_engine.py** — Adaptive Repayment Scheduler

**Purpose:** Proposes concrete alternative repayment structures tailored to each borrower's condition.

**Repayment Strategies by Condition:**

| Condition | Proposed Strategy | Details |
|-----------|-------------------|---------|
| **Stable** | Keep Current Plan | Existing loan terms remain unchanged |
| **Improving** | Accelerated Track (Optional) | Borrower can optionally pay down faster to reduce total interest |
| **Seasonal Pattern** | Step Schedule | Payment aligns with income peaks and troughs (lower in low seasons) |
| **Temporary Stress** | Moratorium + Re-amortization | Pause payments during stress months; extend total term to spread payments |
| **Chronic Strain** | Lightened/Extended Plan | Reduce monthly payment through longer loan term or partial forgiveness |
| **Structural Decline** | Full Restructuring | Requires manual lender review; may involve significant term/rate changes |

**Step Schedule Example (Seasonal):**
```
Months 1-3 (Peak Season):   $600/month
Months 4-6 (Low Season):    $350/month
Months 7-9 (Growing):       $500/month
Months 10-12 (Peak Again):  $650/month
(Pattern repeats)
```

**Benefits:**
- Reduces default risk by matching payments to income availability
- Maintains borrower dignity through transparent restructuring
- Preserves lender portfolio performance
- Customized to each borrower's unique pattern

---

### 8. **generate_report.py** — Pipeline Orchestrator

**Purpose:** Runs the complete analysis pipeline for all borrowers and generates output.

**Workflow:**
1. Generates synthetic borrower data (via `data_generator.py`)
2. Analyzes cash flow for each borrower (via `cashflow_engine.py`)
3. Assesses risk and generates evidence (via `risk_engine.py`, `health_engine.py`)
4. Proposes alternative repayment schedules (via `repayment_engine.py`)
5. Aggregates results and writes to `dashboard/data.js`

**Key Feature:** 
- Produces `dashboard/data.js` which the dashboard reads to display results
- Re-run this whenever you want fresh analysis

---

### 9. **Dashboard System** — Interactive Visualization

**Components:**

- **index.html** — Main UI structure
  - Portfolio overview
  - Borrower list
  - Chart containers
  - Evidence display sections
  
- **app.js** — Logic & Interactivity
  - Loads data from `data.js`
  - Renders interactive charts (Chart.js library)
  - Handles borrower selection and filtering
  - Displays evidence trails
  - Shows original vs. recommended repayment schedules
  
- **data.js** — Generated Analysis Output
  - Contains all borrower data
  - Classification results
  - Risk scores and evidence
  - Recommended repayment schedules
  - Automatically generated by `generate_report.py`

**Features:**
- No server required (fully static)
- Interactive charts and visualizations
- Responsive design
- Works in any modern browser
- Uses Chart.js for charts and Google Fonts for typography

---

## How to Run the Project

### Prerequisites

- **Python 3.6+** installed on your system
- **Modern web browser** (Chrome, Firefox, Safari, Edge)
- **Internet connection** (only needed to load Chart.js and Google Fonts CDN)

### Quick Start (3 Steps)

#### Step 1: Regenerate Data (Optional)
If you want to create fresh synthetic data:

```bash
python3 generate_report.py
```

This will:
- Generate new synthetic borrower data
- Run complete analysis pipeline
- Update `dashboard/data.js` with results
- **Requires only Python standard library — no pip install needed**
- Takes ~2-3 seconds

**Skip this step if** you want to use the pre-generated data already included.

#### Step 2: Open Dashboard
Navigate to the dashboard folder and open the HTML file:

**Option A: Double-click (Easiest)**
```
1. Open file explorer
2. Navigate to: HACKATHON/dashboard/
3. Double-click on: index.html
4. Dashboard opens in your default browser
```

**Option B: Command line**
```bash
# From the HACKATHON directory
python3 -m http.server 8000

# Then visit in browser:
# http://localhost:8000/dashboard/index.html
```

#### Step 3: Explore Results
- See portfolio of 6 borrowers
- Click on each borrower to view detailed analysis
- See cash-flow charts, risk scores, and evidence
- Compare original vs. recommended repayment schedules

---

## Detailed Setup Instructions

### Windows Setup

**1. Install Python (if not already installed)**
- Download from: https://www.python.org/downloads/
- Run installer and **check "Add Python to PATH"**
- Verify installation:
  ```cmd
  python --version
  ```

**2. Navigate to Project**
```cmd
# Open Command Prompt and navigate to project folder
cd C:\path\to\HACKATHON
```

**3. Regenerate Data**
```cmd
python generate_report.py
```

**4. View Dashboard**
```cmd
# Option A: Double-click dashboard/index.html in File Explorer

# Option B: Use Python server
python -m http.server 8000
# Then open: http://localhost:8000/dashboard/index.html
```

### macOS Setup

**1. Verify Python Installation**
```bash
python3 --version
```

**2. Navigate to Project**
```bash
cd /path/to/HACKATHON
```

**3. Regenerate Data**
```bash
python3 generate_report.py
```

**4. View Dashboard**
```bash
# Option A: Double-click dashboard/index.html in Finder

# Option B: Use Python server
python3 -m http.server 8000
# Then open: http://localhost:8000/dashboard/index.html
```

### Linux Setup

**1. Verify Python Installation**
```bash
python3 --version
```

**2. Navigate to Project**
```bash
cd /path/to/HACKATHON
```

**3. Regenerate Data**
```bash
python3 generate_report.py
```

**4. View Dashboard**
```bash
# Option A: Open with default browser
xdg-open dashboard/index.html

# Option B: Use Python server
python3 -m http.server 8000
# Then open: http://localhost:8000/dashboard/index.html
```

---

## Project Workflow

### Complete Analysis Flow

```
User Input (Borrower Financial History)
         │
         ▼
┌─────────────────────────────────────┐
│   STEP 1: ANALYZE CASH FLOW        │
├─────────────────────────────────────┤
│ • Calculate net monthly cash flow   │
│ • Detect seasonality patterns       │
│ • Identify stress periods           │
│ • Classify borrower condition       │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│   STEP 2: ASSESS RISK               │
├─────────────────────────────────────┤
│ • Calculate affordability score     │
│ • Calculate risk score              │
│ • Generate evidence chain           │
│ • Create plain-language reasoning   │
└──────────────┬──────────────────────┘
               │
        ┌──────┴──────────┐
        │                 │
        ▼                 ▼
  ┌──────────────┐  ┌──────────────┐
  │ STEP 3A:     │  │ STEP 3B:     │
  │ FORECAST     │  │ COMPARE      │
  │ CASH-FLOW    │  │ STRATEGIES   │
  ├──────────────┤  ├──────────────┤
  │ • Trend      │  │ • Score 5    │
  │   projection │  │   strategies │
  │ • Seasonal   │  │ • Rank by    │
  │   adjustment │  │   quality    │
  │ • 24-month   │  │ • Select     │
  │   forecast   │  │   optimal    │
  │ • Uncertainty│  │ • Compare    │
  │   bounds     │  │   outcomes   │
  └──────┬───────┘  └───────┬──────┘
         │                  │
         └──────┬───────────┘
                │
                ▼
┌─────────────────────────────────────┐
│   STEP 4: RECOMMEND RESTRUCTURING   │
├─────────────────────────────────────┤
│ • Propose adaptive repayment plan   │
│ • Calculate alternative schedules   │
│ • Compare with original terms       │
│ • Estimate impact on default risk   │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│   STEP 5: GENERATE DASHBOARD DATA   │
├─────────────────────────────────────┤
│ • Aggregate all results             │
│ • Format for visualization          │
│ • Include forecast data             │
│ • Include scenario comparisons      │
│ • Write to dashboard/data.js        │
│ • Prepare evidence summaries        │
└──────────────┬──────────────────────┘
               │
               ▼
        Dashboard Ready
        (View in Browser)
```

### How Dashboard Loads Data

1. User opens `dashboard/index.html` in browser
2. Browser loads HTML structure
3. `app.js` executes and reads `data.js`
4. Charts are rendered using Chart.js library:
   - Historical cash-flow data from cashflow_engine
   - Forward forecasts from forecast_engine
   - Strategy comparison data from scenario_engine
   - Risk and evidence data from risk_engine
5. Interactive features become available
6. User can click to filter and explore results
7. User can compare repayment strategies and forecasts side-by-side

---

## Understanding the Output

### Dashboard Display

**Portfolio Overview Section:**
- Table showing all 6 borrowers
- Key metrics: Name, Condition, Risk Score, Affordability Score
- Color-coded risk levels:
  - 🟢 Green (Low Risk): Stable, Improving
  - 🟡 Yellow (Medium Risk): Seasonal, Temporary Stress
  - 🔴 Red (High Risk): Chronic Strain, Structural Decline

**Borrower Detail View:**

When you click on a borrower, you see:

1. **Cash-Flow Chart**
   - Month-by-month income and expenses
   - Loan installment line
   - Safety buffer visualization
   - Shaded stress periods
   - Historical data (24 months)

2. **Cash-Flow Forecast Chart** (if enabled)
   - Forward-looking 6-12 month projection
   - Trend line showing expected direction
   - Uncertainty bands (80% confidence interval)
   - Seasonal adjustments applied
   - Helps assess future affordability

3. **Evidence Trail**
   - Plain-language reasoning
   - Specific metrics and numbers
   - Justification for classification
   - Risk assessment summary

4. **Repayment Comparison Chart**
   - Original payment schedule (current terms)
   - Recommended payment schedule (adapted to condition)
   - Total interest paid comparison
   - Impact on default risk
   - Timeline comparison

5. **Strategy Comparison Matrix** (Scenario Analysis)
   - All 5 repayment strategies evaluated:
     - Strategy A: Fixed (current)
     - Strategy B: Seasonal Step
     - Strategy C: Income-Linked
     - Strategy D: Temporary Relief
     - Strategy E: Grace/Moratorium
   - Metrics for each strategy:
     - Sustainability score (affordability)
     - Recovery score (completion probability)
     - Stability score (payment consistency)
     - Overall ranking
   - Highlighted: Recommended strategy

6. **Metrics Panel**
   - Affordability Score (0-100)
   - Risk Score (0-100)
   - Condition Classification
   - Seasonality Index
   - Trend Direction
   - Forecast confidence level

### Interpreting Scores

**Affordability Score:**
- **80-100**: Excellent — Can comfortably afford current loan
- **60-79**: Good — Can afford with minimal stress
- **40-59**: Concerning — Frequent cash-flow stress
- **20-39**: Critical — Regular safety buffer violations
- **0-19**: Severe — Cannot reliably afford installments

**Risk Score:**
- **0-20**: Very Low Risk — Excellent repayment prospects
- **21-40**: Low Risk — Good repayment prospects
- **41-60**: Medium Risk — Uncertain repayment prospects
- **61-80**: High Risk — Significant default risk
- **81-100**: Very High Risk — Severe default risk

---

## Key Features & Innovations

### 1. **Explainable AI - The Evidence Chain**
Unlike black-box scoring systems, this project explains *why* each recommendation is made:
- Specific months are cited
- Actual dollar amounts are shown
- Pattern reasoning is transparent
- Borrowers and lenders can understand and trust decisions

### 2. **Seasonality vs. Structural Decline Detection**
Distinguishes between:
- Predictable seasonal dips (addressable through payment timing)
- Genuine income decline (requires deeper restructuring)

Uses year-over-year correlation rather than simple variance to avoid confusing random noise with patterns.

### 3. **Stress Cluster Identification**
Identifies contiguous periods where borrowers can't afford installments while maintaining safety buffer. Enables:
- Targeted moratorium periods (not blanket payment holidays)
- Precise payment restructuring
- Better default prediction

### 4. **6 Archetype Borrower Profiles**
Covers most common microfinance borrower patterns:
- Employed (stable income)
- Agricultural (seasonal)
- Gig workers (irregular)
- Shock-hit borrowers (recoverable temporary crisis)
- Declining businesses (structural problems)
- Growth-stage businesses (improving prospects)

### 5. **Adaptive Repayment Engine**
Not one-size-fits-all. Each borrower gets:
- Condition-specific restructuring strategy
- Aligned with their actual cash-flow pattern
- Maintains loan viability for lender
- Improves repayment probability for borrower

### 6. **No Dependencies - Runs Everywhere**
- Python standard library only (no pip install)
- Dashboard needs no server or build process
- Works offline after initial load
- CDN optional (can run without internet)

---

## Limitations

It's important to understand what this prototype *can and cannot do*:

### 1. **Synthetic Data Only**
- **What:** All data is artificially generated, not from real microfinance transactions
- **Impact:** Patterns are realistic but not validated against actual repayment outcomes
- **Solution:** Validate against real data before production deployment

### 2. **Heuristic Thresholds**
The system uses hand-tuned parameters:
- 10% safety buffer threshold
- 6-month trend window
- Seasonality detection cutoffs
- Stress cluster duration minimums

**What This Means:**
- Good starting points, not mathematically optimized
- May need tuning for different geographic regions/borrower types
- Real deployment should calibrate against historical outcomes

**Example:** "Did borrowers we classified as 'temporary_stress' actually recover and repay?"

### 3. **Six Archetypes, Not Universal**
- **Design:** Built to distinguish 6 specific patterns
- **Limitation:** Real borrowers may show blended or noisier patterns
- **Impact:** Classifier accuracy may drop on data outside these archetypes

### 4. **Borrower-Side Only**
- **Design:** Only considers borrower affordability
- **Missing:** Lender's liquidity, portfolio concentration, regulatory limits
- **Real World:** Lenders balance borrower affordability with lender risk constraints

### 5. **No Machine Learning**
- Classification and scoring use statistical heuristics, not learned models
- **Advantage:** Explainable, no black-box decisions
- **Disadvantage:** May miss complex patterns that ML could capture

### 6. **24-Month Window Only**
- **Design:** Uses 24 months of history for analysis
- **Issue:** Longer-term cycles (3-5 year business patterns) won't be captured
- **Limitation:** Very new borrowers (<12 months history) may be misclassified

---

## Troubleshooting

### Problem: "Python command not found"

**Windows:**
- Python not added to PATH during installation
- **Solution:** Reinstall Python and check "Add Python to PATH"

**macOS/Linux:**
```bash
# Check if python3 is available
which python3

# If not, install Python:
# macOS: brew install python3
# Ubuntu: sudo apt-get install python3
```

### Problem: Dashboard shows empty page

**Possible Causes:**
1. `data.js` not generated yet
2. Chart.js CDN unavailable (no internet connection)
3. Browser JavaScript errors

**Solutions:**
```bash
# Regenerate data.js
python3 generate_report.py

# Check console for errors
# In browser: Press F12 to open Developer Tools > Console tab
```

### Problem: "ModuleNotFoundError" when running Python scripts

**Cause:** Missing Python modules
**Solution:** All modules are from standard library—should not occur
```bash
# Verify Python installation
python3 --version

# Try running with full path
/usr/bin/python3 generate_report.py
```

### Problem: Charts not rendering in dashboard

**Cause:** Chart.js library not loading (usually CDN issue)
**Solution:**
1. Ensure internet connection
2. Check browser console for errors (F12)
3. Try offline chart alternatives (basic HTML tables)

### Problem: Dashboard is very slow

**Cause:** Browser rendering large datasets
**Solutions:**
- Close other browser tabs/applications
- Use modern browser (Chrome/Firefox recommended)
- Reduce animation settings if available

---

## Technology Stack

### Backend Analysis

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Data Generation | Python 3 | Synthetic borrower data creation |
| Cash-Flow Analysis | Python 3 | Statistical analysis and pattern detection |
| Risk Assessment | Python 3 | Scoring and evidence generation |
| Orchestration | Python 3 | Pipeline coordination |

### Frontend Visualization

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Layout | HTML5 | Page structure |
| Styling | CSS3 | Visual design |
| Interactivity | JavaScript (Vanilla) | User interactions, data manipulation |
| Charts | Chart.js 3.x | Data visualization |
| Fonts | Google Fonts | Typography |

### Dependencies

- **Python:** Python 3.6+ (standard library only)
- **Frontend:** Chart.js (loaded from CDN), Google Fonts (loaded from CDN)
- **Browser:** Any modern browser (Chrome, Firefox, Safari, Edge)

### No External Packages Required
- No pip install needed
- No npm install needed
- No database required
- No server required (optional)

---

## Future Enhancements

### Short Term (Next Sprint)

1. **Real Data Integration**
   - Swap `data_generator.py` for actual microfinance transaction data
   - Validate classifier accuracy against real outcomes
   
2. **Threshold Calibration**
   - Analyze historical data to optimize safety buffer, window sizes, cutoffs
   - A/B test different threshold configurations
   
3. **Lender Constraints**
   - Add portfolio-level risk limits
   - Include regulatory requirements (reserve ratios, etc.)
   - Balance borrower affordability with lender viability

4. **Enhanced Dashboard**
   - Real-time data updates
   - Export reports (PDF, Excel)
   - Portfolio analytics (default rates, recovery metrics)

### Medium Term

1. **Machine Learning Classifier**
   - Train on historical repayment outcomes
   - Improve accuracy on edge cases
   - Add confidence scores to predictions

2. **Borrower Communication Portal**
   - Borrowers can view their analysis
   - Propose counter-restructuring options
   - Track actual repayment vs. predictions

3. **Dynamic Repayment Adjustment**
   - Automated payment plan updates as data arrives
   - Re-analysis triggered on significant cash-flow changes
   - Real-time stress alerts

### Long Term

1. **Multi-Loan Portfolio Optimization**
   - Consider multiple outstanding loans per borrower
   - Cross-loan restructuring recommendations
   
2. **Predictive Alerts**
   - Flag borrowers at risk before stress occurs
   - Recommend preemptive restructuring
   
3. **Mobile Applications**
   - Borrower app for payment tracking and plans
   - Lender app for portfolio management
   
4. **Integration with MFI Systems**
   - Connect to core banking software
   - Real-time data feeds
   - Automated restructuring execution

---

## Getting Help

### Questions About the Project?

1. **How do I interpret the risk score?** → See "Understanding the Output" section
2. **Why is a borrower classified as 'structural decline'?** → Check the "Evidence Trail" in the dashboard
3. **What repayment plan does the system recommend?** → See "Repayment Engine" section
4. **How do I change thresholds or parameters?** → Edit the constants in `cashflow_engine.py` and `risk_engine.py`

### Suggested Framing for Demonstrations

Lead with the **evidence trail** — it's the core differentiator:
- Anyone can compute a risk score
- **Showing your work** (which months, which numbers, why this is a dip and not a decline) builds trust
- Borrowers and lenders both need to understand *why* recommendations are made
- Explainability drives adoption and reduces legal/regulatory risk

---

## Summary

This project demonstrates a **practical, explainable approach** to adaptive loan restructuring. By combining statistical cash-flow analysis, transparent risk assessment, and condition-specific repayment strategies, it addresses a real microfinance pain point while remaining understandable to all stakeholders.

**Get started now:**
1. `python3 generate_report.py` (regenerate data)
2. Open `dashboard/index.html` in your browser
3. Explore the borrower analysis and recommendations

Enjoy exploring the system!
