---
name: evalkit-fill
description: Fill in the TODOs of an evalkit suite (suites/<name>/suite.json) - test conversations, step map, checks and report - then validate it and do a small test run. Use when the user wants to finish, fill out, or complete an eval suite, or after `new.py` created one.
---

# Fill an evalkit suite

Turn a suite skeleton from `new.py` into a suite that is ready to run. Follow the method in evalkit's README:
map the workflow into steps, mark each step as code, model or human, and give each step a check.
Use code for a check wherever you can. The user decides what "good" means; you draft, they confirm.

Paths: `KIT` is `../../kit` from the base directory shown when this skill loads; it holds the evalkit scripts.
`SUITES` is `$EVALKIT_HOME/suites/` (default `~/.claude/evalkit/suites/`). The suite is `SUITES/<name>/`.

## 1. Find the suite

- If the user named a suite or path, use it. Otherwise run `python3 KIT/check_suite.py` on each folder in
  `SUITES` and pick the ones that are not ready. If more than one, ask which one.
- Run `python3 KIT/check_suite.py <suite>`. This is the list of TODOs and errors you must clear.

## 2. Read before you draft

- `suite.json`, and every file in the suite's `skills/` folder (SKILL.md and the files it references).
- `KIT/README.md` for the suite format and the check contract.
- If the suite tests something other than a skill (a CLAUDE.md rule, hooks), read the files its conditions point to.

## 3. Map the steps

Split what is under test into its steps, in order. For each step, decide:

- **kind**: `code` (a script or fixed rule does it; same result every time), `model` (Claude decides; results vary),
  or `human` (a person judges or approves).
- **evidence**: what file shows the step happened: `reply.md`, the transcript (`~/.claude/projects/*/{session_id}.jsonl`),
  or files in `{workspace}` (a skill that writes files needs `Write` or `Edit` in `tools` and `allowed_tools`).
- **check**: how to tell if it went right.

Always include, for a skill: `trigger` (model: Claude picks the skill; check `skill-used`) and
`quality` (human: `review.md`). If a step leaves no evidence, say so in the step's `check` text. Do not invent a check.

## 4. Ask the user only what you cannot infer

Use AskUserQuestion once, with at most 3 questions. Offer your drafts as the first options. Ask about:

- The real requests they use this for (offer 3 drafted prompts; they can replace them).
- What a good result must have, and what a bad one looks like (offer the rules you found in SKILL.md).
- Scope: models and runs (offer: haiku + sonnet, 5 runs, and show the call count from `run.py --dry-run`).

Do not ask about anything in SKILL.md, the README or suite.json.

## 5. Write the suite

- **description**: one sentence, the question this eval answers.
- **conversations**: 2 to 4, each 1 to 3 turns, from the user's real requests. Include:
  one that does not name the skill (tests the trigger), one edge case from SKILL.md, and a follow-up turn
  where the skill's rules could drift. Keep prompts self-contained: Claude runs in an empty temp folder.
  If the prompts need input files, put them in `suites/<name>/fixtures/` and set `"fixtures": "fixtures"`;
  they are copied into the temp folder, so prompts refer to them by plain name. Add `Read` to `tools` and `allowed_tools`.
  Do not ask Claude to read files outside the temp folder.
- **checks**: one script per rule you can test in code, in `suites/<name>/checks/<id>.py`.
  Contract: read the files given as arguments; print one JSON object (numbers become metrics, lists become counts);
  exit 0 for pass. Pass paths in `cmd` with placeholders (`{suite}`, `{reply}`, `{workspace}`, `{session_id}`, `{turn}`).
  Use `only_conditions` when a check only makes sense for one condition.
  Prefer checks that measure (counts, lengths, present or missing sections) over yes/no.
- **steps**: the map from step 3; set each step's `check` to the check ids that cover it.
- **report**: `primary` = the one metric that best answers the description; `columns` = 2 to 5 metrics.
- Keep the `skills/` copy and the conditions as they are, unless the user asks. They are what is under test.

## 6. Test the checks before the model runs

For each check script, write a good and a bad example in a temp folder and run the script on both.
The good one must pass and the bad one must fail. Fix the script until it does. Delete the examples.

## 7. Validate and do a small test run

1. `python3 KIT/check_suite.py <suite>` until it says `ready to run`. Fix errors; tell the user about warnings.
2. `python3 KIT/run.py <suite> --dry-run`, and tell the user the call count.
3. With the user's OK, run `python3 KIT/run.py <suite> --models haiku --runs 1` (cheap).
4. Read `report.md`, then open the artifacts of every failed check: `t<n>/reply.md`, `t<n>/check-<id>.json`,
   `t<n>/workspace/`. Decide for each: is the reply wrong, or is the check wrong? Fix a wrong check and re-run.
   Do not loosen a check only to make it pass.

## 8. Hand over

Tell the user, briefly:
- the step map (step, kind, check) and which steps have no code check,
- what the small run showed, and any check you fixed,
- the command and call count for the full run. Do not start the full run unless the user asks.
