# evalkit

A Claude Code plugin that tests whether a skill does what you think, and keeps doing it.
It runs the same conversations with and without the skill, on more than one model, and checks every step.

## Install

```
/plugin marketplace add bandarr-io/evalkit
/plugin install evalkit@evalkit
```

To try it without installing, clone the repo and run `claude --plugin-dir ./evalkit/plugins/evalkit`.

Requirements: `python3` (standard library only) and the `claude` CLI on the PATH. `run.py` runs `claude -p` once for each turn.

## Use

1. Run `/evalkit:eval-skill-new <skill-name>`. It copies the skill into a new suite and sets the tools and permissions.
2. Run `/evalkit:evalkit-fill <suite>`. It writes the test conversations and checks, and does a small test run.
3. Run the full suite when the small run looks right. The skill gives you the command and the number of model calls.

Each model call costs money. Use `run.py --dry-run` to see the number of calls before a run.

## Where your suites go

Suites and run results go to `~/.claude/evalkit/suites/`. Set `EVALKIT_HOME` to use a different folder.
Plugin updates do not touch this folder.

## Contents

- `plugins/evalkit/skills/eval-skill-new/`: makes a suite for a skill.
- `plugins/evalkit/skills/evalkit-fill/`: fills in the suite's TODOs and tests it.
- `plugins/evalkit/kit/`: the runner, the report, the suite checker, and shared checks. See `kit/README.md` for the suite format.
