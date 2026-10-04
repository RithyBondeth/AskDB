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


class _Closable:
    def __init__(self, sql: str):
        self.sql, self.closed = sql, False

    def generate(self, question, repairs=None):
        from askdb.generate import Generation

        return Generation(sql=self.sql, explanation="")

    def close(self):
        self.closed = True


def test_ask_closes_the_generator_it_built(db_path):
    from askdb.config import Settings
    from askdb.pipeline import AskDB

    db = AskDB.from_settings(Settings(database_url=f"sqlite:///{db_path}"))
    built = _Closable("SELECT 1")
    db.generator_for = lambda *a, **k: built
    db.ask("one")
    assert built.closed

    passed_in = _Closable("SELECT 1")
    db.ask("one", generator=passed_in)
    assert not passed_in.closed  # the caller owns it


def test_generators_close_only_clients_they_created():
    import anthropic
    import httpx

    from askdb.generate import ClaudeGenerator
    from askdb.hosted import HostedGenerator

    shared = httpx.Client()
    HostedGenerator("s", "m", "http://x", "k", client=shared).close()
    assert not shared.is_closed
    own = HostedGenerator("s", "m", "http://x", "k")
    own.close()
    assert own.client.is_closed

    shared_claude = anthropic.Anthropic(api_key="k")
    ClaudeGenerator("s", client=shared_claude).close()
    assert not shared_claude.is_closed()
    per_request = ClaudeGenerator("s", api_key="user-key")
    assert per_request.client.api_key == "user-key"
    per_request.close()
    assert per_request.client.is_closed()
