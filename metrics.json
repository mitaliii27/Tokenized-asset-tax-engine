"""
generate_data.py
-----------------
Synthesizes a realistic-but-fake dataset of tokenized-asset (digital securities)
trading activity across a mix of institutional wallets and broker feeds.

Two raw sources are produced, mirroring how this data actually arrives in a bank:

1. blockchain_ledger_raw.csv   - on-chain transfer events (semi-structured JSON
   memo blob per row, the way an indexer / node export typically looks)
2. broker_statements_raw.txt   - free-text broker confirmation lines (the
   "unstructured" source Xceptor-style tools are built to parse)

Both feed src/xceptor_extractor.py, which is where the real parsing logic lives.

Usage:
    python data/generate_data.py --rows 50000 --seed 42
"""
import argparse
import json
import random
from datetime import datetime, timedelta

from faker import Faker

fake = Faker()

TOKENS = [
    ("TBOND-24", "tokenized_treasury", 100.00),
    ("TREIT-A", "tokenized_reit", 25.50),
    ("TEQ-MSFT", "tokenized_equity", 415.20),
    ("TEQ-NVDA", "tokenized_equity", 118.75),
    ("TCORP-HY", "tokenized_corp_bond", 98.10),
    ("TCASH-USD", "tokenized_money_market", 1.00),
]

BROKERS = ["Fidelity Digital", "BNY Digital Assets", "Coinbase Prime", "Anchorage Custody", "State Street Digital"]
WALLET_PREFIX = "0x"
CLIENT_POOL = [1000 + i for i in range(250)]  # 250 recurring institutional clients


def rand_wallet():
    return WALLET_PREFIX + "".join(random.choices("0123456789abcdef", k=40))


def rand_price_walk(base_price, days):
    """Simple geometric walk so month-over-month variance looks organic."""
    price = base_price
    path = []
    for _ in range(days):
        price *= 1 + random.gauss(0, 0.015)
        path.append(round(max(price, 0.01), 4))
    return path


def generate_blockchain_ledger(n_rows, start_date, seed):
    random.seed(seed)
    rows = []
    price_paths = {sym: rand_price_walk(px, 400) for sym, _, px in TOKENS}
    for i in range(n_rows):
        sym, asset_class, _ = random.choice(TOKENS)
        day_offset = random.randint(0, 399)
        ts = start_date + timedelta(days=day_offset, seconds=random.randint(0, 86399))
        qty = round(random.lognormvariate(2.2, 1.1), 4)
        price = price_paths[sym][day_offset]
        direction = random.choices(["BUY", "SELL", "TRANSFER_IN", "TRANSFER_OUT"], weights=[35, 35, 15, 15])[0]

        # inject a small, controlled fraction of anomalous trades (used later
        # to validate the Isolation Forest model against a known ground truth)
        is_seeded_anomaly = random.random() < 0.012
        if is_seeded_anomaly:
            qty *= random.choice([18, 25, 40])
            price *= random.choice([0.55, 1.65])

        memo = {
            "wallet_from": rand_wallet() if direction in ("SELL", "TRANSFER_OUT") else "CUSTODY_OMNIBUS",
            "wallet_to": rand_wallet() if direction in ("BUY", "TRANSFER_IN") else "CUSTODY_OMNIBUS",
            "chain": random.choice(["Ethereum-L1", "Base", "Avalanche-Subnet"]),
            "gas_fee_usd": round(random.uniform(0.4, 18.0), 2),
            "settlement_ref": fake.bothify(text="STL-########"),
        }

        # ~0.8% upstream data-quality defects (nulled/negative fields from
        # feed timeouts) - these are what the ETL quality gate exists to catch
        dirty_roll = random.random()
        if dirty_roll < 0.004:
            qty = -abs(qty)
        elif dirty_roll < 0.008:
            price = 0.0

        rows.append(
            {
                "event_id": f"EVT{i:08d}",
                "timestamp": ts.isoformat(),
                "symbol": sym,
                "asset_class": asset_class,
                "direction": direction,
                "quantity": qty,
                "price_usd": price,
                "memo_json": json.dumps(memo),
                "seeded_anomaly": int(is_seeded_anomaly),  # kept only for model validation, dropped before ETL load
            }
        )
    return rows


def generate_broker_statements(n_rows, start_date, seed):
    """Free-text confirmation lines - the messy, human-written source."""
    random.seed(seed + 1)
    lines = []
    templates = [
        "CONFIRM {broker}: client {client} {side} {qty} units {sym} @ {price} USD settle {settle} ref#{ref}",
        "{broker} TRADE CONF - {sym} {side} qty={qty} px={price} settlement_date={settle} client_id={client} ref={ref}",
        "Trade advice: {side} order for {client}, {sym}, quantity {qty}, price {price}, broker {broker}, ref {ref}, settles {settle}",
    ]
    for i in range(n_rows):
        # ~2% of real-world broker feeds arrive truncated / malformed (dropped
        # connections, legacy fax-to-text conversion, etc.) - Xceptor-style
        # tools route these to a manual exception queue instead of failing silently.
        if random.random() < 0.02:
            lines.append(f"*** PARTIAL FEED *** {fake.bothify(text='??? corrupted segment ########')}")
            continue
        sym, _, _ = random.choice(TOKENS)
        day_offset = random.randint(0, 399)
        settle = (start_date + timedelta(days=day_offset + 2)).date().isoformat()
        t = random.choice(templates)
        lines.append(
            t.format(
                broker=random.choice(BROKERS),
                client=f"CL-{random.choice(CLIENT_POOL)}",
                side=random.choice(["BUY", "SELL"]),
                qty=round(random.lognormvariate(2.0, 1.0), 2),
                sym=sym,
                price=round(random.uniform(0.9, 450), 2),
                settle=settle,
                ref=fake.bothify(text="BRK-######"),
            )
        )
    return lines


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", type=int, default=50000)
    ap.add_argument("--broker-rows", type=int, default=8000)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out-dir", default=".")
    args = ap.parse_args()

    start_date = datetime(2025, 1, 1)

    ledger_rows = generate_blockchain_ledger(args.rows, start_date, args.seed)
    import csv

    ledger_path = f"{args.out_dir}/blockchain_ledger_raw.csv"
    with open(ledger_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(ledger_rows[0].keys()))
        w.writeheader()
        w.writerows(ledger_rows)

    broker_lines = generate_broker_statements(args.broker_rows, start_date, args.seed)
    broker_path = f"{args.out_dir}/broker_statements_raw.txt"
    with open(broker_path, "w") as f:
        f.write("\n".join(broker_lines))

    n_anom = sum(r["seeded_anomaly"] for r in ledger_rows)
    print(f"Wrote {len(ledger_rows)} ledger events -> {ledger_path}")
    print(f"Wrote {len(broker_lines)} broker confirmation lines -> {broker_path}")
    print(f"Seeded {n_anom} ground-truth anomalies ({n_anom/len(ledger_rows):.2%}) for model validation")


if __name__ == "__main__":
    main()
