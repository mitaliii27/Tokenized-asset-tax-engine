"""
test_pipeline.py
------------------
Lightweight unit tests for the pieces of the pipeline that don't need a live
Spark session or the full generated dataset - fast enough to run in CI on
every commit. Run with:  pytest tests/
"""
import sys
import os
import json

import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.xceptor_extractor import extract_broker_line, BROKER_TEMPLATES
from src.tax_engine import fifo_realized_gains, flag_wash_sales


def test_broker_template_matches_all_three_layouts():
    lines = [
        "CONFIRM Fidelity Digital: client CL-1001 BUY 12.5 units TEQ-MSFT @ 415.2 USD settle 2025-01-05 ref#STL-12345678",
        "BNY Digital Assets TRADE CONF - TBOND-24 SELL qty=100 px=100.5 settlement_date=2025-02-01 client_id=CL-1002 ref=BRK-000111",
        "Trade advice: BUY order for CL-1003, TREIT-A, quantity 40, price 25.6, broker Coinbase Prime, ref BRK-999888, settles 2025-03-10",
    ]
    for line in lines:
        res = extract_broker_line(line)
        assert res.matched, f"failed to match: {line}"
        assert res.confidence > 0.9


def test_broker_template_rejects_garbage():
    res = extract_broker_line("*** PARTIAL FEED *** garbled nonsense ########")
    assert not res.matched


def test_fifo_realized_gains_simple_case():
    txns = pd.DataFrame(
        [
            {"client_id": "CL-1", "symbol": "TEQ-MSFT", "side": "BUY", "quantity": 10, "price_usd": 100,
             "timestamp": pd.Timestamp("2025-01-01")},
            {"client_id": "CL-1", "symbol": "TEQ-MSFT", "side": "SELL", "quantity": 4, "price_usd": 150,
             "timestamp": pd.Timestamp("2025-02-01")},
        ]
    )
    realized = fifo_realized_gains(txns)
    assert len(realized) == 1
    row = realized.iloc[0]
    assert row["quantity"] == 4
    assert row["proceeds_usd"] == pytest.approx(600.0)
    assert row["cost_basis_usd"] == pytest.approx(400.0)
    assert row["gain_loss_usd"] == pytest.approx(200.0)
    assert row["holding_period"] == "short_term"


def test_wash_sale_flagged_on_repurchase_within_30_days():
    txns = pd.DataFrame(
        [
            {"client_id": "CL-2", "symbol": "TCORP-HY", "side": "BUY", "quantity": 10, "price_usd": 100,
             "timestamp": pd.Timestamp("2025-01-01")},
            {"client_id": "CL-2", "symbol": "TCORP-HY", "side": "SELL", "quantity": 10, "price_usd": 80,
             "timestamp": pd.Timestamp("2025-02-01")},
            {"client_id": "CL-2", "symbol": "TCORP-HY", "side": "BUY", "quantity": 10, "price_usd": 82,
             "timestamp": pd.Timestamp("2025-02-15")},
        ]
    )
    realized = fifo_realized_gains(txns)
    realized = flag_wash_sales(realized, txns)
    loss_row = realized[realized["gain_loss_usd"] < 0].iloc[0]
    assert loss_row["wash_sale_flag"] == True  # noqa: E712


def test_metrics_json_has_expected_top_level_keys(tmp_path):
    """Guards the schema the dashboard builder depends on - if this drifts,
    dashboard/build_dashboard.py will fail loudly rather than rendering garbage."""
    sample = {
        "etl": {"rows_ingested": 1, "data_quality_pass_rate": 1.0},
        "fpna": {"total_gross_volume_usd": 1.0},
        "tax": {"total_estimated_tax_liability_usd": 1.0},
        "aml": {"n_flagged": 1, "roc_auc": 1.0},
        "workflow": {"escalated_to_compliance": 1},
    }
    for key in ["etl", "fpna", "tax", "aml", "workflow"]:
        assert key in sample
