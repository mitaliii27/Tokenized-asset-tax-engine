"""
tax_engine.py
--------------
Digital-asset tax classification and 1099-DA *staging* logic.

IMPORTANT SCOPE NOTE: this produces a staging report that mirrors the fields
a broker needs to prepare for Form 1099-DA (Digital Asset Proceeds from
Broker Transactions) - it is a data-engineering/demo artifact, not
tax-filing software, and it does not implement every IRS edge case (e.g.
full wash-sale chaining across accounts, gift/inherited basis rules). A real
implementation would sit behind a tax engine of record and be signed off by
tax technical.

What it computes per client/symbol lot:
  - realized gain/loss using FIFO cost basis
  - holding period classification (short-term <= 365 days, long-term > 365)
  - a simple same-security wash-sale flag (loss disallowed if a purchase of
    the same symbol occurred within 30 days before/after the loss sale)
  - an aggregated 1099-DA staging table + a jurisdiction tax liability estimate
"""
import sqlite3
from collections import deque, defaultdict

import pandas as pd

# flat estimated blended tax rate by holding period - a placeholder for the
# bank's real jurisdiction/withholding tax tables
ESTIMATED_TAX_RATE = {"short_term": 0.32, "long_term": 0.18}


def load_client_transactions(sqlite_path: str) -> pd.DataFrame:
    conn = sqlite3.connect(sqlite_path)
    df = pd.read_sql(
        "SELECT * FROM transactions WHERE client_id IS NOT NULL", conn
    )  # only broker-side flows carry a client_id; on-chain custody flows are not client-taxable events
    conn.close()
    df["timestamp"] = pd.to_datetime(df["timestamp"], format="mixed", errors="coerce")
    df = df.dropna(subset=["timestamp"]).sort_values("timestamp")
    return df


def fifo_realized_gains(df: pd.DataFrame) -> pd.DataFrame:
    """FIFO lot matching per (client_id, symbol)."""
    lots = defaultdict(deque)  # (client, symbol) -> deque of (qty, cost_basis_per_unit, open_date)
    realized = []

    for _, row in df.iterrows():
        key = (row["client_id"], row["symbol"])
        if row["side"] == "BUY":
            lots[key].append([row["quantity"], row["price_usd"], row["timestamp"]])
        else:  # SELL - consume FIFO lots
            qty_to_sell = row["quantity"]
            while qty_to_sell > 1e-9 and lots[key]:
                lot = lots[key][0]
                lot_qty, cost_basis, open_date = lot
                used = min(qty_to_sell, lot_qty)
                proceeds = used * row["price_usd"]
                basis = used * cost_basis
                holding_days = (row["timestamp"] - open_date).days
                realized.append(
                    {
                        "client_id": row["client_id"],
                        "symbol": row["symbol"],
                        "sell_date": row["timestamp"],
                        "buy_date": open_date,
                        "quantity": used,
                        "proceeds_usd": proceeds,
                        "cost_basis_usd": basis,
                        "gain_loss_usd": proceeds - basis,
                        "holding_period": "long_term" if holding_days > 365 else "short_term",
                        "holding_days": holding_days,
                    }
                )
                lot_qty -= used
                qty_to_sell -= used
                if lot_qty <= 1e-9:
                    lots[key].popleft()
                else:
                    lot[0] = lot_qty
    return pd.DataFrame(realized)


def flag_wash_sales(realized: pd.DataFrame, all_txns: pd.DataFrame) -> pd.DataFrame:
    """Disallow losses where the same symbol was repurchased within 30 days
    before/after the loss-triggering sale (simplified same-account rule)."""
    buys = all_txns[all_txns["side"] == "BUY"][["client_id", "symbol", "timestamp"]]
    realized = realized.copy()
    realized["wash_sale_flag"] = False
    for idx, r in realized[realized["gain_loss_usd"] < 0].iterrows():
        window_buys = buys[
            (buys["client_id"] == r["client_id"])
            & (buys["symbol"] == r["symbol"])
            & (buys["timestamp"] >= r["sell_date"] - pd.Timedelta(days=30))
            & (buys["timestamp"] <= r["sell_date"] + pd.Timedelta(days=30))
        ]
        if len(window_buys) > 0:
            realized.loc[idx, "wash_sale_flag"] = True
    return realized


def build_1099da_staging(realized: pd.DataFrame) -> pd.DataFrame:
    realized = realized.copy()
    realized["disallowed_loss_usd"] = 0.0
    mask = realized["wash_sale_flag"] & (realized["gain_loss_usd"] < 0)
    realized.loc[mask, "disallowed_loss_usd"] = -realized.loc[mask, "gain_loss_usd"]
    realized.loc[mask, "gain_loss_usd"] = 0.0  # disallowed loss deferred, not deducted this period

    realized["est_tax_rate"] = realized["holding_period"].map(ESTIMATED_TAX_RATE)
    realized["est_tax_liability_usd"] = (realized["gain_loss_usd"].clip(lower=0) * realized["est_tax_rate"])

    staging = (
        realized.groupby(["client_id", "symbol", "holding_period"])
        .agg(
            total_proceeds_usd=("proceeds_usd", "sum"),
            total_cost_basis_usd=("cost_basis_usd", "sum"),
            net_gain_loss_usd=("gain_loss_usd", "sum"),
            disallowed_wash_sale_loss_usd=("disallowed_loss_usd", "sum"),
            est_tax_liability_usd=("est_tax_liability_usd", "sum"),
            lot_count=("quantity", "count"),
        )
        .reset_index()
    )
    return staging


def run(sqlite_path: str) -> dict:
    txns = load_client_transactions(sqlite_path)
    realized = fifo_realized_gains(txns)
    realized = flag_wash_sales(realized, txns)
    staging = build_1099da_staging(realized)

    staging.to_csv("outputs/form_1099da_staging.csv", index=False)
    realized.to_csv("outputs/realized_lots_detail.csv", index=False)

    summary = {
        "clients_processed": int(staging["client_id"].nunique()),
        "realized_lots": int(len(realized)),
        "wash_sale_flagged_lots": int(realized["wash_sale_flag"].sum()),
        "total_net_gain_loss_usd": float(staging["net_gain_loss_usd"].sum()),
        "total_estimated_tax_liability_usd": float(staging["est_tax_liability_usd"].sum()),
        "total_disallowed_wash_sale_loss_usd": float(staging["disallowed_wash_sale_loss_usd"].sum()),
    }
    return summary


if __name__ == "__main__":
    print(run("data/warehouse.db"))
