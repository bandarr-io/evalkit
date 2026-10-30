---
name: eval-skill-new
description: Create an evalkit suite for a skill (copy, conditions, tools, permissions), ready for /evalkit:evalkit-fill.
argument-hint: <skill-name> [--suite NAME]
disable-model-invocation: true
---

# New eval suite for a skill

The argument names the skill under test. `setup_suite.py` does the fixed work; you read its output, settle the
findings, and hand over to `/evalkit:evalkit-fill`. Paths: `SK` is the base directory shown when this skill loads.
`KIT=SK/../../kit` holds the evalkit scripts.

## 1. Run the setup script

```
python3 SK/setup_suite.py <argument>
```

The exit code picks the branch:

- **0**: the suite is created. Go to step 2.
- **1**: no skill, or more than one. Show the user the script's list and ask which one. Run again with the name or path.
- **2**: the suite exists. If files differ, ask the user: refresh the copy (`--sync`, then stop: the suite is ready
  to run again), or make a second suite (`--suite <skill>-eval-2`). If nothing differs, tell the user to run
  `/evalkit:evalkit-fill <suite>` or `run.py`, and stop.

## 2. Settle the findings

Read the skill's SKILL.md once, then go through each FINDINGS line of the script output:

- **env vars**: for each variable that stops a side effect (opens a browser, sends a message, writes outside the
  project), set it to `1` in the `env` of both conditions in `suite.json`. Add an allow rule for the prefixed
  command too, for example `Bash(MY_VAR=1 python3:*)`: Claude sometimes types the variable in front of the command.
- **MCP or external services**: the eval has no MCP servers. Name each step that needs one; `/evalkit:evalkit-fill` marks it
  as a step with no evidence or writes prompts that avoid it.
- **input files**: note them for `/evalkit:evalkit-fill`, which puts them in `fixtures/`.
- **tools**: compare TOOLS with what SKILL.md tells Claude to do. Add a missing tool to `tools` and to
  `allowed_tools` in both conditions. Keep both conditions the same: the skill is the only difference.

Done when every finding is settled in `suite.json` or named in your hand-over.

## 3. Validate

```
python3 KIT/check_suite.py <suite>      # TODO rows (and the "kind must be" error of the TODO step) are for /evalkit:evalkit-fill; fix any other error
python3 KIT/run.py <suite> --dry-run    # the call count
```

## 4. Hand over

Tell the user: the suite path, the tools and allow rules, each finding and what you did with it, and the call count.
Then ask: "Start /evalkit:evalkit-fill <suite> now?" On a yes, invoke the `evalkit:evalkit-fill` skill with the suite name.
