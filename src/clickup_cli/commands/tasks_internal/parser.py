"""Task parser registration implementation."""

from ...helpers import add_id_argument


def register_parser(subparsers, F):
    """Register all tasks subcommands on the given subparsers object."""
    tasks_parser = subparsers.add_parser(
        "tasks",
        formatter_class=F,
        help="Full task CRUD: list, get, create, update, search, delete, move, merge, lists, add-to-list, remove-from-list, link, depend",
        description="""\
Manage ClickUp tasks — full CRUD plus search, move, merge, links, and dependencies.

Subcommands:
  list    — list tasks in a list or space (paginated internally)
  get     — fetch one task by ID
  create  — create a new task in a list or space (mutating)
  update  — update fields on an existing task (mutating)
  search  — search tasks by query across workspace or within a space
  delete  — delete a task (destructive)
  move    — move a task to a different list/space (mutating, v3)
  merge   — merge source tasks into a target task (mutating)
  lists   — inspect the lists a task belongs to
  add-to-list        — add a task to an additional list (mutating)
  remove-from-list   — remove a task from an additional list (mutating)
  link    — manage linked-task relationships (mutating/read)
  depend  — manage dependency relationships (mutating/read)

Tasks live in lists. Each space has a default list, but you can also
target a specific list (e.g. one inside a folder) using --list <id>.
Use 'folders list' and 'lists list' to discover list IDs.

Does not cover: checklists, time tracking, or attachments. Use `tasks search --custom-field`
for custom-field filtering and Phase 10+ flows for custom-field mutation on create.""",
        epilog="""\
examples:
  clickup tasks list --space <name>
  clickup tasks list --list 12345
  clickup tasks get abc123
  clickup --dry-run tasks create --space <name> --name "New feature"
  clickup tasks create --space <name> --list 12345 --name "In a folder list"
  clickup tasks search "login bug" --space <name>
  clickup tasks list --space <name> --subtasks
  clickup tasks search "bug" --list 12345""",
    )
    tasks_sub = tasks_parser.add_subparsers(dest="command", required=True)

    # tasks list
    tl = tasks_sub.add_parser(
        "list",
        formatter_class=F,
        help="List tasks in a list or space",
        description="""\
List all tasks in a list. Results are paginated internally and returned
as a single JSON object with a tasks array and count.

By default, output is compact (id, name, status, priority, url).
Use --full for the full task objects returned by the API, with status
normalized to a consistent dict shape, or --fields to pick specific fields.

Target the list using --space (uses the space's default list) or
--list (targets a specific list ID, e.g. one inside a folder).
If both are given, --list takes precedence.

Use --subtasks to include nested child tasks in the results. Without it,
only top-level tasks are returned (ClickUp API default).

Use this when you need to see all tasks, optionally filtered by status
or including closed tasks.

Use --tag to filter by tag name (API-level filtering, exact match).""",
        epilog="""\
returns:
  {"tasks": [...], "count": N}

examples:
  clickup tasks list --space <name>
  clickup tasks list --space <name> --full
  clickup tasks list --space <name> --fields id,name,url
  clickup tasks list --space <name> --include-closed
  clickup tasks list --space <name> --include-archived
  clickup tasks list --space <name> --status "in progress"
  clickup tasks list --space <name> --subtasks
  clickup tasks list --space <name> --tag "created by claude"

notes:
  Output is compact by default (id, name, status, priority, url).
  Use --full for full task objects with normalized status shape, or --fields
  for custom field selection.
  At least one of --space or --list is required.
  If both are given, --list takes precedence.
  Use --subtasks to include nested child tasks (e.g. Epic/Story/Task hierarchies).
  Use 'lists list --folder <id>' or 'lists list --space <name>' to
  discover list IDs for lists inside folders.
  Status values are space-specific. Check the space configuration
  for valid status names before filtering.""",
    )
    tl.add_argument(
        "--space",
        metavar="SPACE_NAME_OR_ID",
        type=str,
        help="Space name (from config) or raw space ID — uses the space's default list",
    )
    tl.add_argument(
        "--list",
        type=str,
        dest="list_id",
        help="Raw list ID — targets a specific list (overrides --space)",
    )
    tl.add_argument(
        "--include-closed",
        action="store_true",
        help="Include closed/completed tasks in results",
    )
    tl.add_argument(
        "--include-archived",
        action="store_true",
        dest="include_archived",
        help="Include archived tasks (makes a second API call and merges results)",
    )
    tl.add_argument(
        "--status", type=str, help="Filter tasks by status name (space-specific)"
    )
    tl.add_argument(
        "--subtasks",
        action="store_true",
        help="Include subtasks (nested child tasks) in results",
    )
    tl.add_argument(
        "--tag",
        type=str,
        action="append",
        dest="tags",
        help="Filter by tag name (repeatable, API-level, auto-lowercased)",
    )
    tl.add_argument(
        "--fields",
        type=str,
        help="Comma-separated list of fields to return per task (e.g. id,name,status,url)",
    )
    tl.add_argument(
        "--full",
        action="store_true",
        help="Return full task objects, with status normalized to a dict shape (default is compact: id, name, status, priority, url)",
    )
    tl.add_argument(
        "--all-pages",
        action="store_true",
        help="Fetch every task page instead of the default bounded aggregate scan",
    )

    # tasks get
    tg = tasks_sub.add_parser(
        "get",
        formatter_class=F,
        help="Fetch one task by ID (includes comments by default)",
        description="""\
Fetch a single task by its ClickUp task ID.

By default, the first comment page is fetched and appended to the task
output under a "comments" key (array of {id, comment_text, user, date})
and a "comment_count" field. Completeness metadata shows whether that
comment slice is complete or truncated.

Use --all-comments to fetch every comment page explicitly, or
--no-comments to suppress comment fetching if output is too verbose or
you only need the task fields.""",
        epilog="""\
returns:
  One task JSON object with all fields, plus:
    "comments": [{id, comment_text, user, date}, ...]
    "comment_count": N

  Also includes: "comment_count_returned", "comments_complete",
  and "comments_truncated".

  With --no-comments, returns the raw task object without comments.

examples:
  clickup tasks get abc123
  clickup tasks get abc123 --fields id,name,status,url
  clickup tasks get abc123 --full --no-comments
  clickup --pretty tasks get abc123
  clickup tasks get abc123 --no-comments""",
    )
    add_id_argument(tg, "task_id", "ClickUp task ID")
    comment_mode = tg.add_mutually_exclusive_group()
    comment_mode.add_argument(
        "--no-comments",
        action="store_true",
        help="Skip comment hydration and return the raw task object",
    )
    comment_mode.add_argument(
        "--all-comments",
        action="store_true",
        help="Fetch every comment page instead of the default bounded slice",
    )
    output_shape = tg.add_mutually_exclusive_group()
    output_shape.add_argument(
        "--fields",
        type=str,
        help="Comma-separated list of fields to return (e.g. id,name,status,url)",
    )
    output_shape.add_argument(
        "--full",
        action="store_true",
        help="Return the full task payload explicitly (default behavior for tasks get)",
    )

    # tasks create
    tc = tasks_sub.add_parser(
        "create",
        formatter_class=F,
        help="Create a new task in a list or space",
        description="""\
Create a new task in a list. This is a mutating command.

Provide --space to use that space's default list, or --list to target a
specific list directly (e.g. one inside a folder). When --list is provided,
the CLI can infer --space automatically.

Use --desc for inline text or --desc-file for file-based content.
Do not use both at the same time.

Phase 10 fields are supported directly on create: start/due dates,
time estimate, points, repeatable --custom-field values, and explicit
task/custom item type selection.

Use --dry-run to preview the request body without creating the task.
Global flags may appear before or after the command group:
  clickup --dry-run tasks create --space <name> --name "My task"
  clickup tasks create --space <name> --name "My task" --dry-run""",
        epilog="""\
returns:
  The created task object from the API.

examples:
  clickup tasks create --space <name> --name "Add login page"
  clickup tasks create --space <name> --name "Fix bug" --desc "Details here"
  clickup tasks create --space <name> --list 12345 --name "In folder list"
  clickup tasks create --space <name> --name "Read article" --desc-file notes.md
  clickup tasks create --space <name> --name "Kickoff" --start-date 2026-04-21 --due-date 2026-04-24
  clickup tasks create --space <name> --name "Estimate" --time-estimate 90m --points 3
  clickup tasks create --space <name> --name "Bug" --custom-field field-1=high --task-type type-1
  clickup tasks create --space <name> --name "Bug" --tag urgent --tag backend

notes:
  Provide either --space or --list.
  If --list is given, the task is created in that list instead of the
  space's default list, and --space can usually be omitted.
  --desc and --desc-file are mutually exclusive. Using both is an error.
  --assign assigns the task to a user ID.
  --custom-field uses FIELD_ID=VALUE and is repeatable.
  --tag is repeatable, auto-lowercased, and applied after task creation.
  --task-type accepts a task/custom item type ID from `task-types list`.
  Does not support: checklists or attachments.""",
    )
    tc.add_argument(
        "--space",
        metavar="SPACE_NAME_OR_ID",
        type=str,
        help="Target space name or raw ID (auto-inferred from --list if omitted)",
    )
    tc.add_argument(
        "--list",
        type=str,
        dest="list_id",
        help="Raw list ID — creates task in this list (overrides space default)",
    )
    tc.add_argument(
        "--name",
        required=True,
        help="Task title (required)",
    )
    tc.add_argument(
        "--desc",
        type=str,
        help="Inline description text (mutually exclusive with --desc-file)",
    )
    tc.add_argument(
        "--desc-file", type=str, help="Path to a file containing description content"
    )
    tc.add_argument("--status", type=str, help="Initial task status (space-specific)")
    tc.add_argument(
        "--priority",
        type=str,
        help="Priority: urgent, high, normal, low (default: from config)",
    )
    tc.add_argument(
        "--assign",
        type=str,
        dest="assign_user",
        help="Assign to a user ID",
    )
    tc.add_argument(
        "--start-date",
        type=str,
        help="Task start date in YYYY-MM-DD format",
    )
    tc.add_argument(
        "--due-date",
        type=str,
        help="Task due date in YYYY-MM-DD format",
    )
    tc.add_argument(
        "--time-estimate",
        type=str,
        help="Time estimate like 90m, 2h, or 1d",
    )
    tc.add_argument(
        "--points",
        type=str,
        help="Sprint points as a number",
    )
    tc.add_argument(
        "--custom-field",
        dest="custom_fields",
        action="append",
        metavar="FIELD_ID=VALUE",
        help="Custom field to set after create (repeatable, format: field_uuid=value)",
    )
    tc.add_argument(
        "--tag",
        dest="tags",
        action="append",
        help="Tag to apply after create (repeatable, auto-lowercased)",
    )
    tc.add_argument(
        "--task-type",
        type=str,
        help="Task/custom item type ID from `task-types list`",
    )

    # tasks update
    tu = tasks_sub.add_parser(
        "update",
        formatter_class=F,
        help="Update fields on an existing task (core, assignees, tags, custom fields)",
        description="""\
Update one or more fields on an existing task. This is a mutating command.

Core fields are sent in one PUT request: --name, --status, --priority,
--desc / --desc-file, plus assignee diffs (--add-assignee / --remove-assignee).

Tag changes run as extra POST/DELETE calls (one per tag) because the
ClickUp API handles tags on a per-task endpoint.

Custom fields run as extra POST calls (one per field) for the same reason.
Format: --custom-field FIELD_ID=VALUE — repeat for multiple fields.

At least one mutable operation is required — otherwise the command exits
with an error. All operations are gated by --dry-run: in dry-run mode the
command returns a structured plan and makes no API calls.

Global flags may appear before or after the command group:
  clickup --dry-run tasks update abc123 --status "complete" """,
        epilog="""\
returns:
  On live runs: the updated task object returned by the final PUT
  (or the task as of the last mutation if no PUT was issued).
  On --dry-run: a structured plan describing the PUT body and each
  side-effect call that would run.

examples:
  clickup tasks update abc123 --name "Renamed task"
  clickup tasks update abc123 --status "complete"
  clickup tasks update abc123 --add-tag "in review" --remove-tag "draft"
  clickup tasks update abc123 --add-assignee 12345 --remove-assignee 67890
  clickup tasks update abc123 --custom-field abc-uuid=high --custom-field xyz-uuid=42
  clickup --dry-run tasks update abc123 --add-tag urgent

notes:
  --desc and --desc-file are mutually exclusive. Using both is an error.
  Tag names are auto-lowercased.
  --custom-field values are sent as strings; the ClickUp API coerces
  them to the field's declared type.""",
    )
    add_id_argument(tu, "task_id", "ClickUp task ID to update")
    tu.add_argument("--name", type=str, help="New task name")
    tu.add_argument("--status", type=str, help="New status (space-specific)")
    tu.add_argument(
        "--priority", type=str, help="Priority: urgent, high, normal, low (or 1-4)"
    )
    tu.add_argument(
        "--desc",
        type=str,
        help="Inline description text (mutually exclusive with --desc-file)",
    )
    tu.add_argument(
        "--desc-file", type=str, help="Path to a file containing description content"
    )
    tu.add_argument(
        "--add-assignee",
        dest="add_assignees",
        action="append",
        metavar="USER_ID",
        help="Assign user ID to the task (repeatable)",
    )
    tu.add_argument(
        "--remove-assignee",
        dest="remove_assignees",
        action="append",
        metavar="USER_ID",
        help="Unassign user ID from the task (repeatable)",
    )
    tu.add_argument(
        "--add-tag",
        dest="add_tags",
        action="append",
        metavar="TAG",
        help="Tag to add to the task (repeatable, auto-lowercased)",
    )
    tu.add_argument(
        "--remove-tag",
        dest="remove_tags",
        action="append",
        metavar="TAG",
        help="Tag to remove from the task (repeatable, auto-lowercased)",
    )
    tu.add_argument(
        "--custom-field",
        dest="custom_fields",
        action="append",
        metavar="FIELD_ID=VALUE",
        help="Custom field to set (repeatable, format: field_uuid=value)",
    )

    # tasks search
    ts = tasks_sub.add_parser(
        "search",
        formatter_class=F,
        help="Search tasks by query string",
        description="""\
Search tasks across the workspace by a text query.

Results are paginated internally and returned as a single JSON object.
By default, output is compact (id, name, status, priority, url).
Use --full for the full task objects returned by the API, with status
normalized to a consistent dict shape, or --fields to pick specific fields.

Use --space, --list, or --folder to scope results. Use `--space` to search the
whole space across every list it owns. Without any scope filter, results may
include tasks from all spaces.

When the query looks like a task ID (e.g. PROJ-39, PROJ-12), --name-prefix
is auto-applied to filter exact matches. Use --name-prefix explicitly for
other prefix-based filtering.""",
        epilog="""\
returns:
  {"tasks": [...], "count": N}

examples:
  clickup tasks search "login bug"
  clickup tasks search "PROJ-39" --space <name>
  clickup tasks search "PROJ-8" --space <name>
  clickup tasks search "PROJ" --space <name> --name-prefix "PROJ-9"
  clickup tasks search "deploy" --include-closed --full
  clickup tasks search "bug" --fields id,name,url
  clickup tasks search "bug" --list 12345
  clickup tasks search "bug" --custom-field abc123=high

notes:
  Output is compact by default (id, name, status, priority, url).
  Use --full for full task objects with normalized status shape, or --fields
  for custom field selection.
  Queries matching the pattern ABC-123 auto-apply --name-prefix.
  Use --space, --list, or --folder to scope results.
  Use `--space` to search the whole space across every list it owns.
  --custom-field applies equality filters as FIELD_ID=VALUE and is repeatable.
  --name-prefix filters the returned tasks client-side by task name prefix.
  The search API has a default page size — this CLI handles pagination
  automatically and returns all matching results.""",
    )
    add_id_argument(ts, "query", "Search query string")
    ts.add_argument(
        "--include-closed",
        action="store_true",
        help="Include closed/completed tasks in results",
    )
    ts.add_argument(
        "--include-archived",
        action="store_true",
        dest="include_archived",
        help="Include archived tasks (makes a second API call and merges results)",
    )
    ts.add_argument(
        "--space",
        metavar="SPACE_NAME_OR_ID",
        type=str,
        help="Scope search to a specific space (name from config or raw ID); use it to search the whole space",
    )
    ts.add_argument(
        "--list", type=str, dest="list_id", help="Scope search to a specific list ID"
    )
    ts.add_argument(
        "--folder",
        type=str,
        dest="folder_id",
        help="Scope search to a specific folder ID (ClickUp calls this project_ids)",
    )
    ts.add_argument(
        "--custom-field",
        type=str,
        action="append",
        dest="custom_fields",
        metavar="FIELD_ID=VALUE",
        help="Filter by a custom field equality match (repeatable)",
    )
    ts.add_argument(
        "--name-prefix",
        type=str,
        help="Keep only tasks whose name starts with this prefix (client-side filter)",
    )
    ts.add_argument(
        "--tag",
        type=str,
        action="append",
        dest="tags",
        help="Filter by tag name (repeatable, client-side, auto-lowercased)",
    )
    ts.add_argument(
        "--fields",
        type=str,
        help="Comma-separated list of fields to return per task (e.g. id,name,status,url)",
    )
    ts.add_argument(
        "--full",
        action="store_true",
        help="Return full task objects, with status normalized to a dict shape (default is compact: id, name, status, priority, url)",
    )
    ts.add_argument(
        "--all-pages",
        action="store_true",
        help="Fetch every search results page instead of the default bounded aggregate scan",
    )

    # tasks delete
    td = tasks_sub.add_parser(
        "delete",
        formatter_class=F,
        help="Delete a task (destructive)",
        description="""\
Delete a task permanently. This is a destructive, irreversible command.

Use --dry-run to preview the operation without deleting anything.
Global flags may appear before or after the command group:
  clickup --dry-run tasks delete abc123""",
        epilog="""\
returns:
  {"status": "ok", "action": "deleted", "task_id": "..."}

examples:
  clickup --dry-run tasks delete abc123
  clickup tasks delete abc123""",
    )
    add_id_argument(td, "task_id", "ClickUp task ID to delete")

    # tasks move
    tm = tasks_sub.add_parser(
        "move",
        formatter_class=F,
        help="Move a task to a different list/space",
        description="""\
Move a task to a different list. This is a mutating command (v3 API).

The destination can be a configured space name — which resolves
to that space's default list — or a raw ClickUp list ID.

For tasks in multiple lists, this changes the home list only.

Use --dry-run to preview without moving.
Global flags may appear before or after the command group:
  clickup --dry-run tasks move abc123 --to <space-or-list-id>""",
        epilog="""\
returns:
  The updated task object from the API.

examples:
  clickup tasks move abc123 --to <space-or-list-id>
  clickup tasks move abc123 --to 901816700000
  clickup --dry-run tasks move abc123 --to <space-or-list-id>""",
    )
    add_id_argument(tm, "task_id", "ClickUp task ID to move")
    tm.add_argument(
        "--to",
        required=True,
        dest="to_list",
        help="Destination space name or raw list ID",
    )

    # tasks merge
    tmg = tasks_sub.add_parser(
        "merge",
        formatter_class=F,
        help="Merge source tasks into a target task",
        description="""\
Merge one or more source tasks into a target task. This is a mutating command.

The source tasks are absorbed into the target. Their comments, attachments,
and activity are consolidated. Source tasks are removed after merging.

Use --dry-run to preview without merging.
Global flags may appear before or after the command group:
  clickup --dry-run tasks merge abc123 --sources def456,ghi789""",
        epilog="""\
returns:
  The merged task object from the API.

examples:
  clickup tasks merge abc123 --sources def456
  clickup tasks merge abc123 --sources def456,ghi789
  clickup --dry-run tasks merge abc123 --sources def456""",
    )
    add_id_argument(tmg, "task_id", "Target task ID (tasks merge into this)")
    tmg.add_argument(
        "--sources",
        required=True,
        dest="source_ids",
        help="Comma-separated source task IDs to merge into the target",
    )

    # tasks lists
    ttl = tasks_sub.add_parser(
        "lists",
        formatter_class=F,
        help="Inspect the lists a task belongs to",
        description="""\
Inspect the home list and additional list memberships for a task.

This is distinct from `tasks move`: it reports membership only and does not
change or imply a home-list move.

Delegates to GET /task/{id} and returns an explicit home-list field plus the
full list membership set for the task.""",
        epilog="""\
returns:
  {"task_id": "...", "home_list": {...}, "lists": [...]}

examples:
  clickup tasks lists abc123
  clickup tasks lists --task-id abc123""",
    )
    add_id_argument(ttl, "task_id", "ClickUp task ID")

    # tasks add-to-list
    ttal = tasks_sub.add_parser(
        "add-to-list",
        formatter_class=F,
        help="Add a task to an additional list",
        description="""\
Add a task to an additional list without changing its home list.

This is distinct from `tasks move`, which changes the home list. Use --dry-run
to preview the exact membership action before calling the API.""",
        epilog="""\
examples:
  clickup tasks add-to-list abc123 --list-id 901816700000
  clickup --dry-run tasks add-to-list abc123 --list-id 901816700000""",
    )
    add_id_argument(ttal, "task_id", "ClickUp task ID")
    ttal.add_argument(
        "--list-id",
        required=True,
        dest="list_id",
        help="Additional ClickUp list ID to add the task to",
    )

    # tasks remove-from-list
    ttrfl = tasks_sub.add_parser(
        "remove-from-list",
        formatter_class=F,
        help="Remove a task from an additional list",
        description="""\
Remove a task from an additional list without converting the operation into a
home-list move.

If ClickUp rejects the removal because the task cannot leave that list, the
command surfaces that API failure instead of masking it.""",
        epilog="""\
examples:
  clickup tasks remove-from-list abc123 --list-id 901816700000
  clickup --dry-run tasks remove-from-list abc123 --list-id 901816700000""",
    )
    add_id_argument(ttrfl, "task_id", "ClickUp task ID")
    ttrfl.add_argument(
        "--list-id",
        required=True,
        dest="list_id",
        help="Additional ClickUp list ID to remove the task from",
    )

    # tasks depend — subcommand group for dependency CRUD
    tdp = tasks_sub.add_parser(
        "depend",
        formatter_class=F,
        help="Manage task dependencies (add, remove, list)",
        description="""\
Manage ClickUp task dependencies — the "waiting on" / "blocking"
relationships between tasks. Dependencies have direction:

  --depends-on      : this task is blocked until another task finishes
  --depended-on-by  : another task is blocked until this task finishes

Subcommands:
  add     — create a dependency link
  remove  — delete a dependency link
  list    — list this task's current dependency links

Under the hood these map to POST/DELETE /task/{id}/dependency and the
`dependencies` field returned by GET /task/{id}.""",
        epilog="""\
examples:
  clickup tasks depend add abc123 --depends-on def456
  clickup tasks depend add abc123 --depended-on-by def456
  clickup tasks depend remove abc123 --depends-on def456
  clickup tasks depend list abc123
  clickup --dry-run tasks depend add abc123 --depends-on def456""",
    )
    tdp_sub = tdp.add_subparsers(dest="subcommand", required=True)

    for name, desc in (
        ("add", "Create a dependency link between two tasks"),
        ("remove", "Delete a dependency link between two tasks"),
    ):
        sp = tdp_sub.add_parser(
            name,
            formatter_class=F,
            help=desc,
            description=f"""\
{desc}.

Exactly one of --depends-on / --depended-on-by is required. The direction
determines which task is blocked:

  --depends-on BLOCKER_TASK_ID      : <task_id> waits for BLOCKER
  --depended-on-by BLOCKED_TASK_ID  : BLOCKED waits for <task_id>

Use --dry-run to preview without calling the API.""",
        )
        add_id_argument(sp, "task_id", "Target ClickUp task ID")
        direction = sp.add_mutually_exclusive_group(required=True)
        direction.add_argument(
            "--depends-on",
            dest="depends_on",
            type=str,
            metavar="OTHER_TASK_ID",
            help="Other task this task is blocked by",
        )
        direction.add_argument(
            "--depended-on-by",
            dest="dependency_of",
            type=str,
            metavar="OTHER_TASK_ID",
            help="Other task that is blocked by this task",
        )

    tdpl = tdp_sub.add_parser(
        "list",
        formatter_class=F,
        help="List a task's current dependency links",
        description="""\
List the dependency links on a task. Returns both directions:

  depends_on      — tasks that must finish before this one
  depended_on_by  — tasks that are blocked by this one

Delegates to GET /task/{id} and returns the `dependencies` array
partitioned by direction.""",
        epilog="""\
returns:
  {"task_id": "...", "depends_on": [...], "depended_on_by": [...]}

examples:
  clickup tasks depend list abc123""",
    )
    add_id_argument(tdpl, "task_id", "ClickUp task ID")

    # tasks link - linked-task relationship CRUD
    tlk = tasks_sub.add_parser(
        "link",
        formatter_class=F,
        help="Manage linked-task relationships (add, remove, list)",
        description="""\
Manage ClickUp linked-task relationships. Links are distinct from dependencies:
they associate tasks without introducing "blocked by" or "blocking" meaning.

Subcommands:
  add     — create a linked-task relationship
  remove  — delete a linked-task relationship
  list    — list this task's current linked-task relationships

Under the hood these map to POST/DELETE /task/{id}/link/{linked_task_id}
and the `linked_tasks` field returned by GET /task/{id}.""",
        epilog="""\
examples:
  clickup tasks link add abc123 --linked-task def456
  clickup tasks link remove abc123 --linked-task def456
  clickup tasks link list abc123
  clickup --dry-run tasks link add abc123 --linked-task def456""",
    )
    tlk_sub = tlk.add_subparsers(dest="subcommand", required=True)

    for name, desc in (
        ("add", "Create a linked-task relationship between two tasks"),
        ("remove", "Delete a linked-task relationship between two tasks"),
    ):
        sp = tlk_sub.add_parser(
            name,
            formatter_class=F,
            help=desc,
            description=f"""\
{desc}.

This relationship is not a dependency. Use `tasks depend` for blocking flows.

Use --dry-run to preview without calling the API.""",
        )
        add_id_argument(sp, "task_id", "Target ClickUp task ID")
        sp.add_argument(
            "--linked-task",
            dest="linked_task_id",
            required=True,
            type=str,
            metavar="OTHER_TASK_ID",
            help="Other task to link or unlink",
        )

    tlkl = tlk_sub.add_parser(
        "list",
        formatter_class=F,
        help="List a task's current linked-task relationships",
        description="""\
List the linked-task relationships on a task.

Delegates to GET /task/{id} and returns only the `linked_tasks` data,
separate from any dependency arrays or other task metadata.""",
        epilog="""\
returns:
  {"task_id": "...", "linked_tasks": [...]}

examples:
  clickup tasks link list abc123""",
    )
    add_id_argument(tlkl, "task_id", "ClickUp task ID")
