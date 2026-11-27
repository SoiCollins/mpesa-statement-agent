from __future__ import annotations

import json
from pathlib import Path

from mpesa_agent.anomalies import detect_anomalies
from mpesa_agent.graph import build_graph
from mpesa_agent.llm import FakeLLMClient
from mpesa_agent.models import Transaction

ROOT = Path(__file__).resolve().parents[1]
CASES_PATH = ROOT / "data" / "evals" / "cases.json"
SAMPLE_PATH = ROOT / "data" / "samples" / "synthetic_statement.csv"


def run() -> tuple[int, int]:
    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    graph = build_graph(FakeLLMClient())
    statement = SAMPLE_PATH.read_text(encoding="utf-8")
    question_passes = 0
    for case in cases["questions"]:
        result = graph.invoke({"raw_csv": statement, "question": case["question"]})
        passed = case["contains"].casefold() in result["answer"].casefold()
        question_passes += passed
        print(f"{'PASS' if passed else 'FAIL'} {case['id']}: {result['answer']}")

    anomaly_passes = 0
    for case in cases["anomalies"]:
        transactions = [Transaction.model_validate(item) for item in case["transactions"]]
        found_types = {anomaly.anomaly_type for anomaly in detect_anomalies(transactions)}
        expected = case["expected"]
        passed = (expected is None and not found_types) or (
            expected is not None and expected in found_types
        )
        anomaly_passes += passed
        print(
            f"{'PASS' if passed else 'FAIL'} {case['id']}: "
            f"expected {expected}, found {found_types}"
        )

    print(
        f"\nQuestion cases: {question_passes}/{len(cases['questions'])}; "
        f"anomaly cases: {anomaly_passes}/{len(cases['anomalies'])}; "
        f"overall: {question_passes + anomaly_passes}/"
        f"{len(cases['questions']) + len(cases['anomalies'])}"
    )
    return question_passes, anomaly_passes


if __name__ == "__main__":
    question_score, anomaly_score = run()
    raise SystemExit(0 if question_score == 10 and anomaly_score == 10 else 1)
