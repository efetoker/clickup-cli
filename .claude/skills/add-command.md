---
name: add-command
description: Step-by-step workflow for adding a new CLI command to clickup-cli, with verification at each step.
---

# Add a New CLI Command

`CONTRIBUTING.md#adding-a-new-command` is the canonical workflow. Follow it first; keep this skill as an agent-focused reminder instead of a second source of truth.

## Agent Reminders

- Use `src/clickup_cli/commands/<group>.py` for the parser and handlers, except `tasks`, which keeps parser/read/write internals under `src/clickup_cli/commands/tasks_internal/` behind the public facade.
- Expose or update `COMMAND_MANIFEST`; new groups must be imported into `COMMAND_MANIFESTS` in `src/clickup_cli/commands/__init__.py`.
- Do not hand-edit `HANDLERS`; it is derived from manifests.
- Use `add_id_argument()` for positional IDs so both positional and `--flag` forms work.
- Make `--help` self-sufficient with examples, return-shape notes, and dry-run guidance for mutating commands.
- Add focused tests in the relevant split test module under `tests/`; use `tests/test_commands_metadata.py` for `fields` and `task-types`.
- If the command adds a new workflow pattern, update `.claude/skills/clickup-cli.md` with a usage example.

## Verification

Run the standard contributor checks from `CONTRIBUTING.md`:

```bash
pytest -v
ruff check src/ tests/
scripts/validate-cli-output.sh
```
