#!/usr/bin/env python3
"""Run an eval suite: the same multi-turn conversations, under each condition, on each model, N times.

Every step saves what it did to its own file, and every check runs on those files.

  run.py SUITE_DIR [--models haiku,sonnet] [--runs 5] [--conditions a,b]
                   [--conversations id1,id2] [--jobs 4] [--dry-run]

Output: SUITE_DIR/runs/<timestamp>/  (results.jsonl, report.md, review.md, one folder per turn)
"""
import argparse
import itertools
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import report  # noqa: E402

TURN_TIMEOUT = 300


def expand(value, ctx):
    """Fill {placeholders} and ~ in strings, recursively through dicts and lists."""
    if isinstance(value, str):
        for k, v in ctx.items():
            value = value.replace("{" + k + "}", str(v))
        return os.path.expanduser(value) if value.startswith("~") else value
    if isinstance(value, dict):
        return {k: expand(v, ctx) for k, v in value.items()}
    if isinstance(value, list):
        return [expand(v, ctx) for v in value]
    return value


def make_workspace(suite, suite_dir, cond, ctx):
    """A fresh project dir outside $HOME, so no stray CLAUDE.md or project settings leak in."""
    ws = Path(tempfile.mkdtemp(prefix="evalkit-"))
    fixtures = cond.get("fixtures", suite.get("fixtures"))
    if fixtures:  # input files the prompts refer to, copied into the project root
        shutil.copytree(suite_dir / fixtures, ws, dirs_exist_ok=True)
    if cond.get("claude_md"):
        src = Path(os.path.expanduser(cond["claude_md"]))
        src = src if src.is_absolute() else suite_dir / src
        shutil.copy(src, ws / "CLAUDE.md")
    if cond.get("settings"):
        (ws / ".claude").mkdir()
        (ws / ".claude" / "settings.json").write_text(json.dumps(expand(cond["settings"], ctx), indent=2))
    if cond.get("skills_dir"):
        src = suite_dir / cond["skills_dir"]
        shutil.copytree(src, ws / ".claude" / "skills", dirs_exist_ok=True)
    return ws


def run_check(check, ctx, out_dir):
    cmd = expand(check["cmd"], ctx)
    p = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=120)
    try:
        body = json.loads(p.stdout)
    except ValueError:
        body = {"stdout": p.stdout.strip()}
    body = body if isinstance(body, dict) else {"value": body}
    body["_exit"] = p.returncode
    if p.stderr.strip():
        body["_stderr"] = p.stderr.strip()[-2000:]
    (out_dir / f"check-{check['id']}.json").write_text(json.dumps(body, indent=2))
    metrics = {}
    for k, v in body.items():
        if k.startswith("_"):
            continue
        if isinstance(v, bool):
            metrics[f"{check['id']}.{k}"] = int(v)
        elif isinstance(v, (int, float)):
            metrics[f"{check['id']}.{k}"] = v
        elif isinstance(v, list):
            metrics[f"{check['id']}.{k}"] = len(v)
    return p.returncode == 0, metrics


def run_conversation(job):
    suite, suite_dir, root, model, cname, conv, rep = job
    cond = suite["conditions"][cname]
    session_id = str(uuid.uuid4())
    base = root / model / cname / conv["id"] / f"r{rep}"
    data = base / "data"
    data.mkdir(parents=True, exist_ok=True)
    ctx = {"data": data, "session_id": session_id, "condition": cname, "model": model, "suite": suite_dir, "kit": HERE}
    ws = make_workspace(suite, suite_dir, cond, ctx)
    env = {**os.environ, **expand(cond.get("env", {}), ctx)}
    # Tools are off unless the suite or condition lists them. A skill needs at least "Skill".
    tools = cond.get("tools", suite.get("tools", []))
    mode = cond.get("permission_mode", suite.get("permission_mode"))
    # Permissions go on the command line: allow rules in an untrusted project's settings are ignored.
    allowed = cond.get("allowed_tools", suite.get("allowed_tools", []))
    denied = cond.get("disallowed_tools", suite.get("disallowed_tools", []))
    rows = []
    try:
        for t, prompt in enumerate(conv["turns"], 1):
            tdir = base / f"t{t}"
            tdir.mkdir(parents=True, exist_ok=True)
            (tdir / "prompt.txt").write_text(prompt)
            cmd = ["claude", "-p", prompt, "--model", model, "--output-format", "json",
                   "--setting-sources", "project", "--strict-mcp-config", "--tools", ",".join(tools)]
            if mode:
                cmd += ["--permission-mode", mode]
            if allowed:
                cmd += ["--allowedTools", ",".join(allowed)]
            if denied:
                cmd += ["--disallowedTools", ",".join(denied)]
            cmd += ["--session-id", session_id] if t == 1 else ["--resume", session_id]
            row = {"model": model, "condition": cname, "conversation": conv["id"], "run": rep,
                   "turn": t, "session_id": session_id, "dir": str(tdir.relative_to(root))}
            start = time.time()
            try:
                p = subprocess.run(cmd, cwd=ws, env=env, capture_output=True, text=True, timeout=TURN_TIMEOUT)
                res = json.loads(p.stdout)
            except (subprocess.TimeoutExpired, ValueError) as exc:
                res = {"is_error": True, "result": f"runner error: {exc}"}
            (tdir / "result.json").write_text(json.dumps(res, indent=2))
            reply = res.get("result") or ""
            (tdir / "reply.md").write_text(reply)
            usage = res.get("usage") or {}
            row.update(ok=not res.get("is_error"), wall_s=round(time.time() - start, 2),
                       duration_ms=res.get("duration_ms"), output_tokens=usage.get("output_tokens"),
                       cost_usd=res.get("total_cost_usd"), checks={}, metrics={})
            # Keep what Claude left in the project (files a skill wrote), minus the setup we put there.
            shutil.copytree(ws, tdir / "workspace", dirs_exist_ok=True,
                            ignore=lambda d, names: [n for n in names if Path(d) == ws and n in ("CLAUDE.md", ".claude")])  # fixtures are kept: a skill may edit them
            if row["ok"]:
                cctx = {**ctx, "reply": tdir / "reply.md", "turn_dir": tdir, "turn": t, "workspace": ws}
                for check in suite.get("checks", []):
                    if cname in check.get("skip_conditions", []) or cname not in check.get("only_conditions", [cname]):
                        continue
                    passed, metrics = run_check(check, cctx, tdir)
                    row["checks"][check["id"]] = passed
                    row["metrics"].update(metrics)
            rows.append(row)
            print(f"  {model:>7} {cname:<10} {conv['id']:<10} r{rep} t{t} "
                  + ("ok" if row["ok"] else "ERROR") + f" {row['wall_s']}s", flush=True)
            if not row["ok"]:
                break
    finally:
        shutil.rmtree(ws, ignore_errors=True)
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("suite")
    ap.add_argument("--models")
    ap.add_argument("--runs", type=int)
    ap.add_argument("--conditions")
    ap.add_argument("--conversations")
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    suite_dir = Path(a.suite).expanduser().resolve()
    if suite_dir.name == "suite.json":
        suite_dir = suite_dir.parent
    if not (suite_dir / "suite.json").is_file():
        hint = " (found suites.json: rename it to suite.json)" if (suite_dir / "suites.json").exists() else ""
        if (suite_dir / "SKILL.md").exists():
            hint = (f"\nThat folder is a skill, not a suite. Create a suite for it first:\n"
                    f"  python3 {HERE}/new.py SUITE_NAME --skill {suite_dir}")
        sys.exit(f"No suite.json in {suite_dir}{hint}\nA suite is a folder with a suite.json; see {HERE}/README.md.")
    suite = json.loads((suite_dir / "suite.json").read_text())
    todo = [t for c in suite["conversations"] for t in c["turns"] if t.startswith("TODO")]
    if todo:
        sys.exit(f"suite.json still has TODO prompts, for example: {todo[0]!r}")
    models = a.models.split(",") if a.models else suite["models"]
    runs = a.runs or suite.get("runs", 5)
    conds = a.conditions.split(",") if a.conditions else list(suite["conditions"])
    convs = [c for c in suite["conversations"] if not a.conversations or c["id"] in a.conversations.split(",")]
    jobs = list(itertools.product(models, conds, convs, range(1, runs + 1)))
    turns = sum(len(c["turns"]) for c in convs) * len(models) * len(conds) * runs
    print(f"{suite['name']}: {len(jobs)} conversations, {turns} model calls "
          f"({len(models)} models x {len(conds)} conditions x {len(convs)} conversations x {runs} runs)")
    if a.dry_run:
        return

    root = suite_dir / "runs" / time.strftime("%Y%m%d-%H%M%S")
    root.mkdir(parents=True)
    (root / "suite.json").write_text(json.dumps(suite, indent=2))
    (root / "args.json").write_text(json.dumps(vars(a), indent=2))
    with ThreadPoolExecutor(a.jobs) as pool, open(root / "results.jsonl", "a") as out:
        for rows in pool.map(run_conversation, [(suite, suite_dir, root, m, c, v, r) for m, c, v, r in jobs]):
            for row in rows:
                out.write(json.dumps(row) + "\n")
    print(report.build(root))
    print(f"\nArtifacts: {root}")


if __name__ == "__main__":
    main()
