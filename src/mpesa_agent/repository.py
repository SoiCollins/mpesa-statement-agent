from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from uuid import uuid4


@dataclass(frozen=True)
class UploadedStatement:
    statement_id: str
    filename: str
    raw_csv: str


class StatementRepository:
    def __init__(self) -> None:
        self._statements: dict[str, UploadedStatement] = {}
        self._lock = RLock()

    def add(self, filename: str, raw_csv: str) -> UploadedStatement:
        statement = UploadedStatement(str(uuid4()), filename, raw_csv)
        with self._lock:
            self._statements[statement.statement_id] = statement
        return statement

    def get(self, statement_id: str) -> UploadedStatement | None:
        with self._lock:
            return self._statements.get(statement_id)
