---
name: clickup-cli
description: Use the clickup CLI to manage ClickUp tasks, comments, docs, folders, lists, spaces, and tags from the command line. JSON output, dry-run support.
---

# ClickUp CLI Skill

You have access to the `clickup` CLI for managing ClickUp workspaces.

## Discovery

Always start by discovering available commands:

```bash
clickup --help                    # list all command groups
clickup <group> --help            # list subcommands in a group
clickup <group> <command> --help  # full usage for a specific command
```

## Safety

Before any mutating command (create, update, delete), use `--dry-run`:

```bash
clickup --dry-run tasks create --space myspace --name "New task"
```

Global flags (`--pretty`, `--dry-run`) can appear before or after the command group.

## Output

- Successful output is always JSON on stdout
- Errors go to stderr with non-zero exit code
- Use `--pretty` for indented JSON when reading output
- Use `--full` on task list/search for raw API response

## Common Workflows

### Find and read a task
```bash
clickup tasks search "login bug" --space myspace
clickup tasks get <task_id>
```

### Create a task
```bash
clickup --dry-run tasks create --space myspace --name "Fix auth" --desc "Details"
clickup tasks create --space myspace --name "Fix auth" --desc "Details"
```

### Add a comment
```bash
clickup comments add <task_id> --text "Work complete"
clickup comments add <task_id> --file report.md
```

### Read and edit docs
```bash
clickup docs list --space myspace
clickup docs pages <doc_id>
clickup docs get-page <doc_id> <page_id>
clickup docs edit-page <doc_id> <page_id> --content-file updated.md
clickup docs edit-page <doc_id> <page_id> --content "New section" --append
```

### Discover workspace structure
```bash
clickup spaces list
clickup folders list --space myspace
clickup lists list --folder <folder_id>
clickup spaces statuses myspace
```

## Configuration

The CLI loads config from (in order):
1. `CLICKUP_CONFIG_PATH` env var
2. `~/.config/clickup-cli/config.json`
3. `clickup-config.json` in current directory

Or use environment variables only:
- `CLICKUP_API_TOKEN` (required)
- `CLICKUP_WORKSPACE_ID` (required without config file)

Run `clickup init` for interactive setup.

## Key Behaviors

- `tasks get` auto-fetches comments (use `--no-comments` to skip)
- `tasks search` auto-detects task ID patterns (e.g. "PROJ-39") and applies prefix filtering
- `tasks create` checks for duplicates before creating (use `--skip-dedup` to bypass)
- Tag names are auto-lowercased (ClickUp API requirement)
- Doc ID ≠ page ID — always use `docs pages` to find page IDs first
