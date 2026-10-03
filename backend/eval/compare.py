"""Print a Markdown comparison table from eval result files.

uv run python eval/compare.py                  # all files in eval/results/
uv run python eval/compare.py a.json b.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

RESULTS = Path(__file__).with_name("results")


def main(paths: list[str]) -> int:
    files = [Path(p) for p in paths] or sorted(RESULTS.glob("*.json"))
    if not files:
        print("No result files. Run eval/run_eval.py with --out first.", file=sys.stderr)
        return 1

    runs = [json.loads(f.read_text()) | {"file": f.name} for f in files]
    print(
        "| Model | Provider | Execution accuracy | Fixed by self-correction | Median s/question |"
    )
    print("| --- | --- | --- | --- | --- |")
    for r in sorted(runs, key=lambda r: -r["accuracy"]):
        total = r.get("total") or len(r["results"])
        hits = r.get("hits", round(r["accuracy"] * total))
        print(
            f"| `{r['model']}` | {r.get('provider', 'claude')} "
            f"| **{r['accuracy']:.1%}** ({hits}/{total}) "
            f"| {r.get('self_corrected', '–')} | {r.get('median_seconds', '–')} |"
        )

    # Questions where the models disagree are the interesting ones to read.
    if len(runs) > 1:
        by_id: dict[str, dict[str, bool]] = {}
        for r in runs:
            for item in r["results"]:
                by_id.setdefault(item["id"], {})[r["model"]] = item["match"]
        split = [qid for qid, m in by_id.items() if len(set(m.values())) > 1]
        if split:
            print("\nQuestions where results differ: " + ", ".join(f"`{q}`" for q in split))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
