#!/usr/bin/env python3
"""Check: did the skill run in this session? Counts only Skill calls that succeeded.

Usage: skill_used.py SESSION_ID SKILL_NAME [--expect-unused]
"""
import glob
import json
import os
import sys

session, skill = sys.argv[1], sys.argv[2]
expect_unused = "--expect-unused" in sys.argv
paths = glob.glob(os.path.expanduser(f"~/.claude/projects/*/{session}.jsonl"))
calls, results = {}, {}
for line in open(paths[0], encoding="utf-8") if paths else []:
    e = json.loads(line)
    content = (e.get("message") or {}).get("content")
    if not isinstance(content, list) or e.get("type") not in ("assistant", "user"):
        continue
    for c in content:
        if c.get("type") == "tool_use" and c.get("name") == "Skill":
            if str((c.get("input") or {}).get("skill", "")).split(":")[-1] == skill:
                calls[c["id"]] = True
        elif c.get("type") == "tool_result" and c.get("tool_use_id"):
            results[c["tool_use_id"]] = not c.get("is_error")
ok = [i for i in calls if results.get(i)]
print(json.dumps({"used": bool(ok), "calls": len(calls), "failed_calls": len(calls) - len(ok), "transcript": bool(paths)}))
sys.exit(0 if bool(ok) != expect_unused else 1)
