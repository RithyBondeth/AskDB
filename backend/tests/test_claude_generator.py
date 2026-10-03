"""Check the request ClaudeGenerator sends, using a mock HTTP transport (no network)."""

import json

import anthropic
import httpx2 as httpx
import pytest

from askdb.generate import ClaudeGenerator, GenerationError, Repair


def mock_client(reply_text: str, stop_reason: str = "end_turn", seen: list | None = None):
    def handler(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(request)
        return httpx.Response(
            200,
            json={
                "id": "msg_test",
                "type": "message",
                "role": "assistant",
                "model": "claude-opus-5-5",
                "content": [{"type": "text", "text": reply_text}],
                "stop_reason": stop_reason,
                "stop_sequence": None,
                "usage": {"input_tokens": 10, "output_tokens": 10},
            },
        )

    return anthropic.Anthropic(
        api_key="test", http_client=httpx.Client(transport=httpx.MockTransport(handler))
    )


def test_request_shape_and_parse():
    seen: list[httpx.Request] = []
    client = mock_client("```sql\nSELECT 1\n```\nOne.", seen=seen)
    gen = ClaudeGenerator("SYSTEM", client=client).generate("q", [Repair("SELECT x", "boom")])

    assert gen.sql == "SELECT 1"
    body = json.loads(seen[0].content)
    assert body["model"] == "claude-opus-5-5"
    assert body["thinking"] == {"type": "adaptive"}
    assert body["output_config"] == {"effort": "medium"}
    assert body["fallbacks"] == "default"
    assert body["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert [m["role"] for m in body["messages"]] == ["user", "assistant", "user"]
    assert "server-side-fallback-2026-07-01" in seen[0].headers["anthropic-beta"]


def test_refusal_raises():
    client = mock_client("", stop_reason="refusal")
    with pytest.raises(GenerationError, match="declined"):
        ClaudeGenerator("SYSTEM", client=client).generate("q")
