"""
xceptor_extractor.py
---------------------
NOTE ON SCOPE: Xceptor is a licensed, proprietary intelligent-data-capture
platform. This module is an open-source stand-in that reproduces the *pattern*
Xceptor is used for in production - template-based extraction of structured
fields from messy, semi-structured, or free-text sources - so the pipeline is
fully runnable without an enterprise license. If you have access to real
Xceptor, swap this module for an Xceptor workflow that emits the same schema.

What it does here:
  1. Parses the JSON memo blob embedded in each blockchain ledger row.
  2. Parses free-text broker confirmation lines using a small library of
     regex "templates" (the same idea as Xceptor's template matching -
     try each known layout until one matches with high confidence).
  3. Emits both sources into one normalized schema so downstream ETL doesn't
     care where a row originated.
"""
import json
import re
from dataclasses import dataclass, asdict
from typing import Optional

import pandas as pd

NORMALIZED_COLUMNS = [
    "source", "event_id", "timestamp", "symbol", "side", "quantity", "price_usd",
    "client_id", "counterparty", "chain_or_broker", "settlement_ref", "extraction_confidence",
]

BROKER_TEMPLATES = [
    re.compile(
        r"CONFIRM (?P<broker>[\w\s]+): client (?P<client>CL-\d+) (?P<side>BUY|SELL) "
        r"(?P<qty>[\d.]+) units (?P<sym>[\w-]+) @ (?P<price>[\d.]+) USD settle (?P<settle>[\d-]+) ref#(?P<ref>[\w-]+)"
    ),
    re.compile(
        r"(?P<broker>[\w\s]+) TRADE CONF - (?P<sym>[\w-]+) (?P<side>BUY|SELL) qty=(?P<qty>[\d.]+) "
        r"px=(?P<price>[\d.]+) settlement_date=(?P<settle>[\d-]+) client_id=(?P<client>CL-\d+) ref=(?P<ref>[\w-]+)"
    ),
    re.compile(
        r"Trade advice: (?P<side>BUY|SELL) order for (?P<client>CL-\d+), (?P<sym>[\w-]+), quantity (?P<qty>[\d.]+), "
        r"price (?P<price>[\d.]+), broker (?P<broker>[\w\s]+), ref (?P<ref>[\w-]+), settles (?P<settle>[\d-]+)"
    ),
]


@dataclass
class ExtractionResult:
    matched: bool
    confidence: float
    fields: dict


def extract_broker_line(line: str) -> ExtractionResult:
    """Template-match a single free-text broker confirmation line."""
    for tmpl in BROKER_TEMPLATES:
        m = tmpl.match(line.strip())
        if m:
            g = m.groupdict()
            return ExtractionResult(
                matched=True,
                confidence=0.97,  # exact template hit
                fields={
                    "side": g["side"],
                    "quantity": float(g["qty"]),
                    "symbol": g["sym"],
                    "price_usd": float(g["price"]),
                    "client_id": g["client"],
                    "chain_or_broker": g["broker"].strip(),
                    "settlement_ref": g["ref"],
                    "timestamp": g["settle"],
                },
            )
    return ExtractionResult(matched=False, confidence=0.0, fields={})


def extract_broker_file(path: str) -> pd.DataFrame:
    records = []
    unmatched = 0
    with open(path) as f:
        for i, line in enumerate(f):
            if not line.strip():
                continue
            res = extract_broker_line(line)
            if not res.matched:
                unmatched += 1
                continue
            f_ = res.fields
            records.append(
                {
                    "source": "broker_statement",
                    "event_id": f"BRK{i:08d}",
                    "timestamp": f_["timestamp"],
                    "symbol": f_["symbol"],
                    "side": f_["side"],
                    "quantity": f_["quantity"],
                    "price_usd": f_["price_usd"],
                    "client_id": f_["client_id"],
                    "counterparty": None,
                    "chain_or_broker": f_["chain_or_broker"],
                    "settlement_ref": f_["settlement_ref"],
                    "extraction_confidence": res.confidence,
                }
            )
    df = pd.DataFrame(records, columns=NORMALIZED_COLUMNS)
    print(f"[xceptor_extractor] broker file: matched {len(df)} / {len(df)+unmatched} lines "
          f"({unmatched} sent to exception queue for manual template review)")
    return df


def extract_ledger_file(path: str) -> pd.DataFrame:
    raw = pd.read_csv(path)
    out = []
    for _, r in raw.iterrows():
        memo = json.loads(r["memo_json"])
        side = "BUY" if r["direction"] in ("BUY", "TRANSFER_IN") else "SELL"
        out.append(
            {
                "source": "blockchain_ledger",
                "event_id": r["event_id"],
                "timestamp": r["timestamp"],
                "symbol": r["symbol"],
                "side": side,
                "quantity": r["quantity"],
                "price_usd": r["price_usd"],
                "client_id": None,
                "counterparty": memo["wallet_from"] if side == "BUY" else memo["wallet_to"],
                "chain_or_broker": memo["chain"],
                "settlement_ref": memo["settlement_ref"],
                "extraction_confidence": 1.0,  # structured JSON, no template ambiguity
            }
        )
    df = pd.DataFrame(out, columns=NORMALIZED_COLUMNS)
    df["_seeded_anomaly"] = raw["seeded_anomaly"].values  # carried through for model validation only
    return df


def run(ledger_path: str, broker_path: str) -> pd.DataFrame:
    ledger_df = extract_ledger_file(ledger_path)
    broker_df = extract_broker_file(broker_path)
    combined = pd.concat([ledger_df, broker_df], ignore_index=True)
    print(f"[xceptor_extractor] normalized {len(combined)} total records from 2 heterogeneous sources")
    return combined


if __name__ == "__main__":
    df = run("data/blockchain_ledger_raw.csv", "data/broker_statements_raw.txt")
    df.to_parquet("data/normalized_transactions.parquet", index=False)
    print(df.head())
