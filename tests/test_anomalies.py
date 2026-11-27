from __future__ import annotations

from pathlib import Path

from mpesa_agent.anomalies import detect_anomalies
from mpesa_agent.categorization import categorize
from mpesa_agent.models import Transaction
from mpesa_agent.parser import parse_statement_csv

ROOT = Path(__file__).resolve().parents[1]


def test_sample_flags_duplicate_spike_and_failed_reversal() -> None:
    rows = parse_statement_csv((ROOT / "data/samples/synthetic_statement.csv").read_text())
    transactions = [categorize(row) for row in rows]
    anomaly_types = {anomaly.anomaly_type for anomaly in detect_anomalies(transactions)}
    assert anomaly_types == {"duplicate_transaction", "unusual_spike", "failed_reversal"}


def test_failed_reversal_requires_failed_status() -> None:
    transaction = Transaction(
        timestamp="2025-09-01T10:00:00+03:00",
        details="Successful reversal",
        amount="100",
        status="completed",
        transaction_type="reversal",
    )
    assert detect_anomalies([transaction]) == []
