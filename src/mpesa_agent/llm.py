from __future__ import annotations

import json
import os
from calendar import month_name
from collections import Counter
from decimal import Decimal
from typing import Protocol

from mpesa_agent.models import Anomaly, Transaction


class AnswerClient(Protocol):
    def answer(
        self, question: str, transactions: list[Transaction], anomalies: list[Anomaly]
    ) -> str: ...


def _money(value: Decimal) -> str:
    return f"KES {value:,.2f}"


def _month_for(question: str) -> int | None:
    lowered = question.casefold()
    for month in range(1, 13):
        if month_name[month].casefold() in lowered:
            return month
    return None


def _category_for(question: str) -> str | None:
    lowered = question.casefold()
    aliases = {
        "suppliers": ("supplier", "wholesale", "stock"),
        "utilities": ("utilities", "electricity", "water bill", "internet"),
        "fees": ("fee", "fees", "charges"),
        "payroll": ("payroll", "salary", "salaries", "wages"),
        "transport": ("transport", "fuel", "fare", "delivery"),
        "sales": ("sales", "income", "received", "revenue"),
    }
    for category, terms in aliases.items():
        if any(term in lowered for term in terms):
            return category
    return None


class FakeLLMClient:
    """Deterministic, network-free answer client for development and evaluations."""

    def answer(
        self, question: str, transactions: list[Transaction], anomalies: list[Anomaly]
    ) -> str:
        lowered = question.casefold()
        if any(term in lowered for term in ("anomal", "duplicate", "spike", "reversal")):
            if not anomalies:
                return "No anomalies were flagged by the current rules."
            counts = Counter(anomaly.anomaly_type for anomaly in anomalies)
            labels = {
                "duplicate_transaction": "possible duplicate",
                "unusual_spike": "unusual spending spike",
                "failed_reversal": "failed reversal",
            }
            details = ", ".join(
                f"{count} {labels[kind]}{'s' if count != 1 else ''}"
                for kind, count in sorted(counts.items())
            )
            return f"There are {len(anomalies)} flagged anomalies: {details}."

        month = _month_for(question)
        category = _category_for(question)
        if category == "sales" or any(
            term in lowered for term in ("income", "revenue", "received", "earn")
        ):
            filtered = [transaction for transaction in transactions if transaction.amount > 0]
            metric = "income"
            total = sum((transaction.amount for transaction in filtered), Decimal("0"))
        else:
            filtered = [transaction for transaction in transactions if transaction.amount < 0]
            metric = "spend"
            total = sum((abs(transaction.amount) for transaction in filtered), Decimal("0"))

        if month is not None:
            filtered = [
                transaction for transaction in filtered if transaction.timestamp.month == month
            ]
            total = sum(
                (
                    transaction.amount if metric == "income" else abs(transaction.amount)
                    for transaction in filtered
                ),
                Decimal("0"),
            )
        if category is not None:
            filtered = [transaction for transaction in filtered if transaction.category == category]
            total = sum(
                (
                    transaction.amount if metric == "income" else abs(transaction.amount)
                    for transaction in filtered
                ),
                Decimal("0"),
            )

        category_label = f" on {category}" if category else ""
        month_label = f" in {month_name[month]}" if month else ""
        subject = "earned" if metric == "income" else "spent"
        return (
            f"{_money(total)} {subject}{category_label}{month_label} across "
            f"{len(filtered)} transaction{'s' if len(filtered) != 1 else ''}."
        )


class OpenAIAnswerClient:
    def __init__(self, api_key: str, model: str) -> None:
        try:
            from openai import OpenAI
        except ImportError as error:
            raise RuntimeError(
                'Install the optional provider with `pip install -e ".[openai]"`.'
            ) from error
        self.client = OpenAI(api_key=api_key)
        self.model = model

    def answer(
        self, question: str, transactions: list[Transaction], anomalies: list[Anomaly]
    ) -> str:
        statement_context = {
            "transactions": [
                {
                    "timestamp": transaction.timestamp.isoformat(),
                    "details": transaction.details,
                    "amount_kes": str(transaction.amount),
                    "category": transaction.category,
                    "status": transaction.status,
                    "reference": transaction.reference,
                }
                for transaction in transactions
            ],
            "anomalies": [anomaly.model_dump() for anomaly in anomalies],
        }
        response = self.client.responses.create(
            model=self.model,
            instructions=(
                "Answer using only the provided statement data. Keep the answer concise, "
                "use KES for money, and state when the data does not support an answer."
            ),
            input=f"Question: {question}\nStatement data: {json.dumps(statement_context)}",
        )
        return response.output_text.strip()


def create_answer_client() -> AnswerClient:
    provider = os.getenv("APP_LLM_PROVIDER", "fake").strip().casefold()
    if provider == "fake":
        return FakeLLMClient()
    if provider == "openai":
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is required when APP_LLM_PROVIDER=openai.")
        return OpenAIAnswerClient(api_key=api_key, model=os.getenv("OPENAI_MODEL", "gpt-5.5"))
    raise RuntimeError("APP_LLM_PROVIDER must be either 'fake' or 'openai'.")
