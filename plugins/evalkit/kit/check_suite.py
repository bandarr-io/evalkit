#!/usr/bin/env python3
"""Validate a suite before spending money on it: list TODOs and structural problems.

  check_suite.py SUITE_DIR [--json]

Exit 0 = ready to run, 1 = TODOs or errors left.
"""
import json
import os
import re
import sys
from pathlib import Path

PLACEHOLDERS = {"reply", "turn_dir", "turn", "session_id", "data", "suite", "condition", "model", "workspace", "kit"}
KINDS = {"code", "model", "human"}
HERE = Path(__file__).resolve().parent


def todos(value, path="$"):
    if isinstance(value, str):
        if "TODO" in value:
            yield path, value
    elif isinstance(value, dict):
        for k, v in value.items():
            yield from todos(v, f"{path}.{k}")
    elif isinstance(value, list):
        for i, v in enumerate(value):
            yield from todos(v, f"{path}[{i}]")


def validate(suite_dir):
    suite_dir = Path(suite_dir).expanduser().resolve()
    if suite_dir.name == "suite.json":
        suite_dir = suite_dir.parent
    errors, warnings = [], []
    try:
        suite = json.loads((suite_dir / "suite.json").read_text())
    except FileNotFoundError:
        return {"suite": str(suite_dir), "todos": [], "errors": [f"no suite.json in {suite_dir}"], "warnings": []}
    except ValueError as exc:
        return {"suite": str(suite_dir), "todos": [], "errors": [f"suite.json is not valid JSON: {exc}"], "warnings": []}

    if not suite.get("models"):
        errors.append("models: list at least one model")
    if not isinstance(suite.get("runs", 5), int) or suite.get("runs", 5) < 1:
        errors.append("runs: must be a whole number >= 1")
    elif suite.get("runs", 5) < 3:
        warnings.append("runs: under 3 runs cannot show if results are consistent")

    conds = suite.get("conditions") or {}
    if not conds:
        errors.append("conditions: add at least one")
    elif len(conds) < 2:
        warnings.append("conditions: with one condition there is nothing to compare against")
    if suite.get("fixtures") and not (suite_dir / suite["fixtures"]).is_dir():
        errors.append(f"fixtures: {suite['fixtures']} not found in the suite")
    for name, c in conds.items():
        if c.get("fixtures") and not (suite_dir / c["fixtures"]).is_dir():
            errors.append(f"conditions.{name}.fixtures: {c['fixtures']} not found in the suite")
        for key in ("claude_md",):
            if c.get(key) and not (suite_dir / os.path.expanduser(c[key])).exists():
                errors.append(f"conditions.{name}.{key}: {c[key]} not found")
        if c.get("skills_dir") and not (suite_dir / c["skills_dir"]).is_dir():
            errors.append(f"conditions.{name}.skills_dir: {c['skills_dir']} not found in the suite")
        tools = c.get("tools", suite.get("tools", []))
        if c.get("skills_dir") and "Skill" not in tools:
            errors.append(f"conditions.{name}: has skills_dir but 'Skill' is not in tools")

    convs = suite.get("conversations") or []
    if not convs:
        errors.append("conversations: add at least one")
    ids = [c.get("id") for c in convs]
    if len(ids) != len(set(ids)):
        errors.append("conversations: ids must be unique")
    for c in convs:
        if not c.get("turns") or not all(isinstance(t, str) and t.strip() for t in c["turns"]):
            errors.append(f"conversations.{c.get('id')}: needs one or more non-empty turns")

    check_ids = set()
    for chk in suite.get("checks") or []:
        cid = chk.get("id")
        if not cid or cid in check_ids:
            errors.append(f"checks: missing or duplicate id {cid!r}")
        check_ids.add(cid)
        cmd = chk.get("cmd", "")
        if not cmd:
            errors.append(f"checks.{cid}: no cmd")
        for ph in set(re.findall(r"\{(\w+)\}", cmd)) - PLACEHOLDERS:
            errors.append(f"checks.{cid}: unknown placeholder {{{ph}}}")
        for script in re.findall(r"([\w{}~./-]+\.(?:py|sh))\b", cmd):
            p = Path(os.path.expanduser(script.replace("{suite}", str(suite_dir)).replace("{kit}", str(HERE))))
            if not p.is_absolute():
                p = suite_dir / p
            if "{" not in str(p) and not p.exists():
                errors.append(f"checks.{cid}: script {script} not found")
        for key in ("only_conditions", "skip_conditions"):
            for name in chk.get(key, []):
                if name not in conds:
                    errors.append(f"checks.{cid}.{key}: no condition named {name!r}")
    if not check_ids:
        warnings.append("checks: none, so the report has no metrics")

    steps = suite.get("steps") or []
    if not steps:
        warnings.append("steps: map the workflow's steps so the report shows what is and is not checked")
    for s in steps:
        if s.get("kind") not in KINDS:
            errors.append(f"steps.{s.get('id')}: kind must be one of code, model, human")
        elif s["kind"] != "human" and s.get("check") in (None, "", "–"):
            warnings.append(f"steps.{s.get('id')}: {s['kind']} step has no check")

    rep = suite.get("report") or {}
    metrics = [c.get("metric", "") for c in rep.get("columns", [])] + ([rep["primary"]] if rep.get("primary") else [])
    for m in metrics:
        if m.split(".")[0] not in check_ids:
            errors.append(f"report: metric {m!r} does not start with a check id")

    found = [{"path": p, "text": t} for p, t in todos(suite)]
    return {"suite": str(suite_dir), "todos": found, "errors": errors, "warnings": warnings}


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        sys.exit(__doc__)
    r = validate(args[0])
    if "--json" in sys.argv:
        print(json.dumps(r, indent=2))
    else:
        print(r["suite"])
        for label, items in (("TODO", [f"{t['path']}: {t['text']}" for t in r["todos"]]),
                             ("ERROR", r["errors"]), ("WARN", r["warnings"])):
            for i in items:
                print(f"  {label:5} {i}")
        print("  ready to run" if not (r["todos"] or r["errors"]) else
              f"  not ready: {len(r['todos'])} TODOs, {len(r['errors'])} errors")
    sys.exit(0 if not (r["todos"] or r["errors"]) else 1)


if __name__ == "__main__":
    main()
