from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Category = Literal[
    "suppliers",
    "utilities",
    "fees",
    "payroll",
    "transport",
    "sales",
    "other",
]


class Transaction(BaseModel):
    model_config = ConfigDict(extra="ignore")

    timestamp: datetime
    details: str = Field(min_length=1, max_length=500)
    amount: Decimal
    reference: str = Field(default="", max_length=120)
    status: str = Field(default="completed", max_length=80)
    transaction_type: str = Field(default="", max_length=120)
    category: Category = "other"


class Anomaly(BaseModel):
    transaction_reference: str
    anomaly_type: Literal["duplicate_transaction", "unusual_spike", "failed_reversal"]
    severity: Literal["low", "medium", "high"]
    explanation: str


class StatementUpload(BaseModel):
    statement_id: str
    filename: str
    status: Literal["uploaded"] = "uploaded"


class StatementAnalysis(BaseModel):
    statement_id: str
    transaction_count: int
    income_total: Decimal
    spend_total: Decimal
    category_spend: dict[str, Decimal]
    transactions: list[Transaction]
    anomalies: list[Anomaly]
    summary: str


class QuestionRequest(BaseModel):
    question: str = Field(min_length=3, max_length=1000)


class QuestionResponse(BaseModel):
    statement_id: str
    answer: str
