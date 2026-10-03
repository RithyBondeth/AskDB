"""LocalGenerator against mock Ollama / OpenAI-compatible servers (no model download)."""

import json

import httpx
import pytest

from askdb.execute import answer
from askdb.generate import GenerationError, Repair
from askdb.local import LocalGenerator, build_prompt, parse_completion

# What Arctic-Text2SQL-R1 returns after the "<think>" prefill.
ARCTIC_REPLY = """ The question asks for names. I need the customer table.
I should order by id. </think>
<answer> Select names from customer ordered by id.

```sql
SELECT name FROM customer ORDER BY id
```
</answer>"""


def mock_client(replies: list[str], api: str, seen: list):
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        text = replies[min(len(seen), len(replies)) - 1]
        if api == "ollama":
            return httpx.Response(200, json={"model": "m", "response": text, "done": True})
        return httpx.Response(200, json={"choices": [{"text": text, "index": 0}]})

    return httpx.Client(transport=httpx.MockTransport(handler))


def make(api="ollama", replies=(ARCTIC_REPLY,), seen=None):
    seen = seen if seen is not None else []
    return LocalGenerator(
        dialect="sqlite",
        schema_ddl="CREATE TABLE customer (id INTEGER PRIMARY KEY, name TEXT);",
        model="arctic",
        api=api,
        reference_date="2013-12-31",
        client=mock_client(list(replies), api, seen),
    )


def test_prompt_matches_arctic_format():
    prompt = build_prompt("sqlite", "CREATE TABLE t (a INT);", "How many?", "2013-12-31")
    assert prompt.startswith("<|im_start|>system\nYou are a data science expert.")
    assert (
        "<|im_start|>user\nDatabase Engine:\nSQLite\n\nDatabase Schema:\nCREATE TABLE t" in prompt
    )
    assert "Question:\nHow many?\n\n(Treat 2013-12-31 as today" in prompt
    assert prompt.endswith("<|im_start|>assistant\nLet me solve this step by step. \n<think>")
    assert prompt.count("<|im_start|>") == 3


def test_repairs_are_folded_into_the_question():
    prompt = build_prompt("sqlite", "DDL", "Q?", None, [Repair("SELECT x", "no such column: x")])
    assert (
        "A previous attempt failed.\nSQL:\n```sql\nSELECT x\n```\nError: no such column: x"
        in prompt
    )


def test_parse_takes_last_sql_block_and_answer_summary():
    gen = parse_completion("```sql\nSELECT 1\n```\n</think><answer>Final.\n```sql\nSELECT 2\n```")
    assert gen.sql == "SELECT 2"
    assert gen.explanation == "Final."


def test_parse_without_sql_fails():
    with pytest.raises(GenerationError):
        parse_completion("I am not sure. </think><answer>No idea.</answer>")


def test_ollama_request_shape():
    seen: list[httpx.Request] = []
    gen = make("ollama", seen=seen).generate("names?")
    assert gen.sql == "SELECT name FROM customer ORDER BY id"
    assert seen[0].url.path == "/api/generate"
    body = json.loads(seen[0].content)
    assert body["raw"] is True and body["stream"] is False
    assert body["options"]["temperature"] == 0
    assert body["options"]["stop"] == ["<|im_end|>"]


def test_openai_completions_request_shape():
    seen: list[httpx.Request] = []
    make("openai", seen=seen).generate("names?")
    assert seen[0].url.path == "/v1/completions"
    body = json.loads(seen[0].content)
    assert body["temperature"] == 0 and body["prompt"].endswith("<think>")


def test_self_correction_works_with_open_model(engine):
    bad = ARCTIC_REPLY.replace("SELECT name FROM", "SELECT nme FROM")
    seen: list[httpx.Request] = []
    gen = make("ollama", replies=(bad, ARCTIC_REPLY), seen=seen)
    ans = answer("names?", gen, engine, "sqlite")
    assert ans.result.rows == [["Ada"], ["Linus"], ["Grace"]]
    assert len(ans.attempts) == 2
    assert "no such column: nme" in json.loads(seen[1].content)["prompt"]


def test_unreachable_server_gives_friendly_error():
    def handler(request):
        raise httpx.ConnectError("refused")

    gen = LocalGenerator(
        "sqlite", "DDL", "m", client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    with pytest.raises(GenerationError, match="Is Ollama"):
        gen.generate("q")


def test_follow_up_context_goes_into_the_question():
    from askdb.generate import Turn

    prompt = build_prompt("sqlite", "DDL", "only 2012", None, None, [Turn("by year?", "SELECT 1")])
    assert "Earlier in this conversation:\nQ: by year?\n```sql\nSELECT 1\n```" in prompt
    assert "Now answer this follow-up:\n\nonly 2012" in prompt
