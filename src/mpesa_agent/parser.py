from __future__ import annotations

import csv
import io
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation

from pydantic import ValidationError

from mpesa_agent.models import Transaction


class StatementParseError(ValueError):
    """Raised when a statement cannot be mapped to the supported CSV schema."""


REQUIRED_COLUMNS = {"timestamp", "details", "amount"}


def _parse_timestamp(value: str) -> datetime:
    candidate = value.strip()
    formats = ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M", "%d/%m/%Y")
    try:
        parsed = datetime.fromisoformat(candidate.replace("Z", "+00:00"))
    except ValueError:
        for pattern in formats:
            try:
                parsed = datetime.strptime(candidate, pattern)
                break
            except ValueError:
                continue
        else:
            raise ValueError(f"unsupported timestamp: {candidate}") from None
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed


def _parse_amount(value: str) -> Decimal:
    normalized = value.strip().upper().replace("KES", "").replace(",", "").strip()
    if normalized.startswith("(") and normalized.endswith(")"):
        normalized = f"-{normalized[1:-1]}"
    try:
        return Decimal(normalized)
    except InvalidOperation as error:
        raise ValueError(f"invalid amount: {value}") from error


def parse_statement_csv(contents: str) -> list[Transaction]:
    reader = csv.DictReader(io.StringIO(contents))
    if not reader.fieldnames:
        raise StatementParseError("The CSV file is empty or has no header row.")

    normalized_headers = {header.strip().lower(): header for header in reader.fieldnames if header}
    missing = REQUIRED_COLUMNS - normalized_headers.keys()
    if missing:
        columns = ", ".join(sorted(missing))
        raise StatementParseError(f"Missing required CSV columns: {columns}.")

    transactions: list[Transaction] = []
    for row_number, row in enumerate(reader, start=2):
        if not row or not any(value and value.strip() for value in row.values()):
            continue
        normalized = {
            key.strip().lower(): (value or "").strip()
            for key, value in row.items()
            if key is not None
        }
        try:
            transaction = Transaction.model_validate(
                {
                    "timestamp": _parse_timestamp(normalized.get("timestamp", "")),
                    "details": normalized.get("details", ""),
                    "amount": _parse_amount(normalized.get("amount", "")),
                    "reference": normalized.get("reference", ""),
                    "status": normalized.get("status", "completed") or "completed",
                    "transaction_type": normalized.get("transaction_type", ""),
                }
            )
        except (ValueError, ValidationError) as error:
            raise StatementParseError(f"Invalid data on CSV row {row_number}: {error}") from error
        transactions.append(transaction)

    if not transactions:
        raise StatementParseError("The CSV contains a header but no transactions.")
    return transactions
