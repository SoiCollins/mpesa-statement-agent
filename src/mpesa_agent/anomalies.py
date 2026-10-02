from __future__ import annotations

import re
from collections import defaultdict
from datetime import timedelta
from decimal import Decimal
from statistics import median

from mpesa_agent.models import Anomaly, Transaction


REVERSAL_TERMS = ("reversal", "reverse")
FAILURE_TERMS = ("fail", "reject", "declin", "unsuccess")


def _normalized_details(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.casefold())


def detect_anomalies(transactions: list[Transaction]) -> list[Anomaly]:
    anomalies: list[Anomaly] = []
    for index, transaction in enumerate(transactions):
        status = transaction.status.casefold()
        text = f"{transaction.details} {transaction.transaction_type}".casefold()
        if any(term in text for term in REVERSAL_TERMS) and any(
            term in status for term in FAILURE_TERMS
        ):
            anomalies.append(
                Anomaly(
                    transaction_reference=transaction.reference or f"row-{index + 1}",
                    anomaly_type="failed_reversal",
                    severity="high",
                    explanation="A reversal-related transaction has a failure status.",
                )
            )

    for index, transaction in enumerate(transactions):
        if transaction.amount >= 0:
            continue
        for earlier_index, earlier in enumerate(transactions[:index]):
            if earlier.amount >= 0 or abs(earlier.amount) != abs(transaction.amount):
                continue
            same_reference = bool(transaction.reference) and transaction.reference == earlier.reference
            same_charge = (
                _normalized_details(transaction.details) == _normalized_details(earlier.details)
                and abs(transaction.timestamp - earlier.timestamp) <= timedelta(minutes=30)
            )
            if same_reference or same_charge:
                anomalies.append(
                    Anomaly(
                        transaction_reference=transaction.reference or f"row-{index + 1}",
                        anomaly_type="duplicate_transaction",
                        severity="medium",
                        explanation="A matching outgoing charge appears again within 30 minutes.",
                    )
                )
                break

    expenses_by_category: dict[str, list[tuple[int, Decimal]]] = defaultdict(list)
    for index, transaction in enumerate(transactions):
        if transaction.amount < 0:
            expenses_by_category[transaction.category].append((index, abs(transaction.amount)))

    for category, expenses in expenses_by_category.items():
        if len(expenses) < 4:
            continue
        for index, amount in expenses:
            peer_amounts = [peer_amount for peer_index, peer_amount in expenses if peer_index != index]
            baseline = Decimal(str(median(peer_amounts)))
            if baseline > 0 and amount > baseline * Decimal("3"):
                transaction = transactions[index]
                anomalies.append(
                    Anomaly(
                        transaction_reference=transaction.reference or f"row-{index + 1}",
                        anomaly_type="unusual_spike",
                        severity="medium",
                        explanation=(
                            f"This {category} expense is more than 3x the median of its peers."
                        ),
                    )
                )
    return anomalies
