---
name: clickup-cli
description: Use the clickup CLI to manage ClickUp tasks, comments, docs, folders, lists, spaces, tags, custom fields, and task types from the command line. JSON output, dry-run support.
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
clickup --dry-run tasks create --space <space_name> --name "New task"
```

Global flags (`--pretty`, `--dry-run`, `--debug`) can appear before or after the command group.

## Output

- Successful output is always JSON on stdout
- Errors go to stderr with non-zero exit code
- Use `--pretty` for indented JSON when reading output
- On `tasks list` and `tasks search`, default output is compact; `--full` returns full task objects, while `--fields` lets you request a smaller custom shape

## Common Workflows

### Find and read a task
```bash
clickup tasks search "login bug" --space <space_name>
clickup tasks get <task_id>
```

### Create a task
```bash
clickup --dry-run tasks create --space <space_name> --name "Fix auth" --desc "Details"
clickup tasks create --space <space_name> --name "Fix auth" --desc "Details"
clickup tasks create --list <list_id> --name "Fix auth" --desc "Details"
```

### Discover custom fields and task types
```bash
clickup fields list --space <space_name>          # returns fields, count, scope
clickup fields list --list <list_id>              # use for folder-contained lists
clickup task-types list                           # workspace-level task types
```
`fields list --space` inspects the configured default list for that space, or
the first folderless list if no default `list_id` is configured. `task-types
list` is workspace-scoped; any `--space` or `--list` value is echoed for
workflow context but does not filter the API result (`scope_applied: false`).

### Update a task (including tags, assignees, custom fields)
```bash
clickup tasks update <task_id> --status "in progress"
clickup tasks update <task_id> --add-tag urgent --remove-tag draft
clickup tasks update <task_id> --add-assignee <user_id>
clickup tasks update <task_id> --custom-field <field_uuid>=high
clickup --dry-run tasks update <task_id> --add-tag urgent  # returns a plan
```

### Manage task dependencies
```bash
clickup tasks depend add <task_id> --depends-on <blocker_task_id>
clickup tasks depend add <task_id> --depended-on-by <blocked_task_id>
clickup tasks depend list <task_id>
clickup tasks depend remove <task_id> --depends-on <blocker_task_id>
```

### See archived tasks alongside live ones
```bash
clickup tasks list --space <space_name> --include-archived
clickup tasks search "bug" --include-archived
```

### Add a comment
```bash
clickup comments add <task_id> --text "Work complete"
clickup comments add <task_id> --file report.md
```

### Read and edit docs
```bash
clickup docs list --space <space_name>
clickup docs pages <doc_id>
clickup docs get-page <doc_id> <page_id>
clickup docs edit-page <doc_id> <page_id> --content-file updated.md
clickup docs edit-page <doc_id> <page_id> --content "New section" --append
```

### Discover workspace structure
```bash
clickup spaces list
clickup folders list --space <space_name>
clickup lists list --folder <folder_id>
clickup spaces statuses <space_name>
```

### Toggle privacy on a space, folder, or list
```bash
clickup spaces privacy <space_name> --private
clickup folders privacy <folder_id> --public
clickup lists privacy <list_id> --private
clickup --dry-run lists privacy <list_id> --private  # preview body
```
Each command requires exactly one of `--private` / `--public`. This flips the
private/public boolean only — granular member or guest grants must be done in
the ClickUp UI. Hits the v3 ACLs endpoint.

## Configuration

Use `clickup init` for interactive setup. For config file shape, resolution order, and contributor-facing setup notes, prefer `README.md` and `CONTRIBUTING.md` over this repo-local skill.

## Key Behaviors

- `tasks get` auto-fetches comments (use `--no-comments` to skip)
- `tasks search` auto-detects task ID patterns (e.g. "PROJ-39") and applies prefix filtering
- `tasks create` accepts `--space` or `--list`; when only `--list` is provided, the CLI auto-infers the matching configured space alias before resolving the target list
- Use `fields list` before `--custom-field FIELD_ID=VALUE` flows, and `task-types list` before `--task-type` flows
- Tag names are auto-lowercased (ClickUp API requirement)
- Doc ID ≠ page ID — always use `docs pages` to find page IDs first
