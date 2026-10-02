from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from mpesa_agent.llm import FakeLLMClient
from mpesa_agent.main import create_app
from mpesa_agent.repository import StatementRepository


ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "data" / "samples" / "synthetic_statement.csv"


def test_upload_analyze_and_ask() -> None:
    app = create_app(StatementRepository(), FakeLLMClient())
    client = TestClient(app)
    response = client.post(
        "/statements/upload",
        files={"file": ("synthetic_statement.csv", SAMPLE.read_bytes(), "text/csv")},
    )
    assert response.status_code == 201
    statement_id = response.json()["statement_id"]

    analysis = client.post(f"/statements/{statement_id}/analyze")
    assert analysis.status_code == 200
    assert analysis.json()["transaction_count"] == 12
    assert analysis.json()["category_spend"]["suppliers"] == "113000.00"
    assert len(analysis.json()["anomalies"]) == 3

    answer = client.post(
        f"/statements/{statement_id}/ask",
        json={"question": "What did I spend on suppliers in September?"},
    )
    assert answer.status_code == 200
    assert "KES 113,000.00" in answer.json()["answer"]


def test_unknown_statement_returns_404() -> None:
    client = TestClient(create_app(StatementRepository(), FakeLLMClient()))
    response = client.post("/statements/missing/analyze")
    assert response.status_code == 404


def test_upload_rejects_non_csv() -> None:
    client = TestClient(create_app(StatementRepository(), FakeLLMClient()))
    response = client.post(
        "/statements/upload", files={"file": ("statement.pdf", b"not a csv", "application/pdf")}
    )
    assert response.status_code == 415


def test_invalid_csv_is_reported_during_analysis() -> None:
    client = TestClient(create_app(StatementRepository(), FakeLLMClient()))
    uploaded = client.post(
        "/statements/upload",
        files={"file": ("bad.csv", b"timestamp,details\n2025-09-01,Sale\n", "text/csv")},
    )
    response = client.post(f"/statements/{uploaded.json()['statement_id']}/analyze")
    assert response.status_code == 422
    assert "Missing required CSV columns" in response.json()["detail"]
