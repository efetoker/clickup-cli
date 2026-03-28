---
name: add-command
description: Step-by-step workflow for adding a new CLI command to clickup-cli, with verification at each step.
---

# Add a New CLI Command

Follow these steps in order when adding a new command or subcommand.

## 1. Create or extend the command handler

- If this is a new command group, create `src/clickup_cli/commands/<group>.py`
- If extending an existing group, add the handler function to the existing file
- Handler signature: `def cmd_<group>_<command>(client, args):`
- Return a dict (will be output as JSON)
- Mutating commands must check `client.dry_run` and return a dry-run preview instead of calling the API

## 2. Register the handler

- Open `src/clickup_cli/commands/__init__.py`
- Import the new handler function
- Add it to the `HANDLERS` dict with key `"<group>_<command>"`

## 3. Add the subparser in cli.py

- Open `src/clickup_cli/cli.py`
- Find the command group's section (or create a new group with `subs.add_parser()`)
- Add the subparser with:
  - `description=` — what this command does
  - `epilog=` — usage examples (at least 2)
  - `formatter_class=argparse.RawDescriptionHelpFormatter`
- Add all arguments with `help=` text
- For mutating commands, `--dry-run` is handled globally (no per-command flag needed)

## 4. Write help text

- The `--help` output must be self-sufficient for an agent to use the command correctly
- Include concrete examples in the epilog
- Never use real workspace IDs, space names, or tokens in examples — use `<placeholders>`

## 5. Add tests

- Open `tests/test_cli.py` (or create a new test file if the group is large)
- Test argument parsing (parser accepts the new args)
- Test dry-run behavior (mutating commands return dry-run preview)
- Test core logic with `FakeClient`

## 6. Verify

Run these commands and confirm all pass before considering the work done:

```bash
# Lint
ruff check src/ tests/

# Tests
pytest -v

# Help text renders correctly
clickup <group> <command> --help

# Validate CLI output contract
scripts/validate-cli-output.sh
```

## 7. Update the skill (if needed)

If the new command adds a new workflow pattern, update `.claude/skills/clickup-cli.md` with a usage example.
