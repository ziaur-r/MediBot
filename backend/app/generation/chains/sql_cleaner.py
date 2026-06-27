from __future__ import annotations

import re

_SQL_BLOCK_RE = re.compile(r"```(?:sql)?\s*(.*?)```", re.IGNORECASE | re.DOTALL)


class SQLValidationError(ValueError):
    pass


def extract_select_sql(raw_text: str) -> str:
    text = raw_text.strip()
    block_match = _SQL_BLOCK_RE.search(text)
    if block_match:
        text = block_match.group(1).strip()

    statement = text.strip().rstrip(";")
    if not statement:
        raise SQLValidationError("Empty SQL output")

    if ";" in statement:
        raise SQLValidationError("Multiple statements are not allowed")

    lowered = statement.lower().lstrip()
    if not lowered.startswith("select"):
        raise SQLValidationError("Only SELECT statements are allowed")

    forbidden = (" insert ", " update ", " delete ", " drop ", " alter ", " create ", " truncate ")
    padded = f" {lowered} "
    if any(token in padded for token in forbidden):
        raise SQLValidationError("Detected forbidden SQL command")

    return statement
