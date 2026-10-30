#!/usr/bin/env python3
"""Summarize a run folder into report.md (numbers) and review.md (replies for the human step).

  report.py RUN_DIR
"""
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path


def mean(xs):
    xs = [x for x in xs if x is not None]
    return statistics.mean(xs) if xs else None


def sd(xs):
    xs = [x for x in xs if x is not None]
    return statistics.stdev(xs) if len(xs) > 1 else None


def fmt(x, digits=1):
    if x is None:
        return "–"
    return f"{x:.{digits}f}" if isinstance(x, float) else str(x)


def build(root):
    root = Path(root)
    suite = json.loads((root / "suite.json").read_text())
    rows = [json.loads(l) for l in open(root / "results.jsonl") if l.strip()]
    cfg = suite.get("report", {})
    primary = cfg.get("primary")
    columns = cfg.get("columns", [])
    groups = defaultdict(list)
    for r in rows:
        groups[(r["model"], r["condition"])].append(r)
    max_turn = max((r["turn"] for r in rows), default=0)
    check_ids = sorted({c for r in rows for c in r["checks"]})

    out = [f"# {suite['name']} eval: {root.name}", ""]
    if suite.get("description"):
        out += [suite["description"], ""]

    # Main table: one line per model x condition.
    head = ["model", "condition", "turns ok", "out tokens", "seconds", "cost $"] + [c["label"] for c in columns]
    if primary:
        head += [f"{primary} sd"] + [f"{primary} t{t}" for t in range(1, max_turn + 1)]
    out += ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    for (model, cond), rs in sorted(groups.items()):
        ok = [r for r in rs if r["ok"]]
        line = [model, cond, f"{len(ok)}/{len(rs)}", fmt(mean([r["output_tokens"] for r in ok])),
                fmt(mean([r["wall_s"] for r in ok])), fmt(sum(r["cost_usd"] or 0 for r in rs), 3)]
        line += [fmt(mean([r["metrics"].get(c["metric"]) for r in ok])) for c in columns]
        if primary:
            # Spread between repeat runs of the same conversation and turn, averaged.
            cells = defaultdict(list)
            for r in ok:
                cells[(r["conversation"], r["turn"])].append(r["metrics"].get(primary))
            line.append(fmt(mean([sd(v) for v in cells.values()])))
            line += [fmt(mean([r["metrics"].get(primary) for r in ok if r["turn"] == t]))
                     for t in range(1, max_turn + 1)]
        out.append("| " + " | ".join(line) + " |")
    if primary:
        out += ["", f"`{primary} sd` is the spread across runs (lower = more consistent). "
                f"`t1..t{max_turn}` show drift as the conversation grows."]

    # Check pass rates.
    if check_ids:
        out += ["", "## Checks (pass rate)", "", "| model | condition | " + " | ".join(check_ids) + " |",
                "|" + "---|" * (len(check_ids) + 2)]
        for (model, cond), rs in sorted(groups.items()):
            cells = []
            for c in check_ids:
                vals = [r["checks"][c] for r in rs if c in r["checks"]]
                cells.append(f"{sum(vals)}/{len(vals)}" if vals else "–")
            out.append(f"| {model} | {cond} | " + " | ".join(cells) + " |")

    # Step map: which step is code / model / human, and what checks it.
    if suite.get("steps"):
        out += ["", "## Steps", "", "| step | kind | checked by |", "|---|---|---|"]
        for s in suite["steps"]:
            out.append(f"| {s['id']}: {s.get('desc', '')} | {s['kind']} | {s.get('check', '–')} |")

    errors = [r for r in rows if not r["ok"]]
    if errors:
        out += ["", f"## Errors ({len(errors)})", ""]
        out += [f"- {r['dir']}/result.json" for r in errors[:20]]

    text = "\n".join(out) + "\n"
    (root / "report.md").write_text(text)
    write_review(root, suite, rows)
    return text


def write_review(root, suite, rows):
    """Last turn of run 1 for each conversation, side by side per condition: the human-in-the-loop step."""
    out = [f"# {suite['name']} review: {root.name}", "",
           "Read each set. Note which reply you would want, and why. The numbers do not measure this.", ""]
    by_conv = defaultdict(list)
    for r in rows:
        if r["run"] == 1 and r["ok"]:
            by_conv[(r["model"], r["conversation"])].append(r)
    for (model, conv), rs in sorted(by_conv.items()):
        last = max(r["turn"] for r in rs)
        out += [f"## {conv} · {model} · turn {last}", "",
                "> " + (root / rs[0]["dir"]).with_name(f"t{last}").joinpath("prompt.txt").read_text().replace("\n", "\n> "), ""]
        for r in sorted((r for r in rs if r["turn"] == last), key=lambda r: r["condition"]):
            reply = (root / r["dir"] / "reply.md").read_text()
            out += [f"### {r['condition']}", "", reply, ""]
    (root / "review.md").write_text("\n".join(out))


if __name__ == "__main__":
    print(build(sys.argv[1]))
