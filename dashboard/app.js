// app.js - all dashboard logic. Reads REPORT_DATA from data.js (generated
// by generate_report.py). Nothing in here is hardcoded per-borrower;
// every number rendered comes from REPORT_DATA or a live client-side
// recalculation over that borrower's own historical arrays.

const CONDITION_META = {
  stable:             { label: "Stable",             color: "#2E6B4F" },
  improving:          { label: "Improving",          color: "#2E6B4F" },
  recovering:         { label: "Recovering",         color: "#4C8C6B" },
  seasonal_pattern:   { label: "Seasonal Pattern",   color: "#B08226" },
  temporary_stress:   { label: "Temporary Stress",   color: "#B08226" },
  chronic_strain:     { label: "Chronic Strain",     color: "#9C4A3C" },
  structural_decline: { label: "Structural Decline", color: "#9C4A3C" },
};
const MONTH_NAMES = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];

let state = {
  topTab: "portfolio",
  currentId: null,
  detailTab: "overview",
  view: "lender",
  portfolioFilter: "all",
  portfolioSort: { key: "risk_score", dir: "desc" },
};

let charts = {}; // named chart instances, destroyed/recreated on redraw

function fmt(n) {
  return Math.round(n).toLocaleString('en-IN');
}
function pct(n) { return `${Number(n).toFixed(1)}%`; }
function meta(condition) {
  return CONDITION_META[condition] || { label: condition, color: '#445059' };
}
function destroyChart(key) {
  if (charts[key]) { charts[key].destroy(); charts[key] = null; }
}

// ============================================================
// TOP-LEVEL TABS
// ============================================================
function initTabs() {
  document.querySelectorAll('.tabbar .tab').forEach(btn => {
    btn.addEventListener('click', () => {
      state.topTab = btn.dataset.tab;
      document.querySelectorAll('.tabbar .tab').forEach(b => b.classList.toggle('active', b === btn));
      document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
      document.getElementById(`page-${state.topTab}`).classList.add('active');
      if (state.topTab === 'portfolio') renderPortfolioPage();
      if (state.topTab === 'methodology') renderMethodologyPage();
    });
  });
}

function renderTopStrip() {
  const s = REPORT_DATA.portfolio_summary;
  const chips = Object.entries(s.condition_counts).map(([cond, count]) => {
    const m = meta(cond);
    return `<span class="chip"><span class="dot" style="background:${m.color}"></span>${m.label} · ${count}</span>`;
  }).join('');

  document.getElementById('portfolioStats').innerHTML = `
    <div class="stat"><div class="num figure">${s.total_borrowers}</div><div class="label">BORROWERS</div></div>
    <div class="stat"><div class="num figure">${s.avg_financial_health}</div><div class="label">AVG HEALTH</div></div>
    <div class="stat"><div class="num figure">${s.avg_repayment_stress}</div><div class="label">AVG STRESS INDEX</div></div>
    <div style="display:flex;gap:6px;flex-wrap:wrap;max-width:340px;">${chips}</div>
  `;
}

// ============================================================
// PORTFOLIO PAGE
// ============================================================
function renderPortfolioPage() {
  const s = REPORT_DATA.portfolio_summary;
  const borrowers = REPORT_DATA.borrowers;

  document.getElementById('portfolioPage').innerHTML = `
    <h2 style="font-size:1.3rem;margin-bottom:16px;">Portfolio overview</h2>
    <div class="kpi-grid">
      <div class="kpi-card"><div class="num figure">${s.total_borrowers}</div><div class="label">TOTAL BORROWERS</div></div>
      <div class="kpi-card"><div class="num figure">Rs.${fmt(s.total_outstanding)}</div><div class="label">TOTAL OUTSTANDING PRINCIPAL</div></div>
      <div class="kpi-card"><div class="num figure">${s.avg_financial_health}</div><div class="label">AVG FINANCIAL HEALTH</div></div>
      <div class="kpi-card"><div class="num figure">${s.avg_repayment_stress}</div><div class="label">AVG REPAYMENT STRESS INDEX</div></div>
      <div class="kpi-card"><div class="num figure">${s.borrowers_needing_intervention}</div><div class="label">NEED INTERVENTION</div></div>
      <div class="kpi-card"><div class="num figure">${s.borrowers_with_seasonal_mismatch}</div><div class="label">SEASONAL MISMATCH</div></div>
      <div class="kpi-card"><div class="num figure">${s.borrowers_high_risk}</div><div class="label">HIGH RISK (≥60)</div></div>
      <div class="kpi-card"><div class="num figure">${s.estimated_recovery_pct}%</div><div class="label">EST. RECOVERY (RECOMMENDED PLANS)</div></div>
    </div>

    <div style="display:flex;gap:20px;flex-wrap:wrap;margin-bottom:24px;">
      <div class="panel" style="flex:1;min-width:280px;">
        <h3>Condition distribution</h3>
        <div class="chart-wrap short"><canvas id="conditionChart"></canvas></div>
      </div>
      <div class="panel" style="flex:1;min-width:280px;">
        <h3>Risk score distribution</h3>
        <div class="chart-wrap short"><canvas id="riskDistChart"></canvas></div>
      </div>
    </div>

    <h2 style="font-size:1.05rem;margin-bottom:10px;">Borrowers</h2>
    <div class="filter-row" id="filterRow"></div>
    <div class="panel" style="overflow-x:auto;">
      <table class="datatable" id="portfolioTable"></table>
    </div>
  `;

  drawConditionChart(borrowers);
  drawRiskDistChart(borrowers);
  renderFilterChips();
  renderPortfolioTable();
}

function renderFilterChips() {
  const filters = [
    { key: 'all', label: 'All' },
    { key: 'high_risk', label: 'High risk' },
    { key: 'high_stress', label: 'High stress' },
    { key: 'seasonal_pattern', label: 'Seasonal' },
    { key: 'temporary_stress', label: 'Temporary stress' },
    { key: 'chronic_strain', label: 'Chronic strain' },
    { key: 'structural_decline', label: 'Structural decline' },
    { key: 'stable', label: 'Stable / improving' },
  ];
  const row = document.getElementById('filterRow');
  row.innerHTML = filters.map(f =>
    `<button class="filter-chip ${state.portfolioFilter === f.key ? 'active' : ''}" data-key="${f.key}">${f.label}</button>`
  ).join('');
  row.querySelectorAll('.filter-chip').forEach(btn => {
    btn.addEventListener('click', () => {
      state.portfolioFilter = btn.dataset.key;
      renderFilterChips();
      renderPortfolioTable();
    });
  });
}

function filteredBorrowers() {
  const f = state.portfolioFilter;
  return REPORT_DATA.borrowers.filter(b => {
    if (f === 'all') return true;
    if (f === 'high_risk') return b.risk_score >= 60;
    if (f === 'high_stress') return b.repayment_stress_index.band === 'High' || b.repayment_stress_index.band === 'Severe';
    if (f === 'stable') return b.condition === 'stable' || b.condition === 'improving' || b.condition === 'recovering';
    return b.condition === f;
  });
}

function renderPortfolioTable() {
  const cols = [
    { key: 'name', label: 'Borrower' },
    { key: 'financial_health', label: 'Health', get: b => b.financial_health.score },
    { key: 'repayment_stress_index', label: 'Stress', get: b => b.repayment_stress_index.index },
    { key: 'risk_score', label: 'Risk' },
    { key: 'condition', label: 'Condition' },
    { key: 'current_plan', label: 'Current Plan', get: b => b.loan.installment },
    { key: 'recommended_action', label: 'Recommended Action' },
  ];
  let rows = filteredBorrowers();
  const sortKey = state.portfolioSort.key, dir = state.portfolioSort.dir === 'asc' ? 1 : -1;
  rows = [...rows].sort((a, b) => {
    const av = sortKey === 'name' ? a.name : (cols.find(c => c.key === sortKey)?.get?.(a) ?? a[sortKey]);
    const bv = sortKey === 'name' ? b.name : (cols.find(c => c.key === sortKey)?.get?.(b) ?? b[sortKey]);
    if (typeof av === 'string') return av.localeCompare(bv) * dir;
    return (av - bv) * dir;
  });

  const table = document.getElementById('portfolioTable');
  table.innerHTML = `
    <thead><tr>
      ${cols.map(c => `<th data-key="${c.key}" style="cursor:pointer;">${c.label} ${state.portfolioSort.key === c.key ? (dir === 1 ? '▲' : '▼') : ''}</th>`).join('')}
    </tr></thead>
    <tbody>
      ${rows.map(b => {
        const m = meta(b.condition);
        return `<tr class="row-link" data-id="${b.id}" style="cursor:pointer;">
          <td style="text-align:left;"><span class="dot" style="background:${m.color}"></span>${b.name}</td>
          <td>${b.financial_health.score}</td>
          <td>${b.repayment_stress_index.index} (${b.repayment_stress_index.band})</td>
          <td>${b.risk_score}</td>
          <td style="text-align:left;">${m.label}</td>
          <td>Rs.${fmt(b.loan.installment)}/mo</td>
          <td style="text-align:left;">${b.intervention.title}</td>
        </tr>`;
      }).join('')}
    </tbody>
  `;
  table.querySelectorAll('th').forEach(th => {
    th.addEventListener('click', () => {
      const key = th.dataset.key;
      if (state.portfolioSort.key === key) {
        state.portfolioSort.dir = state.portfolioSort.dir === 'asc' ? 'desc' : 'asc';
      } else {
        state.portfolioSort = { key, dir: 'desc' };
      }
      renderPortfolioTable();
    });
  });
  table.querySelectorAll('tbody tr').forEach(tr => {
    tr.addEventListener('click', () => {
      state.topTab = 'borrowers';
      document.querySelectorAll('.tabbar .tab').forEach(b => b.classList.toggle('active', b.dataset.tab === 'borrowers'));
      document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
      document.getElementById('page-borrowers').classList.add('active');
      selectBorrower(tr.dataset.id);
    });
  });
}

function drawConditionChart(borrowers) {
  destroyChart('condition');
  const counts = {};
  borrowers.forEach(b => counts[b.condition] = (counts[b.condition] || 0) + 1);
  const labels = Object.keys(counts).map(c => meta(c).label);
  const colors = Object.keys(counts).map(c => meta(c).color);
  charts.condition = new Chart(document.getElementById('conditionChart').getContext('2d'), {
    type: 'doughnut',
    data: { labels, datasets: [{ data: Object.values(counts), backgroundColor: colors, borderColor: '#F2F0E7', borderWidth: 2 }] },
    options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'right', labels: { boxWidth: 12, font: { size: 11 } } } } },
  });
}

function drawRiskDistChart(borrowers) {
  destroyChart('riskDist');
  const buckets = [0, 0, 0, 0, 0]; // 0-20,20-40,40-60,60-80,80-100
  borrowers.forEach(b => { const i = Math.min(4, Math.floor(b.risk_score / 20)); buckets[i]++; });
  charts.riskDist = new Chart(document.getElementById('riskDistChart').getContext('2d'), {
    type: 'bar',
    data: {
      labels: ['0-20', '20-40', '40-60', '60-80', '80-100'],
      datasets: [{ label: 'Borrowers', data: buckets, backgroundColor: '#B08226', borderRadius: 3 }],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: { y: { beginAtZero: true, ticks: { stepSize: 1, font: { size: 10 } } }, x: { ticks: { font: { size: 10 } } } },
    },
  });
}

// ============================================================
// BORROWER LIST + DETAIL PAGE
// ============================================================
function renderBorrowerList() {
  const list = document.getElementById('borrowerList');
  list.innerHTML = REPORT_DATA.borrowers.map(b => {
    const m = meta(b.condition);
    return `
      <button class="borrower-item" data-id="${b.id}">
        <div class="bname"><span class="dot" style="background:${m.color}"></span>${b.name}</div>
        <div class="barch">${m.label} · Health ${b.financial_health.score}</div>
      </button>`;
  }).join('');
  list.querySelectorAll('.borrower-item').forEach(btn => {
    btn.addEventListener('click', () => selectBorrower(btn.dataset.id));
  });
}

function selectBorrower(id) {
  state.currentId = id;
  state.detailTab = 'overview';
  document.querySelectorAll('.borrower-item').forEach(el => el.classList.toggle('active', el.dataset.id === id));
  renderMain();
}

function currentBorrower() {
  return REPORT_DATA.borrowers.find(x => x.id === state.currentId);
}

function renderMain() {
  const b = currentBorrower();
  if (!b) return;
  const m = meta(b.condition);
  const main = document.getElementById('mainPanel');

  main.innerHTML = `
    <div class="verdict-row">
      <h2 style="font-size:1.35rem;">${b.name}</h2>
      <span class="stamp" style="color:${m.color};">${m.label}</span>
      <span class="chip">Confidence ${b.classification_confidence}%</span>
    </div>
    <div class="borrower-sub">Loan: Rs.${fmt(b.loan.principal)} principal · Rs.${fmt(b.loan.installment)}/month · ${b.loan.tenure_months} month tenure</div>

    <div style="display:flex;justify-content:space-between;align-items:flex-end;flex-wrap:wrap;gap:12px;">
      <div class="score-row">
        <div class="score-card"><div class="num figure">${b.financial_health.score}</div><div class="label">FINANCIAL HEALTH (0-100)</div></div>
        <div class="score-card"><div class="num figure">${b.repayment_stress_index.index}</div><div class="label">STRESS INDEX · ${b.repayment_stress_index.band.toUpperCase()}</div></div>
        <div class="score-card"><div class="num figure">${b.risk_score}</div><div class="label">RISK SCORE (0-100)</div></div>
        <div class="score-card"><div class="num figure">${b.affordability_score}</div><div class="label">AFFORDABILITY (0-100)</div></div>
      </div>
      <div class="view-toggle">
        VIEW:
        <button data-view="lender" class="${state.view === 'lender' ? 'active' : ''}">Lender</button>
        <button data-view="borrower" class="${state.view === 'borrower' ? 'active' : ''}">Borrower</button>
      </div>
    </div>

    <div class="subtabs">
      <button data-subtab="overview" class="${state.detailTab === 'overview' ? 'active' : ''}">Overview</button>
      <button data-subtab="cashflow" class="${state.detailTab === 'cashflow' ? 'active' : ''}">Cash Flow &amp; Forecast</button>
      <button data-subtab="scenarios" class="${state.detailTab === 'scenarios' ? 'active' : ''}">Scenarios &amp; What-If</button>
      <button data-subtab="evidence" class="${state.detailTab === 'evidence' ? 'active' : ''}">Evidence &amp; Warnings</button>
    </div>
    <div id="detailContent"></div>
  `;

  main.querySelectorAll('.view-toggle button').forEach(btn => {
    btn.addEventListener('click', () => { state.view = btn.dataset.view; renderMain(); });
  });
  main.querySelectorAll('.subtabs button').forEach(btn => {
    btn.addEventListener('click', () => { state.detailTab = btn.dataset.subtab; renderDetailContent(); });
  });

  renderDetailContent();
}

function renderDetailContent() {
  const b = currentBorrower();
  const el = document.getElementById('detailContent');
  if (state.detailTab === 'overview') el.innerHTML = overviewHTML(b);
  if (state.detailTab === 'cashflow') el.innerHTML = cashflowHTML(b);
  if (state.detailTab === 'scenarios') el.innerHTML = scenariosHTML(b);
  if (state.detailTab === 'evidence') el.innerHTML = evidenceHTML(b);

  if (state.detailTab === 'cashflow') { drawCashFlowChart(b); drawForecastChart(b); }
  if (state.detailTab === 'scenarios') { drawScheduleChart(b); wireWhatIf(b); }
}

// ============================================================
// OVERVIEW TAB
// ============================================================
function healthBarsHTML(breakdown) {
  const labels = {
    cash_flow_stability: 'Cash-flow stability',
    repayment_coverage: 'Repayment coverage',
    cash_buffer: 'Cash buffer',
    income_trend: 'Income trend',
    expense_pressure: 'Expense pressure',
    recovery_capacity: 'Recovery capacity',
  };
  return Object.entries(breakdown).map(([k, v]) => `
    <div class="health-bar-row">
      <div class="lbl">${labels[k] || k}</div>
      <div class="health-bar-track"><div class="health-bar-fill" style="width:${v}%;"></div></div>
      <div class="v">${v}</div>
    </div>`).join('');
}

function calendarHTML(b) {
  const by_month = b.seasonality.by_month;
  const vals = Object.values(by_month);
  const maxAbs = Math.max(1, ...vals.map(v => Math.abs(v)));
  const cells = MONTH_NAMES.map((name, i) => {
    const v = by_month[i] || 0;
    const ratio = v / maxAbs; // -1..1
    let color;
    if (ratio > 0.33) color = '#2E6B4F';
    else if (ratio > -0.15) color = '#B08226';
    else color = '#9C4A3C';
    return `<div class="cal-cell">
      <div class="mon">${name}</div>
      <div class="cal-dot" style="background:${color};"></div>
      <div class="val figure">${v >= 0 ? '+' : ''}${fmt(v)}</div>
    </div>`;
  }).join('');

  if (!b.seasonality.is_seasonal) {
    return `<div class="panel"><h3>Income seasonality calendar</h3>
      <p style="font-size:0.85rem;color:var(--ink-soft);">No statistically reliable seasonal rhythm was detected for this borrower
      (year-over-year correlation ${b.seasonality.year_over_year_correlation}) - month-to-month variation here looks like noise, not a repeating cycle.</p>
      <div class="cal-grid" style="opacity:0.6;">${cells}</div>
    </div>`;
  }
  const by_month_entries = Object.entries(by_month);
  const peak = by_month_entries.reduce((a, c) => c[1] > a[1] ? c : a);
  const low = by_month_entries.reduce((a, c) => c[1] < a[1] ? c : a);
  return `<div class="panel">
    <h3>Income seasonality calendar</h3>
    <div class="cal-grid">${cells}</div>
    <div style="margin-top:12px;font-size:0.85rem;">
      <span class="badge-inline">Seasonality: YES</span>
      <span class="badge-inline">Confidence ${(b.seasonality.year_over_year_correlation*100).toFixed(0)}%</span>
      <span class="badge-inline">Peak: ${MONTH_NAMES[peak[0]]}</span>
      <span class="badge-inline">Lean: ${MONTH_NAMES[low[0]]}</span>
    </div>
  </div>`;
}

function overviewHTML(b) {
  const rh = b.repayment_history_summary;
  if (state.view === 'borrower') {
    const buffer = b.net_cash_flow[b.net_cash_flow.length - 1] - b.loan.installment;
    return `
      <section><div class="callout">
        <strong>In simple terms:</strong> ${borrowerFriendlySummary(b)}
      </div></section>
      <section>
        <h2>Your income pattern</h2>
        ${calendarHTML(b)}
      </section>
      <section>
        <h2>Your repayment record</h2>
        <div class="panel">
          <div class="kpi-grid" style="margin-bottom:0;">
            <div class="kpi-card"><div class="num figure">${rh.on_time_rate}%</div><div class="label">ON-TIME PAYMENTS</div></div>
            <div class="kpi-card"><div class="num figure">${rh.missed_count}</div><div class="label">MISSED PAYMENTS</div></div>
            <div class="kpi-card"><div class="num figure">${rh.partial_count}</div><div class="label">PARTIAL PAYMENTS</div></div>
          </div>
        </div>
      </section>`;
  }

  return `
    <section>
      <h2>Financial health score</h2>
      <div class="panel">
        <div style="display:flex;align-items:baseline;gap:10px;margin-bottom:14px;">
          <div style="font-family:'Source Serif 4',serif;font-size:2rem;font-weight:600;">${b.financial_health.score}</div>
          <div style="color:var(--ink-soft);font-size:0.82rem;">/ 100 · prototype decision-support score, not a credit score</div>
        </div>
        ${healthBarsHTML(b.financial_health.breakdown)}
      </div>
    </section>

    <section>
      <h2>Repayment stress index</h2>
      <div class="panel">
        <div style="display:flex;align-items:baseline;gap:10px;margin-bottom:10px;">
          <div style="font-family:'Source Serif 4',serif;font-size:2rem;font-weight:600;">${b.repayment_stress_index.index}</div>
          <div class="stamp" style="color:${b.repayment_stress_index.band === 'Very Low' || b.repayment_stress_index.band === 'Low' ? 'var(--good)' : (b.repayment_stress_index.band === 'Moderate' ? 'var(--gold)' : 'var(--risk)')};">${b.repayment_stress_index.band}</div>
        </div>
        <div style="font-size:0.82rem;color:var(--ink-soft);">
          Installment load ${b.repayment_stress_index.components.installment_load} ·
          Frequency ${b.repayment_stress_index.components.stress_frequency} ·
          Severity ${b.repayment_stress_index.components.shortfall_severity} ·
          Duration ${b.repayment_stress_index.components.stress_duration} ·
          Volatility ${b.repayment_stress_index.components.volatility}
        </div>
      </div>
    </section>

    <section>${calendarHTML(b)}</section>

    <section>
      <h2>Recommended intervention</h2>
      <div class="action-box">
        <span class="tag">${b.intervention.title.toUpperCase()}</span>
        ${b.intervention.reason}
      </div>
    </section>

    <section>
      <h2>Repayment history (simulated)</h2>
      <div class="panel">
        <div class="kpi-grid" style="margin-bottom:0;">
          <div class="kpi-card"><div class="num figure">${rh.on_time_rate}%</div><div class="label">ON-TIME RATE</div></div>
          <div class="kpi-card"><div class="num figure">${rh.missed_count}</div><div class="label">MISSED PAYMENTS</div></div>
          <div class="kpi-card"><div class="num figure">${rh.partial_count}</div><div class="label">PARTIAL PAYMENTS</div></div>
          <div class="kpi-card"><div class="num figure">${rh.avg_delay_days}</div><div class="label">AVG DAYS LATE</div></div>
        </div>
      </div>
    </section>
  `;
}

function borrowerFriendlySummary(b) {
  const cond = b.condition;
  const rec = b.comparison_narrative;
  if (cond === 'seasonal_pattern') {
    return `Your income naturally goes up and down through the year. The current fixed payment of Rs.${fmt(b.loan.installment)} can feel heavy in your lower-income months. We'd suggest paying a bit more when income is high and less when it's low - the total you pay stays about the same.`;
  }
  if (cond === 'temporary_stress') {
    return `It looks like you went through a rough patch, but your income has been recovering. We can pause or reduce a few payments and spread the difference over the following months so it's easier to manage.`;
  }
  if (cond === 'chronic_strain') {
    return `Your current payment of Rs.${fmt(b.loan.installment)} looks tight most months. We'd suggest a smaller monthly payment over a slightly longer period so it fits your typical income better.`;
  }
  if (cond === 'structural_decline') {
    return `Your income has been declining for a while. Rather than an automatic change, this needs a conversation with your lender to work out a plan that's realistic for you going forward.`;
  }
  if (cond === 'recovering') {
    return `You went through a difficult period a while back, but things have clearly improved since then. Your current plan should keep working fine - we're just keeping a lighter eye on things for now.`;
  }
  return `Your income comfortably covers your current payment of Rs.${fmt(b.loan.installment)}. No changes are needed right now.`;
}

// ============================================================
// CASH FLOW & FORECAST TAB
// ============================================================
function cashflowHTML(b) {
  const fc = b.forecast;
  return `
    <section>
      <h2>Historical cash flow</h2>
      <div class="panel"><div class="chart-wrap"><canvas id="cfChart"></canvas></div></div>
    </section>
    <section>
      <h2>Forward forecast (next ${fc.months_ahead} months)</h2>
      <div class="panel">
        <div class="chart-wrap"><canvas id="forecastChart"></canvas></div>
        <p style="font-size:0.8rem;color:var(--ink-soft);margin-top:10px;margin-bottom:0;">
          Method: ${fc.method}. The shaded band is a rough 80% plausible range built from this borrower's
          own historical volatility - it widens the further out the forecast goes, because further-out
          months are genuinely less certain, not because of a fixed percentage rule.
        </p>
      </div>
    </section>
  `;
}

function drawCashFlowChart(b) {
  destroyChart('cf');
  const ctx = document.getElementById('cfChart').getContext('2d');
  const labels = b.income.map((_, i) => `M${i + 1}`);
  const stressedSet = new Set(b.stressed_months.map(s => s.month));

  charts.cf = new Chart(ctx, {
    type: 'line',
    data: {
      labels,
      datasets: [
        { label: 'Income', data: b.income, borderColor: '#445059', backgroundColor: 'transparent', borderWidth: 1.5, pointRadius: 0, tension: 0.25 },
        { label: 'Expenses', data: b.expenses, borderColor: '#9C4A3C', backgroundColor: 'transparent', borderWidth: 1.5, borderDash: [3, 3], pointRadius: 0, tension: 0.25 },
        {
          label: 'Net cash flow (3mo avg)', data: b.rolling_average, borderColor: '#2E6B4F',
          backgroundColor: 'rgba(46,107,79,0.08)', borderWidth: 2.5,
          pointRadius: (c) => stressedSet.has(c.dataIndex) ? 4 : 0, pointBackgroundColor: '#9C4A3C',
          fill: true, tension: 0.25,
        },
      ],
    },
    options: {
      responsive: true, maintainAspectRatio: false, interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { position: 'bottom', labels: { boxWidth: 14, font: { family: 'IBM Plex Sans', size: 11 } } },
        tooltip: { callbacks: { label: (c) => `${c.dataset.label}: Rs.${fmt(c.parsed.y)}` } },
      },
      scales: { y: { ticks: { callback: (v) => `Rs.${fmt(v)}`, font: { size: 10 } } }, x: { ticks: { font: { size: 10 } } } },
    },
  });
}

function drawForecastChart(b) {
  destroyChart('forecast');
  const ctx = document.getElementById('forecastChart').getContext('2d');
  const hist = b.net_cash_flow.slice(-12);
  const histLabels = hist.map((_, i) => `M${b.net_cash_flow.length - 12 + i + 1}`);
  const fc = b.forecast.net_cash_flow;
  const fcLabels = fc.point.map((_, i) => `F${i + 1}`);
  const labels = [...histLabels, ...fcLabels];

  const histData = [...hist, ...Array(fc.point.length).fill(null)];
  const pointData = [...Array(hist.length - 1).fill(null), hist[hist.length - 1], ...fc.point];
  const lowerData = [...Array(hist.length - 1).fill(null), hist[hist.length - 1], ...fc.lower];
  const upperData = [...Array(hist.length - 1).fill(null), hist[hist.length - 1], ...fc.upper];

  charts.forecast = new Chart(ctx, {
    type: 'line',
    data: {
      labels,
      datasets: [
        { label: 'Upper range', data: upperData, borderColor: 'transparent', backgroundColor: 'rgba(176,130,38,0.12)', pointRadius: 0, fill: '+1', tension: 0.2 },
        { label: 'Lower range', data: lowerData, borderColor: 'transparent', backgroundColor: 'rgba(176,130,38,0.12)', pointRadius: 0, fill: false, tension: 0.2 },
        { label: 'Forecast', data: pointData, borderColor: '#B08226', borderDash: [5, 3], borderWidth: 2, pointRadius: 2, tension: 0.2 },
        { label: 'Historical (last 12mo)', data: histData, borderColor: '#2E6B4F', backgroundColor: 'transparent', borderWidth: 2, pointRadius: 0, tension: 0.2 },
      ],
    },
    options: {
      responsive: true, maintainAspectRatio: false, interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { position: 'bottom', labels: { boxWidth: 14, font: { size: 11 }, filter: (item) => item.text !== 'Lower range' } },
        tooltip: { callbacks: { label: (c) => `${c.dataset.label}: Rs.${fmt(c.parsed.y)}` }, filter: (item) => item.dataset.label !== 'Lower range' },
      },
      scales: { y: { ticks: { callback: (v) => `Rs.${fmt(v)}`, font: { size: 10 } } }, x: { ticks: { font: { size: 9 }, maxRotation: 0 } } },
    },
  });
}

// ============================================================
// SCENARIOS & WHAT-IF TAB
// ============================================================
function scenariosHTML(b) {
  const sc = b.scenarios;
  const pickKey = sc.optimizer_pick;
  const rows = Object.entries(sc.strategies).map(([key, s]) => {
    const isBest = key === pickKey;
    return `<tr class="${isBest ? 'best-row' : ''}">
      <td style="text-align:left;">${s.label}${isBest ? ' ★' : ''}</td>
      <td>Rs.${fmt(s.avg_payment)}</td>
      <td>Rs.${fmt(s.worst_cash_buffer)}</td>
      <td>${s.stress_months}</td>
      <td>${s.recovery_pct}%</td>
      <td>${s.sustainability_label}</td>
      <td>${s.scores.weighted}</td>
    </tr>`;
  }).join('');

  const cn = b.comparison_narrative;
  const narrativeBlock = cn.current_plan_fails ? `
    <div class="callout">
      <strong>Why not the current plan?</strong><br/>${cn.headline}
      <div style="margin-top:10px;display:flex;gap:24px;flex-wrap:wrap;">
        <div><strong>${cn.improvement.stress_months_before}</strong> stress months (current) → <strong>${cn.improvement.stress_months_after}</strong> stress months (${cn.recommended_label})</div>
        <div>Recovery: <strong>${cn.improvement.recovery_before_pct}%</strong> → <strong>${cn.improvement.recovery_after_pct}%</strong></div>
      </div>
    </div>` : `<div class="callout"><strong>${cn.headline}</strong></div>`;

  return `
    <section>
      <h2>Repayment strategy comparison</h2>
      <div class="panel">
        <div class="chart-wrap short"><canvas id="scheduleChart"></canvas></div>
        <div style="overflow-x:auto;margin-top:14px;">
          <table class="datatable">
            <thead><tr><th style="text-align:left;">Strategy</th><th>Avg Payment</th><th>Worst Buffer</th><th>Stress Months</th><th>Recovery</th><th>Sustainability</th><th>Score</th></tr></thead>
            <tbody>${rows}</tbody>
          </table>
        </div>
        <p style="font-size:0.76rem;color:var(--ink-soft);margin-top:10px;">
          ★ = optimizer's top pick, scored as ${sc.weights.sustainability}×sustainability + ${sc.weights.recovery}×recovery + ${sc.weights.stability}×payment stability.
          This is a transparent decision-support heuristic, not a claim of mathematically optimal contract design.
        </p>
      </div>
    </section>

    <section>${narrativeBlock}</section>

    <section>
      <h2>What-if: income-linked repayment simulator</h2>
      <div class="panel">
        <p style="font-size:0.82rem;color:var(--ink-soft);margin-top:0;">
          Drag the controls to see how an income-linked schedule would perform against this borrower's own
          historical cash flow. This recalculates live in your browser - the classification itself stays
          fixed (it's based on the full historical pattern), but the repayment structure below is fully interactive.
        </p>
        <div class="slider-grid">
          <div class="slider-row">
            <label>Repayment % of disposable cash <span class="v" id="valPct">35%</span></label>
            <input type="range" id="sliderPct" min="10" max="60" value="35" />
          </div>
          <div class="slider-row">
            <label>Safety buffer <span class="v" id="valBuffer">10%</span></label>
            <input type="range" id="sliderBuffer" min="0" max="25" value="10" />
          </div>
          <div class="slider-row">
            <label>Minimum payment (× installment) <span class="v" id="valMin">0.50×</span></label>
            <input type="range" id="sliderMin" min="20" max="90" value="50" />
          </div>
          <div class="slider-row">
            <label>Maximum payment (× installment) <span class="v" id="valMax">1.60×</span></label>
            <input type="range" id="sliderMax" min="100" max="220" value="160" />
          </div>
        </div>
        <div class="kpi-grid" style="margin-top:18px;margin-bottom:0;" id="whatIfResults"></div>
      </div>
    </section>
  `;
}

function drawScheduleChart(b) {
  destroyChart('schedule');
  const ctx = document.getElementById('scheduleChart').getContext('2d');
  const pickKey = b.scenarios.optimizer_pick;
  const recommended = b.scenarios.strategies[pickKey];
  const fixed = b.scenarios.strategies.fixed;
  const labels = fixed.schedule.map((_, i) => `M${i + 1}`);

  charts.schedule = new Chart(ctx, {
    type: 'bar',
    data: {
      labels,
      datasets: [
        { label: 'Original fixed installment', data: fixed.schedule, backgroundColor: 'rgba(68,80,89,0.35)', borderRadius: 2 },
        { label: `Recommended (${recommended.label})`, data: recommended.schedule, backgroundColor: '#B08226', borderRadius: 2 },
      ],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: {
        legend: { position: 'bottom', labels: { boxWidth: 14, font: { size: 11 } } },
        tooltip: { callbacks: { label: (c) => `${c.dataset.label}: Rs.${fmt(c.parsed.y)}` } },
      },
      scales: { y: { ticks: { callback: (v) => `Rs.${fmt(v)}`, font: { size: 10 } } }, x: { ticks: { font: { size: 9 }, maxRotation: 0, autoSkip: true, maxTicksLimit: 12 } } },
    },
  });
}

// ---- live client-side "what-if" income-linked recalculation ----
function simulateIncomeLinked(b, pct, minRatio, maxRatio, safetyBufferPct) {
  const installment = b.loan.installment;
  const netCf = b.net_cash_flow;
  const minPay = installment * minRatio;
  const maxPay = installment * maxRatio;
  const schedule = netCf.map(cf => {
    const disposable = Math.max(0, cf);
    const raw = disposable * pct;
    return Math.min(maxPay, Math.max(minPay, raw));
  });
  let stressed = 0, worst = Infinity;
  schedule.forEach((pay, i) => {
    const cf = netCf[i];
    const remaining = cf - pay;
    worst = Math.min(worst, remaining);
    const bufferNeeded = cf > 0 ? cf * (safetyBufferPct / 100) : 0;
    if (remaining < bufferNeeded) stressed++;
  });
  const totalPayment = schedule.reduce((a, v) => a + v, 0);
  const originalTotal = installment * b.loan.tenure_months;
  const recoveryPct = originalTotal ? (totalPayment / originalTotal * 100) : 0;
  return {
    avgPayment: totalPayment / schedule.length,
    worstBuffer: worst === Infinity ? 0 : worst,
    stressMonths: stressed,
    recoveryPct,
  };
}

function wireWhatIf(b) {
  const sliderPct = document.getElementById('sliderPct');
  const sliderBuffer = document.getElementById('sliderBuffer');
  const sliderMin = document.getElementById('sliderMin');
  const sliderMax = document.getElementById('sliderMax');
  if (!sliderPct) return;

  function recompute() {
    const pct = Number(sliderPct.value) / 100;
    const bufferPct = Number(sliderBuffer.value);
    const minR = Number(sliderMin.value) / 100;
    const maxR = Number(sliderMax.value) / 100;
    document.getElementById('valPct').textContent = `${sliderPct.value}%`;
    document.getElementById('valBuffer').textContent = `${sliderBuffer.value}%`;
    document.getElementById('valMin').textContent = `${minR.toFixed(2)}×`;
    document.getElementById('valMax').textContent = `${maxR.toFixed(2)}×`;

    const r = simulateIncomeLinked(b, pct, minR, maxR, bufferPct);
    document.getElementById('whatIfResults').innerHTML = `
      <div class="kpi-card"><div class="num figure">Rs.${fmt(r.avgPayment)}</div><div class="label">AVG MONTHLY PAYMENT</div></div>
      <div class="kpi-card"><div class="num figure">Rs.${fmt(r.worstBuffer)}</div><div class="label">WORST-MONTH BUFFER</div></div>
      <div class="kpi-card"><div class="num figure">${r.stressMonths}</div><div class="label">PROJECTED STRESS MONTHS</div></div>
      <div class="kpi-card"><div class="num figure">${r.recoveryPct.toFixed(1)}%</div><div class="label">LENDER RECOVERY</div></div>
    `;
  }
  [sliderPct, sliderBuffer, sliderMin, sliderMax].forEach(s => s.addEventListener('input', recompute));
  recompute();
}