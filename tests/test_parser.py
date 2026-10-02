from __future__ import annotations

import pytest

from mpesa_agent.parser import StatementParseError, parse_statement_csv


def test_parses_iso_and_common_day_first_dates() -> None:
    csv_text = (
        "timestamp,details,amount,reference,status\n"
        "2025-09-01T08:15:00+03:00,Customer payment,48000.00,TX1,completed\n"
        '03/09/2025 10:20,Wholesale supplier,"(12,500.00)",TX2,completed\n'
    )
    transactions = parse_statement_csv(csv_text)
    assert transactions[0].timestamp.isoformat() == "2025-09-01T08:15:00+03:00"
    assert str(transactions[1].amount) == "-12500.00"


def test_rejects_missing_required_columns() -> None:
    with pytest.raises(StatementParseError, match="Missing required CSV columns: amount"):
        parse_statement_csv("timestamp,details\n2025-09-01,Sale\n")


def test_reports_invalid_row_number() -> None:
    with pytest.raises(StatementParseError, match="CSV row 2"):
        parse_statement_csv("timestamp,details,amount\nnot-a-date,Sale,10\n")
