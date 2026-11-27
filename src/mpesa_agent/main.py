from __future__ import annotations

from decimal import Decimal

from fastapi import FastAPI, File, HTTPException, UploadFile

from mpesa_agent.graph import build_graph
from mpesa_agent.llm import AnswerClient, create_answer_client
from mpesa_agent.models import (
    Anomaly,
    QuestionRequest,
    QuestionResponse,
    StatementAnalysis,
    StatementUpload,
    Transaction,
)
from mpesa_agent.parser import StatementParseError
from mpesa_agent.repository import StatementRepository

MAX_UPLOAD_BYTES = 5 * 1024 * 1024


def _money(value: Decimal) -> str:
    return f"KES {value:,.2f}"


def _analysis_from_state(statement_id: str, state: dict[str, object]) -> StatementAnalysis:
    transactions = [Transaction.model_validate(item) for item in state["transactions"]]
    anomalies = [Anomaly.model_validate(item) for item in state.get("anomalies", [])]
    income_total = sum(
        (transaction.amount for transaction in transactions if transaction.amount > 0),
        Decimal("0"),
    )
    spend_total = sum(
        (abs(transaction.amount) for transaction in transactions if transaction.amount < 0),
        Decimal("0"),
    )
    category_spend: dict[str, Decimal] = {}
    for transaction in transactions:
        if transaction.amount < 0:
            category_spend[transaction.category] = category_spend.get(
                transaction.category, Decimal("0")
            ) + abs(transaction.amount)
    summary = (
        f"{len(transactions)} transactions; {_money(income_total)} income; "
        f"{_money(spend_total)} spend; {len(anomalies)} anomalies flagged."
    )
    return StatementAnalysis(
        statement_id=statement_id,
        transaction_count=len(transactions),
        income_total=income_total,
        spend_total=spend_total,
        category_spend=category_spend,
        transactions=transactions,
        anomalies=anomalies,
        summary=summary,
    )


def create_app(
    repository: StatementRepository | None = None,
    answer_client: AnswerClient | None = None,
) -> FastAPI:
    statements = repository or StatementRepository()
    client = answer_client or create_answer_client()
    graph = build_graph(client)
    app = FastAPI(
        title="M-Pesa Statement Agent",
        version="0.1.0",
        description="Analyze synthetic mobile-money statement CSVs and ask grounded questions.",
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/statements/upload", response_model=StatementUpload, status_code=201)
    async def upload_statement(file: UploadFile = File(...)) -> StatementUpload:
        filename = file.filename or ""
        if not filename.casefold().endswith(".csv"):
            raise HTTPException(status_code=415, detail="Upload a CSV statement.")
        content = await file.read(MAX_UPLOAD_BYTES + 1)
        if len(content) > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="CSV upload must be 5 MB or smaller.")
        try:
            raw_csv = content.decode("utf-8-sig")
        except UnicodeDecodeError as error:
            raise HTTPException(status_code=400, detail="CSV must be UTF-8 encoded.") from error
        if not raw_csv.strip():
            raise HTTPException(status_code=400, detail="CSV file is empty.")
        statement = statements.add(filename, raw_csv)
        return StatementUpload(statement_id=statement.statement_id, filename=filename)

    @app.post("/statements/{statement_id}/analyze", response_model=StatementAnalysis)
    def analyze_statement(statement_id: str) -> StatementAnalysis:
        statement = statements.get(statement_id)
        if statement is None:
            raise HTTPException(status_code=404, detail="Statement not found.")
        try:
            state = graph.invoke({"raw_csv": statement.raw_csv})
        except StatementParseError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        return _analysis_from_state(statement_id, state)

    @app.post("/statements/{statement_id}/ask", response_model=QuestionResponse)
    def ask_question(statement_id: str, payload: QuestionRequest) -> QuestionResponse:
        statement = statements.get(statement_id)
        if statement is None:
            raise HTTPException(status_code=404, detail="Statement not found.")
        try:
            state = graph.invoke({"raw_csv": statement.raw_csv, "question": payload.question})
        except StatementParseError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        return QuestionResponse(statement_id=statement_id, answer=str(state["answer"]))

    return app


app = create_app()
