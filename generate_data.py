<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Tokenized Asset Flash &amp; Tax Compliance — Dashboard</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/plotly.js/2.32.0/plotly.min.js"></script>
<style>
  :root {
    --ink: #0F1C2E; --cream: #F4EFE4; --accent: #2F6F73;
    --alert: #C98A2C; --positive: #5B7553; --negative: #A6402C;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; background: var(--cream); color: var(--ink);
    font-family: -apple-system, "Segoe UI", Helvetica, Arial, sans-serif;
  }
  .serif { font-family: Georgia, "Iowan Old Style", "Times New Roman", serif; }
  .mono { font-family: ui-monospace, "SF Mono", "JetBrains Mono", Menlo, Consolas, monospace; }

  header {
    background: var(--ink); color: var(--cream); padding: 36px 48px 30px;
    position: relative; overflow: hidden;
  }
  .eyebrow {
    font-family: ui-monospace, monospace; letter-spacing: 3px; font-size: 11px;
    text-transform: uppercase; color: var(--accent); margin-bottom: 10px;
  }
  h1 { font-size: 30px; margin: 0 0 6px; font-weight: 500; }
  .period { font-family: ui-monospace, monospace; font-size: 12px; opacity: 0.65; }

  .stamp {
    position: absolute; top: 28px; right: 54px; border: 2px dashed var(--accent);
    color: var(--accent); padding: 10px 18px; font-family: ui-monospace, monospace;
    font-size: 11px; letter-spacing: 2px; transform: rotate(-7deg); opacity: 0.85;
    text-transform: uppercase; border-radius: 2px;
  }

  main { padding: 34px 48px 60px; max-width: 1280px; margin: 0 auto; }

  .kpi-row { display: grid; grid-template-columns: repeat(5, 1fr); gap: 18px; margin-bottom: 34px; }
  .kpi { background: #fff; border: 1px solid rgba(15,28,46,0.12); padding: 18px 16px 16px; position: relative; }
  .kpi-bar { height: 3px; width: 30px; margin-bottom: 12px; }
  .kpi-value { font-family: ui-monospace, monospace; font-size: 26px; font-weight: 600; line-height: 1; }
  .kpi-label { font-size: 11.5px; opacity: 0.7; margin-top: 8px; line-height: 1.35; }

  .panel {
    background: #fff; border: 1px solid rgba(15,28,46,0.12); padding: 20px 22px 8px; margin-bottom: 22px;
  }
  .panel h2 { font-size: 14px; text-transform: uppercase; letter-spacing: 1.5px; font-weight: 600; margin: 0 0 4px; }
  .panel .sub { font-size: 12px; opacity: 0.6; margin-bottom: 10px; }

  .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 22px; }

  footer {
    padding: 20px 48px 40px; font-size: 11.5px; opacity: 0.6; max-width: 1280px; margin: 0 auto;
    font-family: ui-monospace, monospace;
  }
  hr.rule { border: none; border-top: 1px solid rgba(15,28,46,0.15); margin: 28px 0; }
</style>
</head>
<body>
<header>
  <div class="stamp">DIGITAL ASSET DESK — FLASH</div>
  <div class="eyebrow">Institutional Digital Assets &middot; Flash Reporting</div>
  <h1 class="serif">Tokenized Asset Financial Forecasting &amp; Tax Compliance</h1>
  <div class="period">PERIOD: 2025-01 &rarr; 2026-02 &middot; SOURCE: blockchain ledger + broker confirmations &middot; GENERATED FROM outputs/metrics.json</div>
</header>
<main>
  <div class="kpi-row">
<div class="kpi">
  <div class="kpi-bar" style="background:#2F6F73"></div>
  <div class="kpi-value">$141.4M</div>
  <div class="kpi-label">Gross Trading Volume (14 mo)</div>
</div>
<div class="kpi">
  <div class="kpi-bar" style="background:#0F1C2E"></div>
  <div class="kpi-value">$352K</div>
  <div class="kpi-label">Est. Tax Liability Staged</div>
</div>
<div class="kpi">
  <div class="kpi-bar" style="background:#5B7553"></div>
  <div class="kpi-value">99.3%</div>
  <div class="kpi-label">Feed Data-Quality Pass Rate</div>
</div>
<div class="kpi">
  <div class="kpi-bar" style="background:#C98A2C"></div>
  <div class="kpi-value">596</div>
  <div class="kpi-label">AML Alerts Flagged (Isolation Forest)</div>
</div>
<div class="kpi">
  <div class="kpi-bar" style="background:#A6402C"></div>
  <div class="kpi-value">109</div>
  <div class="kpi-label">Cases Escalated to Compliance</div>
</div></div>

  <div class="panel">
    <h2 class="serif">Monthly Gross Trading Volume vs. Plan</h2>
    <div class="sub">Actual gross notional volume against a trailing 3-month planning proxy, by month</div>
    <div id="volumeChart" style="height:320px"></div>
  </div>

  <div class="grid-2">
    <div class="panel">
      <h2 class="serif">Variance vs. Plan by Asset Class</h2>
      <div class="sub">Average absolute variance %, 5% Appian escalation threshold marked</div>
      <div id="varianceChart" style="height:300px"></div>
    </div>
    <div class="panel">
      <h2 class="serif">Estimated Tax Liability by Holding Period</h2>
      <div class="sub">Staged for Form 1099-DA prep — short-term vs. long-term</div>
      <div id="taxChart" style="height:300px"></div>
    </div>
  </div>

  <div class="grid-2">
    <div class="panel">
      <h2 class="serif">AML Case Lifecycle</h2>
      <div class="sub">Isolation Forest alerts routed through the case-management workflow</div>
      <div id="funnelChart" style="height:300px"></div>
    </div>
    <div class="panel">
      <h2 class="serif">Reviewer Caseload</h2>
      <div class="sub">Cases assigned per compliance reviewer this period</div>
      <div id="reviewerChart" style="height:300px"></div>
    </div>
  </div>

  <hr class="rule">
</main>
<footer>
  Data-quality pass rate 99.3% on 57,839 ingested events &middot; AML model ROC-AUC 0.990 &middot;
  Figures computed on the synthetic dataset shipped in this repo (data/generate_data.py) — not real client or trading data.
</footer>

<script>
const d = {"months": ["2025-01", "2025-02", "2025-03", "2025-04", "2025-05", "2025-06", "2025-07", "2025-08", "2025-09", "2025-10", "2025-11", "2025-12", "2026-01", "2026-02"], "gross": [11206844.0, 9599427.0, 10187241.0, 10989981.0, 10708108.0, 13357480.0, 11947210.0, 10994133.0, 10136027.0, 10883731.0, 10343272.0, 10266399.0, 9742758.0, 991118.0], "budget": [11430981.0, 11430981.0, 10611198.0, 10537794.0, 10464060.0, 10841012.0, 11918893.0, 12244351.0, 12341600.0, 11246306.0, 10884723.0, 10663430.0, 10707757.0, 10319826.0], "variance_classes": ["tokenized_money_market", "tokenized_treasury", "tokenized_reit", "tokenized_equity", "tokenized_corp_bond"], "variance_vals": [23.1, 22.3, 17.5, 16.6, 15.9], "tax_periods": ["long_term", "short_term"], "tax_vals": [562.0, 351008.0], "funnel_stages": ["DETECTED", "ASSIGNED", "UNDER_REVIEW", "CLEARED", "ESCALATED"], "funnel_counts": [596, 596, 596, 487, 109], "reviewers": ["R. Castillo", "J. Okafor", "A. Menon", "S. Iyer", "T. Nakamura"], "reviewer_cases": [135, 124, 117, 111, 109]};
const font = { family: 'ui-monospace, "SF Mono", Menlo, Consolas, monospace', color: '#0F1C2E' };
const layoutBase = {
  margin: { t: 10, r: 20, b: 40, l: 55 }, paper_bgcolor: 'white', plot_bgcolor: 'white',
  font: font, showlegend: true, legend: { orientation: 'h', y: 1.15 }
};

Plotly.newPlot('volumeChart', [
  { x: d.months, y: d.gross, type: 'scatter', mode: 'lines+markers', name: 'Actual', line: {color: '#2F6F73', width: 3} },
  { x: d.months, y: d.budget, type: 'scatter', mode: 'lines', name: 'Plan (trailing avg)', line: {color: '#0F1C2E', width: 2, dash: 'dot'} }
], Object.assign({}, layoutBase, {yaxis: {title: 'USD'}}), {displayModeBar: false, responsive: true});

Plotly.newPlot('varianceChart', [
  { x: d.variance_classes, y: d.variance_vals, type: 'bar', marker: {color: d.variance_vals.map(v => v > 5 ? '#C98A2C' : '#5B7553')} }
], Object.assign({}, layoutBase, {showlegend: false, yaxis: {title: '% variance'}, shapes: [{type:'line', x0:-0.5, x1:d.variance_classes.length-0.5, y0:5, y1:5, line:{color:'#A6402C', dash:'dash', width:1.5}}]}), {displayModeBar: false, responsive: true});

Plotly.newPlot('taxChart', [
  { labels: d.tax_periods, values: d.tax_vals, type: 'pie', hole: 0.55, marker: {colors: ['#2F6F73', '#0F1C2E']} }
], Object.assign({}, layoutBase), {displayModeBar: false, responsive: true});

Plotly.newPlot('funnelChart', [
  { type: 'funnel', y: d.funnel_stages, x: d.funnel_counts, marker: {color: ['#0F1C2E','#2F6F73','#2F6F73','#5B7553','#A6402C']} }
], Object.assign({}, layoutBase, {showlegend: false}), {displayModeBar: false, responsive: true});

Plotly.newPlot('reviewerChart', [
  { x: d.reviewers, y: d.reviewer_cases, type: 'bar', marker: {color: '#2F6F73'} }
], Object.assign({}, layoutBase, {showlegend: false, yaxis: {title: 'cases'}}), {displayModeBar: false, responsive: true});
</script>
</body>
</html>
