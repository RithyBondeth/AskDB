import pytest

from askdb.generate import (
    CannotAnswerError,
    GenerationError,
    Repair,
    Turn,
    build_messages,
    build_system_prompt,
    parse_response,
)


def test_parse_sql_block_and_explanation():
    gen = parse_response("```sql\nSELECT 1;\n```\nReturns one.")
    assert gen.sql == "SELECT 1;"
    assert gen.explanation == "Returns one."


def test_parse_without_block_fails():
    with pytest.raises(GenerationError):
        parse_response("SELECT 1")


def test_cannot_answer():
    with pytest.raises(CannotAnswerError, match="weather"):
        parse_response("CANNOT_ANSWER: the schema has no weather data.")


def test_repairs_become_conversation_turns():
    msgs = build_messages("q", [Repair("SELECT x", "no such column: x")])
    assert [m["role"] for m in msgs] == ["user", "assistant", "user"]
    assert "no such column: x" in msgs[2]["content"]


def test_system_prompt_contains_schema_and_date():
    prompt = build_system_prompt("sqlite", "CREATE TABLE t (a INT);", 100, "2013-12-31")
    assert "CREATE TABLE t" in prompt and "2013-12-31" in prompt and "LIMIT 100" in prompt


def test_context_turns_come_before_the_question():
    msgs = build_messages("now only 2012", None, [Turn("revenue by year", "SELECT 1")])
    assert [m["role"] for m in msgs] == ["user", "assistant", "user"]
    assert msgs[0]["content"] == "Q: revenue by year"
    assert "SELECT 1" in msgs[1]["content"]
    assert msgs[2]["content"].startswith("Q: now only 2012")
