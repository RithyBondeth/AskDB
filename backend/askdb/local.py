"""Stage 3, open-model variant: Arctic-Text2SQL-R1 (or another Qwen-family SQL
model) served locally by Ollama, or by any OpenAI-compatible completions server
(vLLM, llama.cpp, LM Studio).

The prompt mirrors Snowflake's official evaluation code for Arctic-Text2SQL-R1
(ArcticTraining, projects/arctic_text2sql_r1/bird_eval/infer.py): an
OmniSQL-style instruction, ChatML formatting, and an assistant turn pre-filled
with "<think>" so the model reasons before answering. We send the fully
formatted prompt "raw" so the server does not apply its own chat template on top.
"""

from __future__ import annotations

import re
from typing import Literal

import httpx

from askdb.generate import Generation, GenerationError, Repair

SYSTEM = (
    "You are a data science expert. Below, you are provided with a database schema and a natural"
    " language question. Your task is to understand the schema and generate a valid SQL query to"
    " answer the question."
)

OUTPUT_FORMAT = """\
Please provide a detailed chain-of-thought reasoning process and include your thought process \
within `<think>` tags. Your final answer should be enclosed within `<answer>` tags.

Ensure that your SQL query follows the correct syntax and is formatted as follows:

```sql
-- Your SQL query here
```

Example format:
<think> Step-by-step reasoning, including self-reflection and corrections if necessary. \
[Limited by 4K tokens] </think>
<answer> Summary of the thought process leading to the final SQL query. [Limited by 1K tokens]

```sql
Correct SQL query here
```
</answer>"""

USER_TEMPLATE = """\
Database Engine:
{engine}

Database Schema:
{schema}
This schema describes the database's structure, including tables, columns, primary keys, \
foreign keys, and any relevant relationships or constraints.

Question:
{question}

Instructions:
- Make sure you only output the information that is asked in the question. If the question \
asks for a specific column, make sure to only include that column in the SELECT clause, \
nothing more.
- The generated query should return all of the information asked in the question without any \
missing or extra information.
- Before generating the final SQL query, please think through the steps of how to write the \
query.

Output Format:
{output_format}"""

ASSISTANT_PREFILL = "Let me solve this step by step. \n<think>"

ENGINE_NAMES = {"sqlite": "SQLite", "postgresql": "PostgreSQL", "mysql": "MySQL"}

_SQL_BLOCK = re.compile(r"```sql\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)
_ANSWER = re.compile(r"<answer>(.*?)(?:</answer>|$)", re.DOTALL)


def build_question(question: str, reference_date: str | None, repairs: list[Repair] | None) -> str:
    """The model is single-turn, so context and failed attempts go into the question
    (the same slot OmniSQL uses for "external knowledge")."""
    parts = [question]
    if reference_date:
        parts.append(f"(Treat {reference_date} as today when resolving relative dates.)")
    for r in repairs or []:
        parts.append(
            f"A previous attempt failed.\nSQL:\n```sql\n{r.sql}\n```\nError: {r.error}\n"
            "Write a corrected query."
        )
    return "\n\n".join(parts)


def build_prompt(
    dialect: str,
    schema_ddl: str,
    question: str,
    reference_date: str | None = None,
    repairs: list[Repair] | None = None,
) -> str:
    user = USER_TEMPLATE.format(
        engine=ENGINE_NAMES.get(dialect, dialect),
        schema=schema_ddl,
        question=build_question(question, reference_date, repairs),
        output_format=OUTPUT_FORMAT,
    )
    # Qwen2 ChatML, as produced by the model's tokenizer chat template.
    return (
        f"<|im_start|>system\n{SYSTEM}<|im_end|>\n"
        f"<|im_start|>user\n{user}<|im_end|>\n"
        f"<|im_start|>assistant\n{ASSISTANT_PREFILL}"
    )


def parse_completion(text: str) -> Generation:
    """Take the last ```sql block (as the official eval does) and the <answer> summary."""
    blocks = _SQL_BLOCK.findall(text)
    if not blocks:
        raise GenerationError("The open model's response did not contain a ```sql block.")
    sql = blocks[-1].strip()
    answer = _ANSWER.search(text)
    summary = _SQL_BLOCK.sub("", answer.group(1)).strip() if answer else ""
    if len(summary) > 600:
        summary = summary[:600].rsplit(" ", 1)[0] + "…"
    return Generation(sql=sql, explanation=summary)


class LocalGenerator:
    """Generates SQL with an open model behind Ollama or an OpenAI-compatible server."""

    def __init__(
        self,
        dialect: str,
        schema_ddl: str,
        model: str,
        base_url: str = "http://localhost:11434",
        api: Literal["ollama", "openai"] = "ollama",
        reference_date: str | None = None,
        timeout_s: float = 600.0,
        max_tokens: int = 6144,
        context_window: int = 16384,
        client: httpx.Client | None = None,
    ):
        self.dialect = dialect
        self.schema_ddl = schema_ddl
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.api = api
        self.reference_date = reference_date
        self.max_tokens = max_tokens
        self.context_window = context_window
        self.client = client or httpx.Client(timeout=timeout_s)

    def generate(self, question: str, repairs: list[Repair] | None = None) -> Generation:
        prompt = build_prompt(self.dialect, self.schema_ddl, question, self.reference_date, repairs)
        try:
            text = self._complete(prompt)
        except httpx.ConnectError as e:
            raise GenerationError(
                f"Cannot reach the open model server at {self.base_url}. "
                "Is Ollama (or your completions server) running?"
            ) from e
        except httpx.TimeoutException as e:
            raise GenerationError("The open model timed out. Try a smaller quantization.") from e
        except httpx.HTTPStatusError as e:
            raise GenerationError(
                f"Open model server error {e.response.status_code}: {e.response.text[:300]}"
            ) from e
        return parse_completion(text)

    def _complete(self, prompt: str) -> str:
        # Greedy decoding, matching how the model's benchmark numbers were reported.
        if self.api == "ollama":
            res = self.client.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "raw": True,  # prompt is already chat-formatted
                    "stream": False,
                    "options": {
                        "temperature": 0,
                        "num_ctx": self.context_window,
                        "num_predict": self.max_tokens,
                        "stop": ["<|im_end|>"],
                    },
                },
            )
            res.raise_for_status()
            return res.json()["response"]

        res = self.client.post(
            f"{self.base_url}/v1/completions",
            json={
                "model": self.model,
                "prompt": prompt,
                "temperature": 0,
                "max_tokens": self.max_tokens,
                "stop": ["<|im_end|>"],
            },
        )
        res.raise_for_status()
        return res.json()["choices"][0]["text"]
