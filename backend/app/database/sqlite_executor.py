from __future__ import annotations

import sqlite3
from pathlib import Path


class SQLiteExecutor:
    def __init__(self, db_path: str) -> None:
        self._db_path = Path(db_path)
        self._ensure_bootstrap_schema()

    def _ensure_bootstrap_schema(self) -> None:
        if self._db_path.exists():
            return

        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS claims (
                    id INTEGER PRIMARY KEY,
                    claim_id TEXT,
                    status TEXT,
                    amount REAL,
                    created_at TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS maintenance_tickets (
                    id INTEGER PRIMARY KEY,
                    ticket_id TEXT,
                    equipment TEXT,
                    status TEXT,
                    created_at TEXT
                )
                """
            )
            conn.commit()

    @property
    def db_path(self) -> Path:
        return self._db_path

    def inspect_schema(self) -> dict[str, list[str]]:
        if not self._db_path.exists():
            return {}

        with sqlite3.connect(self._db_path) as conn:
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            ).fetchall()

            schema: dict[str, list[str]] = {}
            for (table_name,) in tables:
                columns = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
                schema[table_name] = [col[1] for col in columns]

        return schema

    def execute_select(self, query: str) -> list[dict[str, object]]:
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(query).fetchall()
            return [dict(row) for row in rows]
