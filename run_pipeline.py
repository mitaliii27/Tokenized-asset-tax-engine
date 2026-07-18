"""
run_pipeline.py
-----------------
End-to-end orchestration:
  1. Xceptor-style extraction of raw blockchain + broker sources
  2. PySpark ETL into the SQL warehouse
  3. FP&A flash results + variance analysis
  4. Tax classification + 1099-DA staging
  5. Isolation Forest AML anomaly detection
  6. Appian-style case workflow for flagged anomalies

Writes outputs/metrics.json, consumed by dashboard/build_dashboard.py.

Usage: python run_pipeline.py
"""
import json
import os
import time

os.makedirs("outputs", exist_ok=True)


def main():
    t0 = time.time()
    metrics = {}

    print("== [1/6] Xceptor-style extraction ==")
    from src import xceptor_extractor
    combined = xceptor_extractor.run("data/blockchain_ledger_raw.csv", "data/broker_statements_raw.txt")
    combined.to_parquet("data/normalized_transactions.parquet", index=False)

    print("== [2/6] PySpark ETL -> SQL warehouse ==")
    from src import etl_pipeline
    metrics["etl"] = etl_pipeline.run_etl("data/normalized_transactions.parquet", "data/warehouse.db")

    print("== [3/6] FP&A flash results + variance ==")
    from src import financial_model
    metrics["fpna"] = financial_model.run("data/warehouse.db")

    print("== [4/6] Tax classification + 1099-DA staging ==")
    from src import tax_engine
    metrics["tax"] = tax_engine.run("data/warehouse.db")

    print("== [5/6] AML anomaly detection ==")
    from src import aml_anomaly_model
    metrics["aml"] = aml_anomaly_model.run("data/warehouse.db", "data/blockchain_ledger_raw.csv")

    print("== [6/6] Appian-style case workflow ==")
    from src import workflow_simulator
    metrics["workflow"] = workflow_simulator.run("outputs/aml_flagged_transactions.csv")

    metrics["_meta"] = {"pipeline_runtime_seconds": round(time.time() - t0, 1)}

    with open("outputs/metrics.json", "w") as f:
        json.dump(metrics, f, indent=2, default=str)

    print("\n=== PIPELINE COMPLETE ===")
    print(json.dumps(metrics, indent=2, default=str))


if __name__ == "__main__":
    main()
