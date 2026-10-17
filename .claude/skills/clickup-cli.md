---
name: clickup-cli
description: Use when performing ClickUp work with the local clickup CLI, including tasks, comments, docs, hierarchy, tags, custom fields, task types, relationships, migrations, or workspace lookup.
---

# ClickUp CLI

Use the local Python `clickup` CLI for ClickUp operations. Do not use raw curl or direct API calls unless the CLI is missing the operation and the user explicitly approves a CLI extension or fallback.

**Command:** `clickup <group> <command> [options]`
**Repo:** github.com/efetoker/clickup-cli
**Config:** `~/.config/clickup-cli/config.json`

## Mandatory Workflow Rules

1. **Search before create.** Always run `tasks search "<name>" --space <space> --include-closed --all-pages` before creating a task to avoid duplicates. Every query word must appear in the task name or description; an empty result only proves absence when `results_complete` is true.
2. **Dry-run before every mutation.** Use `--dry-run` before create, update, delete, move, merge, bulk, privacy, docs edit, and hierarchy cleanup commands.
3. **Preview comments before posting.** Show the full comment text locally and get explicit approval before `comments add`, `comments update`, `comments reply`, or `docs edit-page` that posts user-facing text.
4. **Prefer CLI help over memory.** Run `clickup --help`, `clickup <group> --help`, or `clickup <group> <command> --help` when unsure.
5. **Back up before migrations.** For bulk moves, tag migrations, list/folder cleanup, or hierarchy deletion, create a backup or dry-run proof first.
6. **Extend, do not bypass.** If the CLI lacks a needed operation, suggest adding a command under `src/clickup_cli/commands/`.
7. **Strict tags when adding tags.** ClickUp silently creates a Space tag when an unknown tag is added to a task. Pass `--strict-tags` on `tasks create --tag`, `tasks update --add-tag`, `tags add`, and `tasks bulk tags` unless the config already sets `"strict_tags": true`. Create a missing tag deliberately with `tags create`; never rely on implicit creation.

Global flags such as `--pretty`, `--dry-run`, and `--debug` can appear before or after the command group.

## Output

- Successful output is JSON on stdout; errors go to stderr with a non-zero exit code.
- Use `--pretty` for indented JSON when reading output.
- On `tasks list` and `tasks search`, default output is compact (id, name, status, priority, url). Use `--full` for full task objects with a normalized status shape, or `--fields id,name,url` for a custom shape.

## Command Groups Quick Reference

| Group | Key subcommands |
|-------|-----------------|
| `init` | interactive setup |
| `tasks` | `list`, `get`, `create`, `update`, `search`, `delete`, `move`, `merge`, `lists`, `add-to-list`, `remove-from-list`, `bulk`, `link`, `depend` |
| `comments` | `list`, `add`, `update`, `delete`, `thread`, `reply` |
| `docs` | `list`, `get`, `create`, `pages`, `get-page`, `edit-page`, `create-page` |
| `fields` | `list` |
| `folders` | `list`, `get`, `create`, `update`, `delete`, `backup`, `purge-empty`, `privacy` |
| `lists` | `list`, `get`, `create`, `update`, `delete`, `backup`, `privacy` |
| `spaces` | `list`, `get`, `create`, `update`, `delete`, `statuses`, `privacy` |
| `team` | `whoami`, `members` |
| `tags` | `list`, `create`, `edit`, `migrate`, `delete`, `usage`, `add`, `remove` |
| `task-types` | `list` |

## Task Workflow

```bash
# 1. Search first
clickup tasks search "PER-32" --pretty
clickup tasks search "feature name" --space <space> --pretty

# If search returns candidates, inspect each before acting
clickup tasks get <task_id> --pretty

# 2. Discover exact status names and metadata
clickup spaces statuses <space> --pretty
clickup fields list --space <space> --pretty
clickup task-types list --pretty

# 3. Create with dry-run first
clickup --dry-run tasks create --space <space> --name "Title" --desc-file /tmp/desc.md --priority normal
clickup tasks create --space <space> --name "Title" --desc-file /tmp/desc.md --priority normal
clickup --dry-run tasks create --space <space> --name "Bug" --custom-field <field_uuid>=high --task-type <task_type_id>
clickup tasks create --space <space> --name "Subtask" --parent <parent_task_id>

# 4. Update with dry-run first
clickup --dry-run tasks update <task_id> --status "in progress"
clickup tasks update <task_id> --status "in progress"
clickup --dry-run tasks update <task_id> --custom-field <field_uuid>=done

# 5. Clear fields deliberately when requested
clickup --dry-run tasks update <task_id> --clear-priority
clickup tasks update <task_id> --clear-priority
```

Use `--list <list_id>` for a specific list. Use `--space <name>` for the configured default Tasks list in that space.

## Common Workflows

### Find and read a task
```bash
clickup tasks search "login bug" --space <space>
clickup tasks get <task_id>
```
Search is client-side and case-insensitive: every query word must appear in the name or description. Comments are not searched, and there is no phrase, regex, or fuzzy syntax. An empty query (`tasks search ""`) matches all tasks and pairs well with filters.

### Filter tasks
```bash
clickup tasks list --space <space> --include-closed --all-pages --untagged
clickup tasks search "" --space <space> --exclude-tag draft --exclude-tag done
clickup tasks list --space <space> --due-before 2026-10-20 --due-after 2026-10-13
clickup tasks list --space <space> --overdue
```
`--untagged` cannot combine with `--tag`. Date bounds use the local timezone and exclude the boundary day itself. `--overdue` means due before now and not done or closed. Tasks without a due date never match a date filter. All filters run before `--limit`.

### Discover custom fields and task types
```bash
clickup fields list --space <space>          # returns fields, count, scope
clickup fields list --list <list_id>         # use for folder-contained lists
clickup fields list --space <space> --space-level   # fields defined on the Space
clickup fields list --folder <folder_id>     # fields defined on a Folder
clickup fields list --workspace              # fields defined on the Workspace
clickup task-types list                      # workspace-level task types
```
The `--space-level`, `--folder`, and `--workspace` scopes are not recursive; they do not include fields created on lower levels.
`fields list --space` inspects the configured default list for that space, or the first folderless list if no default `list_id` is configured. `task-types list` is workspace-scoped; any `--space` or `--list` value is echoed for workflow context but does not filter the API result (`scope_applied: false`).

### Update a task (including tags, assignees, custom fields)
```bash
clickup tasks update <task_id> --status "in progress"
clickup tasks update <task_id> --add-tag urgent --remove-tag draft --strict-tags
clickup tasks update <task_id> --add-assignee <user_id>
clickup tasks update <task_id> --custom-field <field_uuid>=high
clickup --dry-run tasks update <task_id> --add-tag urgent --strict-tags  # returns a plan
clickup tasks update <task_id> --archive        # or --unarchive
clickup --dry-run tasks bulk archive --task-file ids.txt
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
clickup tasks list --space <space> --include-archived
clickup tasks search "bug" --include-archived
```

### Add a comment
```bash
clickup comments add <task_id> --text "Work complete"
clickup comments add <task_id> --file report.md
```

### Read and edit docs
```bash
clickup docs list --space <space>
clickup docs pages <doc_id>
clickup docs get-page <doc_id> <page_id>
clickup docs edit-page <doc_id> <page_id> --content-file updated.md
clickup docs edit-page <doc_id> <page_id> --content "New section" --append
```

### Discover workspace structure
```bash
clickup spaces list
clickup folders list --space <space>
clickup lists list --folder <folder_id>
clickup spaces statuses <space>
```

### Toggle privacy on a space, folder, or list
```bash
clickup spaces privacy <space> --private
clickup folders privacy <folder_id> --public
clickup lists privacy <list_id> --private
clickup --dry-run lists privacy <list_id> --private  # preview body
```
Each command requires exactly one of `--private` / `--public`. This flips the private/public boolean only — granular member or guest grants must be done in the ClickUp UI. Hits the v3 ACLs endpoint.

## Relationships, Lists, And Tags

- Use `tasks link` for non-blocking related tasks.
- Use `tasks depend` for blocking dependencies.
- Use `tasks move` to change the home list.
- Use `tasks add-to-list` or `tasks remove-from-list` for multi-list membership.
- Use `tasks update --add-tag/--remove-tag` or `tags add/remove` for task-level tags.
- Use `tags create`, `tags delete`, and `tags usage` for Space-level tag lifecycle and audits.
- Use `tags edit --space <space> --tag <old> --name <new>` for a 1:1 rename or a recolor (`--fg-color`/`--bg-color`). Tasks pick up the new name immediately. Renaming onto an existing tag fails.
- Use `tags migrate --space <space> --map map.json` to merge or drop tags across the whole Space. The map is `{"source": ["target", ...], "drop-me": []}`; every source and target must already exist, and sources cannot also be targets.

## Migration Safety

For hierarchy and bulk changes:

```bash
clickup lists backup <list_id> --output-dir ./backup/list-<list_id>
clickup folders backup <folder_id> --output-dir ./backup/folder-<folder_id>
clickup --dry-run tasks bulk move --task-file ids.txt --to <space-or-list-id>
clickup --dry-run folders purge-empty <folder_id>
clickup --dry-run tags migrate --space <space> --map map.json --delete-old
```

`tags migrate` always scans closed tasks, archived lists and tasks, and subtasks, and refuses to run on an incomplete scan. Its dry-run lists every task and operation. `--delete-old` deletes source tags only after a fresh scan shows zero usage and only if every task operation succeeded. There is no rollback: on failure, read `failed`, `remaining`, `resume_from`, and `pending_space_tag_deletions`, then dry-run the map again for a fresh plan.

Prefer backup plus dry-run over manual destructive cleanup. For empty folder cleanup, prefer `folders purge-empty` over ad hoc deletes because it is purpose-built for safe cleanup.

## Edge Cases And Critical Rules

| Situation | Rule |
|-----------|------|
| Description has special chars or is long | Use `--desc-file /tmp/file.md`, not `--desc` |
| Comment has special chars or is long | Use `--file /tmp/comment.md`, not `--text` |
| Custom field values | Discover UUIDs with `fields list`; pass `--custom-field <field_uuid>=<value>` |
| Task type names or IDs | Discover with `task-types list` before `tasks create --task-type ...` |
| Status string rejected | Run `clickup spaces statuses <space>` and use the exact string |
| Search returns multiple results | Run `tasks get <id>` on each candidate before acting |
| Task ID search | `tasks search "PER-32"` auto-applies ID-like prefix filtering |
| Subtasks hidden | Use `tasks search "parent name"` or `--subtasks` when help shows it is available |
| Mutually exclusive content flags | Use one of `--desc`/`--desc-file`, `--text`/`--file`, or `--content`/`--content-file` |
| Privacy changes | Dry-run first; granular member/guest ACLs belong in the ClickUp UI unless the CLI explicitly supports them |
| Bounded scans | `tasks list`/`search` default to a bounded scan; use `--all-pages` for exhaustive results and `--limit N` to cap output |
| Tag audits | `tags usage <space>` audits one tag with `--tag`, or every tag without it; add `--include-closed`/`--include-archived`/`--subtasks` for exhaustive checks |
| Bulk operations | `tasks bulk move`, `tasks bulk tags`, `tasks bulk archive`, and `tags migrate` are dry-run friendly and stop on first failure by default |
| Unknown tag on add | ClickUp creates it silently; use `--strict-tags` (or config `strict_tags: true`) so the command fails before any change |
| Rename vs merge | `tags edit --name` for a 1:1 rename; `tags migrate` when the target tag already exists or several tags merge into one |
| Dry-run made GET requests | Expected for `tags edit`, `tags migrate`, strict checks, and scope resolution; dry-run never sends mutating requests |

## Configuration

Use `clickup init` for interactive setup. For config file shape, resolution order, and contributor-facing setup notes, prefer `README.md` and `CONTRIBUTING.md` over this repo-local skill.

## Key Behaviors

- `tasks get` auto-fetches comments (use `--no-comments` to skip)
- `tasks search` matches every query word against names and descriptions, and auto-detects task ID patterns (e.g. "PROJ-39") to apply prefix filtering
- `tasks create` accepts `--space` or `--list`; when only `--list` is provided, the CLI auto-infers the matching configured space alias before resolving the target list
- Use `fields list` before `--custom-field FIELD_ID=VALUE` flows, and `task-types list` before `--task-type` flows
- Tag names are auto-lowercased (ClickUp API requirement)
- Doc ID ≠ page ID — always use `docs pages` to find page IDs first
