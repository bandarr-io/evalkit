#!/usr/bin/env python3
"""Create a suite skeleton.

  new.py NAME                    empty suite
  new.py NAME --skill PATH       suite that compares Claude with and without the skill at PATH

The suite goes to $EVALKIT_HOME/suites/NAME (default ~/.claude/evalkit/suites/NAME).
Then edit its suite.json: write real conversations, map the steps, add checks.
"""
import argparse
import json
import os
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
# Suites live outside the kit: a plugin update replaces the kit folder.
SUITES = Path(os.environ.get("EVALKIT_HOME", "~/.claude/evalkit")).expanduser() / "suites"


def frontmatter(skill_md):
    m = re.match(r"---\n(.*?)\n---", skill_md.read_text(), re.S)
    meta, key = {}, None
    for line in (m.group(1) if m else "").splitlines():
        kv = re.match(r"([\w-]+):\s*(.*)", line)
        if kv:
            key, val = kv.groups()
            meta[key] = val.strip().strip("\"'")
        elif key and re.match(r"\s+-\s+", line):  # YAML list item
            meta[key] = (meta[key] + ", " if meta[key] else "") + re.sub(r"\s+-\s+", "", line, 1).strip("\"'")
    return meta


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("name")
    ap.add_argument("--skill", help="skill folder (the one with SKILL.md)")
    a = ap.parse_args()

    dest = SUITES / a.name
    if dest.exists():
        sys.exit(f"{dest} exists already.")
    suite = {
        "name": a.name,
        "description": "TODO: the question this eval answers.",
        "models": ["haiku", "sonnet"],
        "runs": 5,
        "tools": [],
        "conditions": {"baseline": {}},
        "conversations": [{"id": "example", "turns": ["TODO: first prompt", "TODO: follow-up prompt"]}],
        "checks": [{"id": "reply", "cmd": "python3 {kit}/checks/reply_stats.py '{reply}'"}],
        "steps": [{"id": "TODO", "kind": "code | model | human", "desc": "TODO: one row per step", "check": "TODO"}],
        "report": {"columns": [{"label": "words", "metric": "reply.words"}]},
    }

    if a.skill:
        src = Path(a.skill).expanduser().resolve()
        if src.name == "SKILL.md":
            src = src.parent
        if not (src / "SKILL.md").is_file():
            sys.exit(f"No SKILL.md in {src}")
        meta = frontmatter(src / "SKILL.md")
        skill = meta.get("name") or src.name
        dest.mkdir(parents=True)
        shutil.copytree(src, dest / "skills" / skill)

        # Same tools in both conditions, so the skill is the only difference.
        allowed = [t.strip() for t in re.split(r",\s*|\s+(?![^()]*\))", meta.get("allowed-tools", "")) if t.strip()]
        tools = sorted({"Skill"} | {re.sub(r"\(.*", "", t) for t in allowed})
        allow = ["Skill"] + allowed  # -p mode refuses an unapproved skill call
        # Your installed skills load in both conditions; the deny rule keeps a copy of
        # this skill in ~/.claude/skills or a plugin out of the without-skill condition.
        without = {"allowed_tools": allow, "disallowed_tools": [f"Skill({skill})"]}
        with_ = {"allowed_tools": allow, "skills_dir": "skills"}
        suite.update(
            description=f"Does the {skill} skill improve replies, and does Claude use it when it should?",
            tools=tools,
            conditions={"without-skill": without, "with-skill": with_},
            conversations=[{"id": "example", "turns": [
                f"TODO: a request the {skill} skill should handle (do not name the skill, to test that Claude picks it)",
                "TODO: a follow-up prompt"]}],
        )
        suite["checks"].append({"id": "skill-used", "only_conditions": ["with-skill"],
                                "cmd": f"python3 {{kit}}/checks/skill_used.py {{session_id}} {skill}"})
        suite["checks"].append({"id": "skill-not-used", "only_conditions": ["without-skill"],
                                "cmd": f"python3 {{kit}}/checks/skill_used.py {{session_id}} {skill} --expect-unused"})
        suite["steps"] = [
            {"id": "trigger", "kind": "model", "desc": f"Claude picks {skill}", "check": "skill-used"},
            {"id": "TODO", "kind": "code | model | human", "desc": "TODO: one row per step in SKILL.md", "check": "TODO"},
            {"id": "quality", "kind": "human", "desc": "The result is what you wanted", "check": "you, with review.md"},
        ]
        suite["report"]["columns"].append({"label": "skill used", "metric": "skill-used.used"})
    else:
        dest.mkdir(parents=True)

    (dest / "suite.json").write_text(json.dumps(suite, indent=2) + "\n")
    print(f"Created {dest}/suite.json")
    if a.skill:
        print(f"Copied the skill to {dest}/skills/{skill}/ (the with-skill condition uses this copy).")
        print(f"Tools in both conditions: {', '.join(suite['tools'])}")
        installed = [p for p in [Path.home() / ".claude" / "skills" / skill] if p.exists()]
        if installed:
            print(f"Note: {installed[0]} is installed too. The without-skill condition denies it.")
    print("Next: replace every TODO in suite.json, then run:\n"
          f"  python3 {HERE}/run.py {dest} --models haiku --runs 1")


if __name__ == "__main__":
    main()
