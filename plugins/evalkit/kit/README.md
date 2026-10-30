# evalkit

Test whether a Claude Code setup (a CLAUDE.md rule, a skill, hooks) does what you think, and keeps doing it.

The method: split the workflow into steps, mark each one as **code**, **model**, or **human**,
save every step's output to its own file, write a check for each step, and run it many times on more than one model.

## Where things are

- `KIT`: this folder (the scripts). In the plugin it is `<plugin>/kit/`. A plugin update replaces it.
- `SUITES`: `$EVALKIT_HOME/suites/`, default `~/.claude/evalkit/suites/`. Your suites and run results go here.

## Run

```bash
python3 $KIT/run.py $SUITES/my-suite --dry-run                       # count the calls first
python3 $KIT/run.py $SUITES/my-suite --models haiku --runs 1 --conversations example
python3 $KIT/run.py $SUITES/my-suite                                 # full suite
python3 $KIT/report.py $SUITES/my-suite/runs/<timestamp>             # rebuild the report
```

Each run writes `$SUITES/<name>/runs/<timestamp>/`:

- `report.md`: one line per model x condition, check pass rates, and the step map
- `review.md`: the final replies side by side, for the human step
- `results.jsonl`: one row per turn
- `<model>/<condition>/<conversation>/r<n>/t<turn>/`: `prompt.txt`, `reply.md`, `result.json`, `check-<id>.json`

## Isolation

Every conversation runs in a fresh temp project with `claude -p --setting-sources project --strict-mcp-config`
and only the tools the suite lists.
Your user settings, hooks and MCP servers do not load. Your installed skills and plugins do load, in every condition. `~/.claude/CLAUDE.md` still loads, the same in every condition.
Eval sessions show up in `~/.claude/projects/` (the checks read those transcripts).

## Test a skill

In Claude Code, run `/evalkit:eval-skill-new <skill>`, then `/evalkit:evalkit-fill <suite>`. The skills do the steps below.

`run.py` takes a suite folder, not a skill folder. Create a suite from the skill first:

```bash
python3 $KIT/new.py my-skill-eval --skill ~/.claude/skills/my-skill
# edit $SUITES/my-skill-eval/suite.json: replace every TODO (run.py refuses to start while TODO prompts remain)
python3 $KIT/run.py $SUITES/my-skill-eval --models haiku --runs 1
```

This copies the skill into the suite and compares two conditions with the same tools:
`with-skill` (the copy is in the project) and `without-skill` (the skill is denied, even if it is installed in `~/.claude/skills`).
Checks: `skill-used` passes only when a Skill call for it succeeded; `skill-not-used` confirms the baseline did not use it.
Write prompts that do not name the skill if you also want to test that Claude picks it.

## Write a suite

`suites/<name>/suite.json`:

- `tools`: tools Claude can use (default: none). `allowed_tools` / `disallowed_tools`: permission rules,
  passed as `--allowedTools` / `--disallowedTools` (allow rules in the temp project's settings are ignored).
  A skill needs `"Skill"` in both `tools` and `allowed_tools`.
- `conditions`: each one can set `claude_md` (file copied to the project CLAUDE.md), `settings` (project settings.json),
  `skills_dir` (copied to `.claude/skills`), `env`, and override `tools`, `allowed_tools`, `disallowed_tools`, `permission_mode`.
- `fixtures`: a folder in the suite whose files are copied into every temp project (input files the prompts refer to). A condition can override it.
- `conversations`: lists of turns, sent in one session.
- `checks`: shell commands run after each turn. Exit 0 = pass. JSON on stdout becomes metrics
  (numbers as-is, lists as their length). `only_conditions` / `skip_conditions` limit where a check runs.
  Placeholders: `{reply}`, `{turn_dir}`, `{turn}`, `{session_id}`, `{data}`, `{suite}`, `{condition}`, `{model}`,
  `{workspace}` (the live temp project, for skills that write files; a copy is kept in `t<turn>/workspace/`),
  `{kit}` (the kit folder, for the shared checks in `{kit}/checks/`).
- `steps`: the step map shown in the report.
- `report.primary` and `report.columns`: which metrics go in the table.
