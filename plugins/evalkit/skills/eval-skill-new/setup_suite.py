#!/usr/bin/env python3
"""Create an evalkit suite for a skill, ready for /evalkit:evalkit-fill.

  setup_suite.py SKILL [--suite NAME] [--sync]

SKILL is a skill name ("power-design", "/power-design", "plugin:name") or a folder that holds SKILL.md.
The suite is $EVALKIT_HOME/suites/<NAME> (default ~/.claude/evalkit/suites/<NAME>), NAME default <skill>-eval.

What it does (the fixed part; the judgment stays with /evalkit:evalkit-fill):
  1. finds the skill folder (user skills, this project's skills, plugin skills)
  2. runs evalkit new.py, which copies the skill and writes the with-skill / without-skill conditions
  3. adds the tools the skill needs to both conditions: Read and Glob always, Write and Edit when the
     skill writes files, Bash plus a run rule per script type when the skill ships scripts
  4. prints findings that /evalkit:evalkit-fill must handle: env vars the scripts read, MCP tools (absent in
     the eval), input files the prompts may need as fixtures

Exit 0: suite created. Exit 2: the suite exists (with --sync, the skill copy is refreshed instead).
Exit 1: skill not found, or found more than once.
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

HOME = Path.home()
KIT = Path(__file__).resolve().parents[2] / "kit"  # <plugin>/skills/eval-skill-new/ -> <plugin>/kit
sys.path.insert(0, str(KIT))
from new import SUITES  # noqa: E402  (one rule for where suites go)
RUNNERS = {".py": "Bash(python3:*)", ".sh": "Bash(bash:*)", ".js": "Bash(node:*)", ".mjs": "Bash(node:*)"}
SKIP = {"__pycache__", ".git", "node_modules"}
WRITES = re.compile(r"\b(write|writes|save|saves|saved|create|creates|generate|generates|output|publish|"
                    r"render|build|builds)\b[^.\n]{0,60}(\bfile\b|\.html|\.md\b|\.json|\.csv|\.txt|\.pptx|"
                    r"\.docx|\bfolder\b|\bmarkdown\b|\bhtml\b)|--out\b", re.I)
INPUTS = re.compile(r"\b(review|edit|update|read|existing|given|the user's)\b[^.\n]{0,40}"
                    r"(\bfile\b|\.html|\.md\b|\.json|\.csv|\.pdf|\bdeck\b|\bslides\b|\bdocument\b)", re.I)
MCP = re.compile(r"mcp__[\w-]+|\bMCP\b[^.\n]{0,40}|\b(Firecrawl|Slack|Gmail|Google Drive|Salesforce|Notion)\b|"
                 r"\bArtifact tool\b|\bWebFetch\b|\bWebSearch\b", re.I)
COMMON_ENV = {"HOME", "USERPROFILE", "PATH", "NODE_ENV", "TMPDIR", "TEMP", "USER", "SHELL", "PWD", "LANG"}
ENV = re.compile(r"""(?:os\.environ(?:\.get)?[(\[]|getenv\(|process\.env\.)\s*["']?([A-Z][A-Z0-9_]+)""")


def find(arg):
    p = Path(arg).expanduser()
    if p.name == "SKILL.md":
        p = p.parent
    if (p / "SKILL.md").is_file():
        return [p.resolve()]
    name = arg.lstrip("/").split(":")[-1]
    roots = [HOME / ".claude" / "skills", Path.cwd() / ".claude" / "skills"]
    hits = [r / name for r in roots if (r / name / "SKILL.md").is_file()]
    hits += [s.parent for s in (HOME / ".claude" / "plugins").glob(f"**/skills/{name}/SKILL.md")]
    return sorted({h.resolve() for h in hits})


def files(skill):
    return [f for f in skill.rglob("*") if f.is_file() and not SKIP & set(f.relative_to(skill).parts)]


def text_of(fs):
    out = []
    for f in fs:
        if f.suffix in (".md", ".txt", ".py", ".sh", ".js", ".mjs", ".json", ".yaml", ".yml"):
            try:
                out.append((f, f.read_text(encoding="utf-8")))
            except (UnicodeDecodeError, OSError):
                pass
    return out


def hits(rx, texts, limit=4, skip=()):
    """Distinct matches, as 'file: "text"'. A match that names one of `skip` (the skill's own files) is left out."""
    found, seen = [], set()
    for f, t in texts:
        for m in rx.finditer(t):
            g = m.group(0).strip()[:70]
            if g.lower() in seen or any(n in g for n in skip):
                continue
            seen.add(g.lower())
            found.append(f"{f.name}: \"{g}\"")
            if len(found) >= limit:
                return found
    return found


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("skill")
    ap.add_argument("--suite")
    ap.add_argument("--sync", action="store_true", help="the suite exists: refresh its copy of the skill")
    a = ap.parse_args()

    found = find(a.skill)
    if len(found) != 1:
        if found:
            sys.exit("More than one skill matches. Run again with the folder path:\n  " +
                     "\n  ".join(map(str, found)))
        names = sorted(p.parent.name for p in (HOME / ".claude" / "skills").glob("*/SKILL.md"))
        sys.exit(f"No skill named {a.skill}. Skills in ~/.claude/skills: {', '.join(names)}")
    skill = found[0]
    suite = SUITES / (a.suite or f"{skill.name}-eval")

    if suite.exists():
        copies = [p.parent for p in (suite / "skills").glob("*/SKILL.md")]
        if a.sync and len(copies) == 1:
            subprocess.run(["rsync", "-a", "--delete", "--exclude", ".git", f"{skill}/", f"{copies[0]}/"], check=True)
            print(f"Synced {skill} -> {copies[0]}")
            sys.exit(0)
        diff = subprocess.run(["diff", "-rq", "-x", ".git", "-x", "__pycache__", str(skill), str(copies[0])],
                              capture_output=True, text=True).stdout.strip() if len(copies) == 1 else ""
        print(f"SUITE EXISTS: {suite}")
        print("The skill copy matches the installed skill." if not diff else
              f"The skill changed since the copy was made ({len(diff.splitlines())} files differ):\n{diff}")
        sys.exit(2)

    r = subprocess.run([sys.executable, str(KIT / "new.py"), suite.name, "--skill", str(skill)],
                       capture_output=True, text=True)
    if r.returncode:
        sys.exit(r.stderr or r.stdout)

    fs = files(skill)
    texts = text_of(fs)
    # The instructions Claude follows: SKILL.md and the files it names. Nested tools the skill never names
    # (a vendored app, a second skill) do not set tools or permissions.
    top = next(t for f, t in texts if f == skill / "SKILL.md")
    docs = [(f, t) for f, t in texts if f == skill / "SKILL.md" or (f.suffix == ".md" and f.name in top)]
    named = [f for f in fs if f.suffix in RUNNERS and any(f.name in t for _, t in docs)]
    scripts = sorted({f.suffix for f in named})
    writes = hits(WRITES, docs)
    own = {f.name for f in fs}

    add_tools, add_allow, why = ["Read", "Glob"], ["Read", "Glob"], ["Read, Glob: the skill reads its own files"]
    if writes:
        add_tools += ["Write", "Edit"]
        add_allow += ["Write", "Edit"]
        why.append(f"Write, Edit: SKILL.md writes files ({writes[0]})")
    if scripts:
        add_tools.append("Bash")
        add_allow += sorted({RUNNERS[s] for s in scripts})
        why.append(f"Bash: SKILL.md runs {', '.join(sorted(f.name for f in named))} (only those runners are allowed)")

    p = suite / "suite.json"
    s = json.loads(p.read_text())
    s["tools"] = sorted(set(s["tools"]) | set(add_tools))
    for c in s["conditions"].values():
        c["allowed_tools"] = c.get("allowed_tools", []) + [t for t in add_allow if t not in c.get("allowed_tools", [])]
    p.write_text(json.dumps(s, indent=2) + "\n")

    env = sorted({m for f, t in texts if f in named for m in ENV.findall(t)} - COMMON_ENV)
    print(f"SUITE: {suite}")
    print(f"SKILL: {skill} -> copied to {suite}/skills/")
    print(f"TOOLS (both conditions): {', '.join(s['tools'])}")
    print(f"ALLOWED: {', '.join(next(iter(s['conditions'].values()))['allowed_tools'])}")
    print("WHY:\n  " + "\n  ".join(why))
    print("FINDINGS for /evalkit:evalkit-fill:")
    print(f"  env vars the scripts read: {', '.join(env) or 'none'}")
    print("  MCP or external services (the eval runs with --strict-mcp-config, so these are absent): " +
          ("; ".join(hits(MCP, docs)) or "none"))
    print("  input files the prompts may need (fixtures): " + ("; ".join(hits(INPUTS, docs, skip=own)) or "none"))
    print(f"  files in the skill: {len(fs)}")


if __name__ == "__main__":
    main()
