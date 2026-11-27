from __future__ import annotations

from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from mpesa_agent.anomalies import detect_anomalies
from mpesa_agent.categorization import categorize
from mpesa_agent.llm import AnswerClient, create_answer_client
from mpesa_agent.models import Anomaly, Transaction
from mpesa_agent.parser import parse_statement_csv


class AgentState(TypedDict, total=False):
    raw_csv: str
    question: str
    transactions: list[dict[str, object]]
    anomalies: list[dict[str, object]]
    answer: str


def build_graph(answer_client: AnswerClient | None = None):
    client = answer_client or create_answer_client()

    def parse_node(state: AgentState) -> dict[str, object]:
        transactions = parse_statement_csv(state["raw_csv"])
        return {
            "transactions": [transaction.model_dump(mode="json") for transaction in transactions]
        }

    def categorize_node(state: AgentState) -> dict[str, object]:
        transactions = [
            categorize(Transaction.model_validate(item)) for item in state["transactions"]
        ]
        return {
            "transactions": [transaction.model_dump(mode="json") for transaction in transactions]
        }

    def detect_anomalies_node(state: AgentState) -> dict[str, object]:
        transactions = [Transaction.model_validate(item) for item in state["transactions"]]
        anomalies = detect_anomalies(transactions)
        return {"anomalies": [anomaly.model_dump(mode="json") for anomaly in anomalies]}

    def answer_node(state: AgentState) -> dict[str, str]:
        question = state.get("question", "").strip()
        if not question:
            return {"answer": ""}
        transactions = [Transaction.model_validate(item) for item in state["transactions"]]
        anomalies = [Anomaly.model_validate(item) for item in state.get("anomalies", [])]
        return {"answer": client.answer(question, transactions, anomalies)}

    workflow = StateGraph(AgentState)
    workflow.add_node("parse", parse_node)
    workflow.add_node("categorize", categorize_node)
    workflow.add_node("detect_anomalies", detect_anomalies_node)
    workflow.add_node("answer", answer_node)
    workflow.add_edge(START, "parse")
    workflow.add_edge("parse", "categorize")
    workflow.add_edge("categorize", "detect_anomalies")
    workflow.add_edge("detect_anomalies", "answer")
    workflow.add_edge("answer", END)
    return workflow.compile()
