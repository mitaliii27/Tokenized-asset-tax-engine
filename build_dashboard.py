"""
build_dashboard.py
--------------------
Builds dashboard/dashboard.html - a self-contained, standalone executive
dashboard (Plotly.js via CDN) populated entirely from this project's own
pipeline outputs (outputs/metrics.json, outputs/flash_variance_report.csv,
outputs/form_1099da_staging.csv, outputs/appian_case_log.csv).

NOTE ON SCOPE: this stands in for the Tableau workbook a production version
of this project would ship (Tableau is a licensed desktop/server product and
can't be authored headlessly in this environment). The chart logic below
maps directly onto Tableau worksheets: line -> monthly volume trend, bar ->
variance by asset class, donut -> tax liability mix, funnel -> AML case
lifecycle. Point a real Tableau workbook at the same outputs/*.csv files to
rebuild this as an actual .twbx, using the chart mapping documented in README.md.

Run after run_pipeline.py:  python dashboard/build_dashboard.py
"""
import json

import pandas as pd

INK = "#0F1C2E"
CREAM = "#F4EFE4"
ACCENT = "#2F6F73"       # teal - digital asset primary accent
ALERT = "#C98A2C"        # amber - flagged / variance breach
POSITIVE = "#5B7553"     # moss - cleared
NEGATIVE = "#A6402C"     # brick - escalated / high risk
STAMP_TEXT = "DIGITAL ASSET DESK — FLASH"


def load_data():
    with open("outputs/metrics.json") as f:
        metrics = json.load(f)
    flash = pd.read_csv("outputs/flash_variance_report.csv")
    tax = pd.read_csv("outputs/form_1099da_staging.csv")
    cases = pd.read_csv("outputs/appian_case_log.csv")
    return metrics, flash, tax, cases


def build_chart_data(flash, tax, cases):
    monthly = flash.groupby("trade_month").agg(gross=("gross_volume_usd", "sum"),
                                                 budget=("budget_gross_volume_usd", "sum")).reset_index()
    variance_by_class = (
        flash.groupby("asset_class")["variance_pct"].mean().sort_values(ascending=False).reset_index()
    )
    tax_by_period = tax.groupby("holding_period")["est_tax_liability_usd"].sum().reset_index()
    funnel_stages = ["DETECTED", "ASSIGNED", "UNDER_REVIEW", "CLEARED", "ESCALATED"]
    funnel_counts = [len(cases), len(cases), len(cases),
                     int((cases.final_state == "CLEARED").sum()), int((cases.final_state == "ESCALATED").sum())]
    reviewer_load = cases["reviewer"].value_counts().reset_index()
    reviewer_load.columns = ["reviewer", "cases"]

    return {
        "months": monthly["trade_month"].tolist(),
        "gross": monthly["gross"].round(0).tolist(),
        "budget": monthly["budget"].round(0).tolist(),
        "variance_classes": variance_by_class["asset_class"].tolist(),
        "variance_vals": (variance_by_class["variance_pct"] * 100).round(1).tolist(),
        "tax_periods": tax_by_period["holding_period"].tolist(),
        "tax_vals": tax_by_period["est_tax_liability_usd"].round(0).tolist(),
        "funnel_stages": funnel_stages,
        "funnel_counts": funnel_counts,
        "reviewers": reviewer_load["reviewer"].tolist(),
        "reviewer_cases": reviewer_load["cases"].tolist(),
    }


KPI_TEMPLATE = """
<div class="kpi">
  <div class="kpi-bar" style="background:{color}"></div>
  <div class="kpi-value">{value}</div>
  <div class="kpi-label">{label}</div>
</div>"""


def fmt_usd(x):
    if abs(x) >= 1_000_000:
        return "${:,.1f}M".format(x/1_000_000)
    if abs(x) >= 1_000:
        return "${:,.0f}K".format(x/1_000)
    return "${:,.0f}".format(x)


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Tokenized Asset Flash &amp; Tax Compliance — Dashboard</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/plotly.js/2.32.0/plotly.min.js"></script>
<style>
  :root {{
    --ink: {ink}; --cream: {cream}; --accent: {accent};
    --alert: {alert}; --positive: {positive}; --negative: {negative};
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; background: var(--cream); color: var(--ink);
    font-family: -apple-system, "Segoe UI", Helvetica, Arial, sans-serif;
  }}
  .serif {{ font-family: Georgia, "Iowan Old Style", "Times New Roman", serif; }}
  .mono {{ font-family: ui-monospace, "SF Mono", "JetBrains Mono", Menlo, Consolas, monospace; }}

  header {{
    background: var(--ink); color: var(--cream); padding: 36px 48px 30px;
    position: relative; overflow: hidden;
  }}
  .eyebrow {{
    font-family: ui-monospace, monospace; letter-spacing: 3px; font-size: 11px;
    text-transform: uppercase; color: var(--accent); margin-bottom: 10px;
  }}
  h1 {{ font-size: 30px; margin: 0 0 6px; font-weight: 500; }}
  .period {{ font-family: ui-monospace, monospace; font-size: 12px; opacity: 0.65; }}

  .stamp {{
    position: absolute; top: 28px; right: 54px; border: 2px dashed var(--accent);
    color: var(--accent); padding: 10px 18px; font-family: ui-monospace, monospace;
    font-size: 11px; letter-spacing: 2px; transform: rotate(-7deg); opacity: 0.85;
    text-transform: uppercase; border-radius: 2px;
  }}

  main {{ padding: 34px 48px 60px; max-width: 1280px; margin: 0 auto; }}

  .kpi-row {{ display: grid; grid-template-columns: repeat(5, 1fr); gap: 18px; margin-bottom: 34px; }}
  .kpi {{ background: #fff; border: 1px solid rgba(15,28,46,0.12); padding: 18px 16px 16px; position: relative; }}
  .kpi-bar {{ height: 3px; width: 30px; margin-bottom: 12px; }}
  .kpi-value {{ font-family: ui-monospace, monospace; font-size: 26px; font-weight: 600; line-height: 1; }}
  .kpi-label {{ font-size: 11.5px; opacity: 0.7; margin-top: 8px; line-height: 1.35; }}

  .panel {{
    background: #fff; border: 1px solid rgba(15,28,46,0.12); padding: 20px 22px 8px; margin-bottom: 22px;
  }}
  .panel h2 {{ font-size: 14px; text-transform: uppercase; letter-spacing: 1.5px; font-weight: 600; margin: 0 0 4px; }}
  .panel .sub {{ font-size: 12px; opacity: 0.6; margin-bottom: 10px; }}

  .grid-2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 22px; }}

  footer {{
    padding: 20px 48px 40px; font-size: 11.5px; opacity: 0.6; max-width: 1280px; margin: 0 auto;
    font-family: ui-monospace, monospace;
  }}
  hr.rule {{ border: none; border-top: 1px solid rgba(15,28,46,0.15); margin: 28px 0; }}
</style>
</head>
<body>
<header>
  <div class="stamp">{stamp_text}</div>
  <div class="eyebrow">Institutional Digital Assets &middot; Flash Reporting</div>
  <h1 class="serif">Tokenized Asset Financial Forecasting &amp; Tax Compliance</h1>
  <div class="period">PERIOD: 2025-01 &rarr; 2026-02 &middot; SOURCE: blockchain ledger + broker confirmations &middot; GENERATED FROM outputs/metrics.json</div>
</header>
<main>
  <div class="kpi-row">{kpi_html}</div>

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
  Data-quality pass rate {etl_pass:.1%} on {rows_ingested:,} ingested events &middot; AML model ROC-AUC {auc:.3f} &middot;
  Figures computed on the synthetic dataset shipped in this repo (data/generate_data.py) — not real client or trading data.
</footer>

<script>
const d = {data_json};
const font = {{ family: 'ui-monospace, "SF Mono", Menlo, Consolas, monospace', color: '{ink}' }};
const layoutBase = {{
  margin: {{ t: 10, r: 20, b: 40, l: 55 }}, paper_bgcolor: 'white', plot_bgcolor: 'white',
  font: font, showlegend: true, legend: {{ orientation: 'h', y: 1.15 }}
}};

Plotly.newPlot('volumeChart', [
  {{ x: d.months, y: d.gross, type: 'scatter', mode: 'lines+markers', name: 'Actual', line: {{color: '{accent}', width: 3}} }},
  {{ x: d.months, y: d.budget, type: 'scatter', mode: 'lines', name: 'Plan (trailing avg)', line: {{color: '{ink}', width: 2, dash: 'dot'}} }}
], Object.assign({{}}, layoutBase, {{yaxis: {{title: 'USD'}}}}), {{displayModeBar: false, responsive: true}});

Plotly.newPlot('varianceChart', [
  {{ x: d.variance_classes, y: d.variance_vals, type: 'bar', marker: {{color: d.variance_vals.map(v => v > 5 ? '{alert}' : '{positive}')}} }}
], Object.assign({{}}, layoutBase, {{showlegend: false, yaxis: {{title: '% variance'}}, shapes: [{{type:'line', x0:-0.5, x1:d.variance_classes.length-0.5, y0:5, y1:5, line:{{color:'{negative}', dash:'dash', width:1.5}}}}]}}), {{displayModeBar: false, responsive: true}});

Plotly.newPlot('taxChart', [
  {{ labels: d.tax_periods, values: d.tax_vals, type: 'pie', hole: 0.55, marker: {{colors: ['{accent}', '{ink}']}} }}
], Object.assign({{}}, layoutBase), {{displayModeBar: false, responsive: true}});

Plotly.newPlot('funnelChart', [
  {{ type: 'funnel', y: d.funnel_stages, x: d.funnel_counts, marker: {{color: ['{ink}','{accent}','{accent}','{positive}','{negative}']}} }}
], Object.assign({{}}, layoutBase, {{showlegend: false}}), {{displayModeBar: false, responsive: true}});

Plotly.newPlot('reviewerChart', [
  {{ x: d.reviewers, y: d.reviewer_cases, type: 'bar', marker: {{color: '{accent}'}} }}
], Object.assign({{}}, layoutBase, {{showlegend: false, yaxis: {{title: 'cases'}}}}), {{displayModeBar: false, responsive: true}});
</script>
</body>
</html>
"""


def main():
    metrics, flash, tax, cases = load_data()
    chart_data = build_chart_data(flash, tax, cases)
    fpna, tax_m, aml, etl, wf = metrics["fpna"], metrics["tax"], metrics["aml"], metrics["etl"], metrics["workflow"]

    kpis = [
        (fmt_usd(fpna["total_gross_volume_usd"]), "Gross Trading Volume (14 mo)", ACCENT),
        (fmt_usd(tax_m["total_estimated_tax_liability_usd"]), "Est. Tax Liability Staged", INK),
        ("{:.1f}%".format(etl["data_quality_pass_rate"]*100), "Feed Data-Quality Pass Rate", POSITIVE),
        (str(aml["n_flagged"]), "AML Alerts Flagged (Isolation Forest)", ALERT),
        (str(wf["escalated_to_compliance"]), "Cases Escalated to Compliance", NEGATIVE),
    ]
    kpi_html = "".join(KPI_TEMPLATE.format(value=v, label=l, color=c) for v, l, c in kpis)

    html = HTML_TEMPLATE.format(
        ink=INK, cream=CREAM, accent=ACCENT, alert=ALERT, positive=POSITIVE, negative=NEGATIVE,
        stamp_text=STAMP_TEXT, kpi_html=kpi_html,
        data_json=json.dumps(chart_data),
        etl_pass=etl["data_quality_pass_rate"], rows_ingested=etl["rows_ingested"], auc=aml["roc_auc"],
    )
    with open("dashboard/dashboard.html", "w") as f:
        f.write(html)
    print("Wrote dashboard/dashboard.html")


if __name__ == "__main__":
    main()
