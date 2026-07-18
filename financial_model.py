"""
financial_model.py
--------------------
FP&A layer: turns the cleaned transaction warehouse into monthly flash
results per tokenized asset class, plus a budget-vs-actual variance view
(the "budget" is a simple prior-month-trend forecast, standing in for the
bank's official planning figures - swap `build_budget()` for a real feed
from the planning system).
"""
import sqlite3

import numpy as np
import pandas as pd


# reference/master-data table: neither raw feed carries asset_class, so it is
# resolved via a symbol lookup - a standard "conform to reference data" ETL step
SYMBOL_ASSET_CLASS = {
    "TBOND-24": "tokenized_treasury",
    "TREIT-A": "tokenized_reit",
    "TEQ-MSFT": "tokenized_equity",
    "TEQ-NVDA": "tokenized_equity",
    "TCORP-HY": "tokenized_corp_bond",
    "TCASH-USD": "tokenized_money_market",
}


def load_transactions(sqlite_path: str) -> pd.DataFrame:
    conn = sqlite3.connect(sqlite_path)
    df = pd.read_sql("SELECT * FROM transactions", conn)
    conn.close()
    df["trade_month"] = df["trade_month"].astype(str)
    df["asset_class"] = df["symbol"].map(SYMBOL_ASSET_CLASS).fillna("unclassified")
    return df


def monthly_flash_results(df: pd.DataFrame) -> pd.DataFrame:
    """Realized flash P&L proxy: net notional flow signed by side, by month/asset class."""
    signed = np.where(df["side"] == "SELL", df["notional_usd"], -df["notional_usd"])
    df = df.assign(signed_notional=signed)
    flash = (
        df.groupby(["trade_month", "asset_class"], dropna=False)
        .agg(
            gross_volume_usd=("notional_usd", "sum"),
            net_flow_usd=("signed_notional", "sum"),
            trade_count=("event_id", "count"),
            avg_ticket_usd=("notional_usd", "mean"),
        )
        .reset_index()
        .sort_values(["asset_class", "trade_month"])
    )
    return flash


def build_budget(flash: pd.DataFrame) -> pd.DataFrame:
    """Naive planning proxy: each month's budget = trailing 3-month average
    *gross volume* per asset class, grown 2% (a stand-in for the bank's
    actual annual operating plan figures). Gross volume is used as the
    variance base rather than net flow, since net flow crosses zero for a
    balanced book and produces meaningless percentage swings."""
    out = []
    for ac, g in flash.groupby("asset_class"):
        g = g.sort_values("trade_month").reset_index(drop=True)
        budget = (
            g["gross_volume_usd"].rolling(3, min_periods=1).mean().shift(1).fillna(g["gross_volume_usd"].iloc[0])
            * 1.02
        )
        g = g.assign(budget_gross_volume_usd=budget)
        out.append(g)
    return pd.concat(out, ignore_index=True)


def variance_report(flash_with_budget: pd.DataFrame) -> pd.DataFrame:
    df = flash_with_budget.copy()
    df["variance_usd"] = df["gross_volume_usd"] - df["budget_gross_volume_usd"]
    df["variance_pct"] = (df["variance_usd"] / df["budget_gross_volume_usd"].replace(0, np.nan)).abs()
    df["variance_flag"] = df["variance_pct"] > 0.05  # >5% triggers Appian variance-justification workflow
    return df


def run(sqlite_path: str) -> dict:
    txns = load_transactions(sqlite_path)
    flash = monthly_flash_results(txns)
    with_budget = build_budget(flash)
    variance = variance_report(with_budget)

    variance.to_csv("outputs/flash_variance_report.csv", index=False)

    summary = {
        "months_covered": int(variance["trade_month"].nunique()),
        "asset_classes": int(variance["asset_class"].nunique()),
        "total_gross_volume_usd": float(flash["gross_volume_usd"].sum()),
        "months_flagged_over_5pct_variance": int(variance["variance_flag"].sum()),
        "pct_month_asset_rows_flagged": round(float(variance["variance_flag"].mean()), 4),
    }
    return summary


if __name__ == "__main__":
    print(run("data/warehouse.db"))
