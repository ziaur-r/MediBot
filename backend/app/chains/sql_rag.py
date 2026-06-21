from __future__ import annotations

from app.chains.sql_cleaner import extract_select_sql
from app.database.sqlite_executor import SQLiteExecutor
from app.services.llm_client import LLMClient


class SQLRAGChain:
    def __init__(self, llm_client: LLMClient, sqlite_executor: SQLiteExecutor) -> None:
        self._llm = llm_client
        self._sqlite = sqlite_executor

    def run(self, question: str) -> tuple[str, str, list[dict[str, object]]]:
        schema = self._sqlite.inspect_schema()
        sql_prompt = (
            "Generate a SQLite SELECT query only. "
            f"Schema: {schema}. Question: {question}"
        )
        raw_sql = self._llm.generate(sql_prompt)
        sql_query = extract_select_sql(raw_sql)
        result_rows = self._sqlite.execute_select(sql_query)

        summarize_prompt = (
            "Summarize these SQLite query results for an internal healthcare operations user. "
            f"Question: {question}. Query: {sql_query}. Rows: {result_rows}"
        )
        answer = self._llm.generate(summarize_prompt)
        return answer, sql_query, result_rows

    @staticmethod
    def validate_sql_output(raw_text: str) -> str:
        return extract_select_sql(raw_text)
