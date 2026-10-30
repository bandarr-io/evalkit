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

## Quick start

1. Run `/evalkit:eval-skill-new <skill-name>`. It copies the skill into a new suite and sets the tools and permissions.
2. Run `/evalkit:evalkit-fill <suite>`. It writes the test conversations and checks, and does a small test run.
3. Run the full suite when the small run looks right. The skill gives you the command and the number of model calls.

Each model call costs money. Use `run.py --dry-run` to see the number of calls before a run.

## The method

A skill is a workflow with steps. Each step is one of three kinds:

- **code**: a script or a fixed rule does the step. The result is the same every time.
- **model**: Claude decides. The result can change from one run to the next.
- **human**: a person judges the result or approves it.

evalkit saves the output of every step to its own file and writes a check for each step.
It uses a code check wherever it can, because a code check gives the same answer every time.
Then it runs the same conversations many times, on more than one model, with and without the skill.
One run tells you what happened once. Many runs tell you how often it happens.

## What `/evalkit:eval-skill-new` does

It does the fixed setup work, so the next skill can start from a suite that runs.

1. It finds the skill: in `~/.claude/skills`, in the current project's `.claude/skills`, or in an installed plugin.
   If it finds no skill or more than one, it shows you the list and asks which one.
2. It copies the skill into the suite. The eval tests this copy, so later edits to the skill do not change a run.
   If the suite exists already, it tells you which files changed and offers to refresh the copy (`--sync`).
3. It writes two conditions with the same tools:
   - `with-skill`: the skill copy is in the test project.
   - `without-skill`: the skill is denied, even if it is installed. This is the baseline.
4. It reads the skill and adds the tools the skill needs to both conditions.
   `Read` and `Glob` always. `Write` and `Edit` if the skill writes files. `Bash` with one run rule for each script type the skill ships.
5. It lists findings for you to settle:
   - environment variables the skill's scripts read (for example, a flag that stops a browser from opening),
   - MCP servers or external services the skill uses (the eval has none),
   - input files the test prompts may need.
6. It validates the suite and shows the number of model calls. Then it offers to start `/evalkit:evalkit-fill`.

## What `/evalkit:evalkit-fill` does

It turns the skeleton into a suite that is ready to run. Claude drafts; you decide what "good" means.

1. **Map the steps.** It splits the skill into its steps and marks each one as code, model, or human.
   For each step it names the evidence (the reply, the session transcript, or files the skill wrote) and how to check it.
   Every suite has a `trigger` step (did Claude pick the skill?) and a `quality` step (you read the replies).
2. **Ask you once.** It asks at most 3 questions, with its drafts as the first options:
   the real requests you use the skill for, what a good and a bad result look like, and which models and how many runs.
3. **Write the conversations.** 2 to 4 conversations, each with 1 to 3 turns. One does not name the skill (to test that Claude picks it).
   One is an edge case from the skill. One has a follow-up turn where the skill's rules can drift.
4. **Write the checks.** One script for each rule it can test in code. Checks measure where they can (counts, lengths, missing sections), not only pass or fail.
5. **Test the checks.** For each check it writes a good and a bad example. The good one must pass and the bad one must fail.
6. **Do a small run.** One model, one run. For each failed check it decides if the reply is wrong or the check is wrong.
   It fixes a wrong check. It does not loosen a check only to make it pass.
7. **Hand over.** It shows the step map, which steps have no code check, what the small run showed, and the command for the full run.
   It does not start the full run unless you ask.

## What a run gives you

Each run writes a folder `suites/<name>/runs/<timestamp>/`:

- `report.md`: one row for each model and condition, with tokens, time, cost, and the check metrics.
  It shows the spread between runs (lower is more consistent) and the main metric for each turn (to show drift in a long conversation).
  It also has the pass rate of each check and the step map.
- `review.md`: the final replies side by side, with and without the skill. This is the human step: read it and decide which reply you want.
- `results.jsonl`: one row for each turn.
- One folder for each turn with the prompt, the reply, the raw result, each check's output, and a copy of the files the skill wrote.

## Isolation

Each conversation runs in a new, empty temp project with only the tools the suite lists.
Your user settings, hooks, and MCP servers do not load.
Your installed skills and plugins do load, and `~/.claude/CLAUDE.md` loads, the same in each condition.
The eval sessions show up in `~/.claude/projects/`, because the checks read those transcripts.

## Where your suites go

Suites and run results go to `~/.claude/evalkit/suites/`. Set `EVALKIT_HOME` to use a different folder.
Plugin updates do not touch this folder.

## Contents

- `plugins/evalkit/skills/eval-skill-new/`: makes a suite for a skill.
- `plugins/evalkit/skills/evalkit-fill/`: fills in the suite's TODOs and tests it.
- `plugins/evalkit/kit/`: the runner, the report, the suite checker, and shared checks. See `kit/README.md` for the suite format,
  to write a suite by hand, or to test a CLAUDE.md rule or a hook in place of a skill.
