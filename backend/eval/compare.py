"""Print a Markdown comparison table from eval result files.

uv run python eval/compare.py                  # all files in eval/results/
uv run python eval/compare.py a.json b.json
uv run python eval/compare.py --readme         # also write the table into README.md
uv run python eval/compare.py --dataset spider-dev-200 --readme   # a benchmark's table

Each dataset has its own table (and its own block in the README); runs from other
datasets are left out.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

RESULTS = Path(__file__).with_name("results")
README = Path(__file__).resolve().parents[2] / "README.md"
# The README table lives between these markers so it can be regenerated.
START, END = "<!-- eval-table:start -->", "<!-- eval-table:end -->"


def markers(dataset: str) -> tuple[str, str]:
    """The README block for a dataset: Chinook's is the original one; a benchmark's
    is named by its family (spider-dev-200 -> eval-table:spider)."""
    if dataset == "chinook":
        return START, END
    family = dataset.split("-")[0]
    return f"<!-- eval-table:{family}:start -->", f"<!-- eval-table:{family}:end -->"


def table(runs: list[dict]) -> list[str]:
    lines = [
        "| Model | Provider | Execution accuracy | Fixed by self-correction | Median s/question |",
        "| --- | --- | --- | --- | --- |",
    ]
    for r in sorted(runs, key=lambda r: -r["accuracy"]):
        total = r.get("total") or len(r["results"])
        hits = r.get("hits", round(r["accuracy"] * total))
        lines.append(
            f"| `{r['model']}` | {r.get('provider', 'claude')} "
            f"| **{r['accuracy']:.1%}** ({hits}/{total}) "
            f"| {r.get('self_corrected', '–')} | {r.get('median_seconds', '–')} |"
        )
    return lines


def update_readme(lines: list[str], readme: Path = README, dataset: str = "chinook") -> None:
    start, end = markers(dataset)
    text = readme.read_text()
    block = re.compile(re.escape(start) + r".*?" + re.escape(end), re.S)
    if not block.search(text):
        raise SystemExit(f"{readme.name} has no {start} … {end} block to replace.")
    readme.write_text(block.sub(lambda _: "\n".join([start, *lines, end]), text))


def main(argv: list[str]) -> int:
    write_readme = "--readme" in argv
    dataset = "chinook"
    if "--dataset" in argv:
        i = argv.index("--dataset")
        dataset = argv[i + 1]
        argv = argv[:i] + argv[i + 2 :]
    paths = [a for a in argv if a != "--readme"]
    files = [Path(p) for p in paths] or sorted(RESULTS.glob("*.json"))
    runs = [json.loads(f.read_text()) | {"file": f.name} for f in files]
    runs = [r for r in runs if r.get("dataset", "chinook") == dataset]
    if not runs:
        print(f"No {dataset} result files. Run eval/run_eval.py with --out first.", file=sys.stderr)
        return 1

    lines = table(runs)
    print("\n".join(lines))

    # Questions where the models disagree are the interesting ones to read.
    if len(runs) > 1:
        by_id: dict[str, dict[str, bool]] = {}
        for r in runs:
            for item in r["results"]:
                by_id.setdefault(item["id"], {})[r["model"]] = item["match"]
        split = [qid for qid, m in by_id.items() if len(set(m.values())) > 1]
        if split:
            print("\nQuestions where results differ: " + ", ".join(f"`{q}`" for q in split))

    if write_readme:
        update_readme(lines, dataset=dataset)
        print(f"\nUpdated the table in {README.name}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
