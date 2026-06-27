import pytest

from app.generation.chains.sql_cleaner import SQLValidationError, extract_select_sql


def test_extract_select_from_markdown_fence() -> None:
    raw = """```sql
SELECT * FROM claims LIMIT 5;
```"""
    assert extract_select_sql(raw) == "SELECT * FROM claims LIMIT 5"


def test_reject_non_select_statement() -> None:
    with pytest.raises(SQLValidationError):
        extract_select_sql("DELETE FROM claims")


def test_reject_multiple_statements() -> None:
    with pytest.raises(SQLValidationError):
        extract_select_sql("SELECT * FROM claims; SELECT * FROM maintenance_tickets")
