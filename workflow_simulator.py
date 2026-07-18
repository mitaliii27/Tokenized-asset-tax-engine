"""
aml_anomaly_model.py
----------------------
Unsupervised anomaly detection over the cleaned transaction warehouse using
an Isolation Forest, aimed at surfacing trades that look like potential
AML risk or reporting inconsistencies (unusual size, off-market pricing,
or bursty client activity).

Because real AML labels don't exist for this synthetic dataset, generate_data.py
seeds a small, known set of injected anomalies (`_seeded_anomaly` - oversized /
mispriced trades) purely so this script can report precision/recall against a
ground truth. In production there are no seeded labels; the model would be
validated against investigator feedback (confirmed/dismissed alerts) instead.
"""
import sqlite3

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.metrics import precision_recall_fscore_support, roc_auc_score


FEATURES = ["quantity", "price_usd", "notional_usd", "z_qty", "z_price", "client_trade_count_7d"]


def load_ledger_with_ground_truth(sqlite_path: str, raw_ledger_path: str) -> pd.DataFrame:
    conn = sqlite3.connect(sqlite_path)
    txns = pd.read_sql("SELECT * FROM transactions WHERE source='blockchain_ledger'", conn)
    conn.close()

    ground_truth = pd.read_csv(raw_ledger_path)[["event_id", "seeded_anomaly"]]
    df = txns.merge(ground_truth, on="event_id", how="left")
    df["timestamp"] = pd.to_datetime(df["timestamp"], format="mixed", errors="coerce")
    return df.dropna(subset=["timestamp"])


def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values("timestamp").copy()
    df["z_qty"] = df.groupby("symbol")["quantity"].transform(lambda s: (s - s.mean()) / (s.std() + 1e-9))
    df["z_price"] = df.groupby("symbol")["price_usd"].transform(lambda s: (s - s.mean()) / (s.std() + 1e-9))

    # rolling 7-day trade count per counterparty - proxy for "bursty" activity
    df = df.set_index("timestamp")
    counts = (
        df.groupby("counterparty")["event_id"]
        .rolling("7D")
        .count()
        .reset_index(level=0, drop=True)
    )
    df["client_trade_count_7d"] = counts
    df = df.reset_index()
    df["client_trade_count_7d"] = df["client_trade_count_7d"].fillna(1)
    return df


def train_and_score(df: pd.DataFrame, contamination: float = 0.012):
    X = df[FEATURES].fillna(0).values
    model = IsolationForest(
        n_estimators=300, contamination=contamination, random_state=42, n_jobs=-1
    )
    model.fit(X)
    # decision_function: higher = more normal. Flip sign so higher = more anomalous.
    df = df.copy()
    df["anomaly_score"] = -model.decision_function(X)
    df["flagged"] = model.predict(X) == -1
    return df, model


def evaluate(df: pd.DataFrame) -> dict:
    y_true = df["seeded_anomaly"].fillna(0).astype(int)
    y_pred = df["flagged"].astype(int)
    precision, recall, f1, _ = precision_recall_fscore_support(y_true, y_pred, average="binary", zero_division=0)
    try:
        auc = roc_auc_score(y_true, df["anomaly_score"])
    except ValueError:
        auc = float("nan")
    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "roc_auc": round(auc, 4),
        "n_flagged": int(df["flagged"].sum()),
        "n_ground_truth_anomalies": int(y_true.sum()),
    }


def run(sqlite_path: str, raw_ledger_path: str) -> dict:
    df = load_ledger_with_ground_truth(sqlite_path, raw_ledger_path)
    df = engineer_features(df)
    scored, _ = train_and_score(df)
    metrics = evaluate(scored)

    flagged = scored[scored["flagged"]].sort_values("anomaly_score", ascending=False)
    flagged[
        ["event_id", "timestamp", "symbol", "quantity", "price_usd", "notional_usd", "anomaly_score", "seeded_anomaly"]
    ].to_csv("outputs/aml_flagged_transactions.csv", index=False)

    return metrics


if __name__ == "__main__":
    print(run("data/warehouse.db", "data/blockchain_ledger_raw.csv"))
