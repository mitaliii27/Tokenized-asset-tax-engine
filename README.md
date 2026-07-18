# Tokenized Asset Financial Forecasting &amp; Automated Tax Compliance Engine

An end-to-end pipeline for an institutional digital-asset desk: it turns raw
blockchain ledger events and free-text broker confirmations into daily FP&A
flash results, a Form 1099-DA tax staging report, and an AML anomaly
case-management workflow — with an executive dashboard on top.

**This is a portfolio project built on synthetic data** (see [Scope &amp;
honesty notes](#scope--honesty-notes) below) — it is designed to demonstrate
the full skill set, end to end and runnably, not to represent a real
employer's system or real client data.

## Business objective

Institutional clients want real-time visibility into the profitability of
their tokenized-asset portfolios. The back office needs an automated way to
classify transactions for tax purposes and flag activity that looks like AML
risk — without waiting on a manual month-end close.

## Architecture

```
blockchain_ledger_raw.csv  ──┐
                              ├─▶ xceptor_extractor.py ─▶ normalized_transactions.parquet
broker_statements_raw.txt ──┘         (template-based           │
                                        field extraction)        ▼
                                                          etl_pipeline.py (PySpark)
                                                     dedupe · quality gate · type cast
                                                                  │
                                                                  ▼
                                                    ┌────── warehouse.db (SQL) ──────┐
                                                    │                                 │
                                                    ▼                                 ▼
                                          financial_model.py                  tax_engine.py
                                     flash results & variance         FIFO gains · wash-sale ·
                                                    │                  1099-DA staging
                                                    │                                 │
                                                    ▼                                 │
                                          aml_anomaly_model.py                        │
                                        Isolation Forest anomaly                      │
                                          detection on ledger flow                    │
                                                    │                                 │
                                                    ▼                                 │
                                        workflow_simulator.py                         │
                                     Appian-style case routing                        │
                                                    │                                 │
                                                    └───────────────┬─────────────────┘
                                                                    ▼
                                                     dashboard/build_dashboard.py
                                                       (Plotly / Tableau-equivalent)
```

## Repo layout

```
data/generate_data.py       synthetic blockchain ledger + broker statement generator
src/xceptor_extractor.py    template-based structured/semi-structured field extraction
src/etl_pipeline.py         PySpark ETL: dedupe, data-quality gate, silver/gold load
src/financial_model.py      monthly flash results + budget-vs-actual variance
src/tax_engine.py           FIFO realized gains, wash-sale detection, 1099-DA staging
src/aml_anomaly_model.py    Isolation Forest anomaly detection (AML) + evaluation
src/workflow_simulator.py   Appian-style case management for flagged anomalies
dashboard/build_dashboard.py  builds the standalone HTML executive dashboard
run_pipeline.py              orchestrates all of the above end to end
tests/test_pipeline.py       unit tests (fast, no Spark session required)
outputs/                     generated reports + metrics.json (git-ignored, regenerate locally)
```

## Quickstart

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 1. generate the synthetic source data (50k ledger events, 8k broker lines)
python data/generate_data.py --rows 50000 --broker-rows 8000 --seed 42

# 2. run the full pipeline (extraction → ETL → FP&A → tax → AML → workflow)
python run_pipeline.py

# 3. build the dashboard
python dashboard/build_dashboard.py
open dashboard/dashboard.html   # (or just double-click the file)

# tests
pytest tests/ -q
```

Requires a JDK on PATH for PySpark (`JAVA_HOME` is auto-set to a common
Ubuntu OpenJDK path in `etl_pipeline.py` — adjust for your machine, or `pip
install pyspark` will still run against any local JVM ≥ 11).

## Results (from this repo's own synthetic dataset — see honesty note below)

Numbers below are what `run_pipeline.py` actually produced on the 50,000-event
/ 8,000-line synthetic dataset generated with `--seed 42`, taken straight from
`outputs/metrics.json`:

| Metric | Value |
|---|---|
| Events ingested | 57,839 |
| Data-quality pass rate (ETL gate) | 99.3% |
| Broker lines auto-parsed by the extractor | 98.0% (161 sent to exception queue) |
| Realized tax lots processed (FIFO) | 2,723 across 250 clients |
| Wash-sale lots flagged | 655 |
| AML model — precision / recall / F1 | 0.68 / 0.71 / 0.69 |
| AML model — ROC-AUC | 0.990 |
| Cases opened in the review workflow | 596 (109 escalated to compliance) |
| Average case cycle time | 15.8 hours |

The AML precision/recall figures are measured against a small set of
synthetic anomalies injected by `generate_data.py` (oversized/mispriced
trades) purely so the model can be scored — production AML validation would
instead use investigator-confirmed/dismissed alert history.

## Skills demonstrated

| Area | Tools / techniques |
|---|---|
| Data capture | Template-based extraction of structured (JSON) and unstructured (free text) sources |
| Data engineering | PySpark, data-quality gating, partitioned parquet, SQL warehouse load |
| FP&A | Monthly flash results, budget-vs-actual variance analysis |
| Tax | FIFO cost basis, holding-period classification, wash-sale detection, 1099-DA staging |
| Analytics / ML | Isolation Forest anomaly detection, precision/recall/ROC-AUC evaluation |
| BI / workflow | Interactive dashboard (Plotly), BPM-style case routing and SLA tracking |

## Scope &amp; honesty notes

- **Data is synthetic.** `data/generate_data.py` generates all source data
  with seeded randomness — there is no real client, trading, or tax data
  anywhere in this repo. Every metric above is a genuine measurement on that
  synthetic data, not an aspirational or invented number.
- **Xceptor and Appian are licensed enterprise platforms** this repo does not
  have access to. `xceptor_extractor.py` and `workflow_simulator.py` are
  open-source stand-ins that reproduce the same *pattern* (template-based
  extraction; stateful case routing with SLAs) so the pipeline is runnable
  end to end without a license. If you have access to the real platforms,
  the README architecture diagram shows exactly where to swap them in — both
  modules emit/consume plain CSV so the integration point is a file, not code.
- **Tableau is a licensed desktop/server product** and can't be authored
  headlessly here; `dashboard/build_dashboard.py` produces a standalone
  Plotly/HTML dashboard from the same output CSVs a Tableau workbook would
  use, with the chart-to-worksheet mapping documented in the file's docstring.
- **The 1099-DA staging report is a data-engineering demo**, not tax-filing
  software — it does not implement every IRS edge case (e.g. multi-account
  wash-sale chaining, gifted/inherited basis) and should not be treated as
  tax advice.

## License

MIT — see [LICENSE](LICENSE).
