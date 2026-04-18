"""Task command handlers — list, get, create, update, search, delete, move, merge."""

import re
import sys

import requests

from ..config import WORKSPACE_ID, SPACES
from ..helpers import read_content, error, format_tasks, fetch_all_comments, add_id_argument


def register_parser(subparsers, F):
    """Register all tasks subcommands on the given subparsers object."""
    tasks_parser = subparsers.add_parser(
        "tasks",
        formatter_class=F,
        help="Full task CRUD: list, get, create, update, search, delete, move, merge",
        description="""\
Manage ClickUp tasks — full CRUD plus search, move, and merge.

Subcommands:
  list    — list tasks in a list or space (paginated internally)
  get     — fetch one task by ID
  create  — create a new task in a list or space (mutating)
  update  — update fields on an existing task (mutating)
  search  — search tasks by query across workspace or within a space
  delete  — delete a task (destructive)
  move    — move a task to a different list/space (mutating, v3)
  merge   — merge source tasks into a target task (mutating)

Tasks live in lists. Each space has a default list, but you can also
target a specific list (e.g. one inside a folder) using --list <id>.
Use 'folders list' and 'lists list' to discover list IDs.

Does not cover: checklists, custom fields, time tracking, or attachments.""",
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
Use --full for the raw API response, or --fields to pick specific fields.

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
  Use --full for raw API response, or --fields for custom field selection.
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
        help="Return full raw API response (default is compact: id, name, status, priority, url)",
    )

    # tasks get
    tg = tasks_sub.add_parser(
        "get",
        formatter_class=F,
        help="Fetch one task by ID (includes comments by default)",
        description="""\
Fetch a single task by its ClickUp task ID.

By default, comments are fetched and appended to the task output under
a "comments" key (array of {id, comment_text, user, date}) and a
"comment_count" field. This ensures task context is always complete
without needing a separate comments list call.

Use --no-comments to suppress comment fetching if output is too verbose
or you only need the task fields.""",
        epilog="""\
returns:
  One task JSON object with all fields, plus:
    "comments": [{id, comment_text, user, date}, ...]
    "comment_count": N

  With --no-comments, returns the raw task object without comments.

examples:
  clickup tasks get abc123
  clickup --pretty tasks get abc123
  clickup tasks get abc123 --no-comments""",
    )
    add_id_argument(tg, "task_id", "ClickUp task ID")
    tg.add_argument(
        "--no-comments",
        action="store_true",
        help="Skip auto-fetching comments (default: comments included)",
    )

    # tasks create
    tc = tasks_sub.add_parser(
        "create",
        formatter_class=F,
        help="Create a new task in a list or space",
        description="""\
Create a new task in a list. This is a mutating command.

--space is always required (used to resolve the target list).
By default, the task is created in the space's default list. Use --list
to target a specific list instead (e.g. one inside a folder).

Use --desc for inline text or --desc-file for file-based content.
Do not use both at the same time.

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

notes:
  --space is always required (to resolve target list). --list is optional.
  If --list is given, the task is created in that list instead of the
  space's default list.
  --desc and --desc-file are mutually exclusive. Using both is an error.
  --assign assigns the task to a user ID.
  Does not support: checklists, custom fields, attachments, or due dates.""",
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
Use --full for the raw API response, or --fields to pick specific fields.

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

notes:
  Output is compact by default (id, name, status, priority, url).
  Use --full for raw API response, or --fields for custom field selection.
  Queries matching the pattern ABC-123 auto-apply --name-prefix.
  Use --space, --list, or --folder to scope results.
  Use `--space` to search the whole space across every list it owns.
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
        help="Return full raw API response (default is compact: id, name, status, priority, url)",
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

PRIORITY_MAP = {"urgent": 1, "high": 2, "normal": 3, "low": 4}

# Pattern for task ID queries like PROJ-39, BUG-12
_TASK_ID_PATTERN = re.compile(r"^[A-Z]+-\d+$")


def _parse_fields(args):
    """Parse --fields arg into a list, or None."""
    raw = getattr(args, "fields", None)
    if not raw:
        return None
    return [f.strip() for f in raw.split(",") if f.strip()]


def _format_and_wrap(tasks, args):
    """Format tasks and wrap in standard response dict."""
    fields = _parse_fields(args)
    full = getattr(args, "full", False)
    formatted = format_tasks(tasks, full=full, fields=fields)
    return {"tasks": formatted, "count": len(formatted)}


def _resolve_priority(priority_arg):
    """Resolve a priority name or number to the API integer value."""
    if priority_arg is None:
        return None
    if priority_arg in PRIORITY_MAP:
        return PRIORITY_MAP[priority_arg]
    if priority_arg.isdigit() and int(priority_arg) in (1, 2, 3, 4):
        return int(priority_arg)
    error(f"Invalid priority: {priority_arg}. Use: urgent, high, normal, low (or 1-4)")


def _resolve_list_id(args, client=None):
    """Resolve the target list ID from --list or --space args.

    --list wins when present. Otherwise --space may be a configured alias
    (from config file) or a raw ClickUp space ID. Raw IDs require a `client`
    because resolving a space to a default list costs one API call.
    """
    if hasattr(args, "list_id") and args.list_id:
        return args.list_id
    if hasattr(args, "space") and args.space:
        space = SPACES.get(args.space)
        if space:
            return space["list_id"]
        if args.space.isdigit():
            if client is None:
                error(
                    f"Raw space ID {args.space} needs an API lookup but no "
                    "client is available. Use --list <list_id> instead."
                )
            return _first_folderless_list_id(client, args.space)
        error(f"Unknown space: {args.space}. Check your config file.")
    error("Provide either --space <name|id> or --list <list_id>")


def _first_folderless_list_id(client, space_id):
    """Return the first folderless list ID in a space, via API lookup."""
    resp = client.get_v2(f"/space/{space_id}/list", allow_dry_run=True)
    lists = resp.get("lists", [])
    if not lists:
        error(
            f"Space {space_id} has no folderless lists. "
            "Pass --list <list_id> to target a list inside a folder."
        )
    return lists[0]["id"]


def _resolve_space_id(space_arg):
    """Resolve a --space alias or raw ID to a concrete space ID."""
    if not space_arg:
        return None
    space = SPACES.get(space_arg)
    if space:
        return space["space_id"]
    if space_arg.isdigit():
        return space_arg
    error(f"Unknown space: {space_arg}. Check your config file.")


def _resolve_scope_list_ids(client, space_arg):
    """Resolve --space to every list ID in that space for search scoping."""
    space_id = _resolve_space_id(space_arg)

    folderless_resp = client.get_v2(f"/space/{space_id}/list", allow_dry_run=True)
    folderless_lists = folderless_resp.get("lists", [])

    folder_resp = client.get_v2(f"/space/{space_id}/folder", allow_dry_run=True)
    folders = folder_resp.get("folders", [])

    list_ids = [item["id"] for item in folderless_lists]
    for folder in folders:
        folder_lists_resp = client.get_v2(
            f"/folder/{folder['id']}/list", allow_dry_run=True
        )
        list_ids.extend(item["id"] for item in folder_lists_resp.get("lists", []))

    list_ids = list(dict.fromkeys(list_ids))
    if not list_ids:
        error(
            f"Space {space_arg} has no lists available for search scoping. "
            "Pass --list <list_id> or --folder <folder_id> instead."
        )
    return list_ids


def _paginate_tasks(client, path, params):
    """Fetch all task pages from a paginated v2 endpoint."""
    all_tasks = []
    page = 0
    while True:
        params["page"] = str(page)
        resp = client.get_v2(path, params=params)
        tasks = resp.get("tasks", [])
        all_tasks.extend(tasks)
        if resp.get("last_page", False):
            break
        page += 1
    return all_tasks


def _filter_by_tags(tasks, tag_names):
    """Client-side filter: keep tasks that have ALL specified tags."""
    required = {t.lower() for t in tag_names}
    return [
        t for t in tasks
        if required <= {tg.get("name", "").lower() for tg in t.get("tags", [])}
    ]


def cmd_tasks_list(client, args):
    list_id = _resolve_list_id(args, client=client)
    if client.dry_run:
        return {"dry_run": True, "action": "list_tasks", "list_id": list_id}

    params = {"archived": "false"}
    if args.include_closed:
        params["include_closed"] = "true"
    if args.status:
        params["statuses[]"] = args.status
    if args.subtasks:
        params["subtasks"] = "true"
    tag_filter = getattr(args, "tags", None)
    if tag_filter:
        params["tags[]"] = [tag.lower() for tag in tag_filter]

    all_tasks = _paginate_tasks(client, f"/list/{list_id}/task", params)

    if getattr(args, "include_archived", False):
        archived_params = dict(params)
        archived_params["archived"] = "true"
        all_tasks.extend(
            _paginate_tasks(client, f"/list/{list_id}/task", archived_params)
        )

    return _format_and_wrap(all_tasks, args)


def cmd_tasks_get(client, args):
    task = client.get_v2(f"/task/{args.task_id}")

    if getattr(args, "no_comments", False):
        return task

    # Auto-fetch comments and append to task output
    try:
        all_comments = fetch_all_comments(client, args.task_id)

        # Slim down to useful fields
        task["comments"] = [
            {
                "id": c.get("id"),
                "comment_text": c.get("comment_text", ""),
                "user": c.get("user", {}).get("username", "unknown"),
                "date": c.get("date"),
            }
            for c in all_comments
        ]
        task["comment_count"] = len(all_comments)
    except (requests.RequestException, KeyError, ValueError) as e:
        print(f"warning: could not fetch comments: {e}", file=sys.stderr)
        task["comments"] = []
        task["comment_count"] = 0

    return task


def _infer_space_from_list(client, list_id):
    """Look up a list via API to find its parent space. Returns space name or ID."""
    resp = client.get_v2(f"/list/{list_id}", allow_dry_run=True)
    space_info = resp.get("space", {})
    space_id = space_info.get("id")
    if not space_id:
        return None
    for name, cfg in SPACES.items():
        if cfg.get("space_id") == str(space_id):
            return name
    return str(space_id)


def cmd_tasks_create(client, args):
    if not args.space and getattr(args, "list_id", None):
        inferred = _infer_space_from_list(client, args.list_id)
        if inferred:
            args.space = inferred
    if not args.space:
        error("--space is required (or provide --list to auto-infer the space)")

    list_id = _resolve_list_id(args, client=client)
    desc = read_content(args.desc, args.desc_file, "--desc")

    body = {"name": args.name}

    if args.priority:
        body["priority"] = _resolve_priority(args.priority)

    if desc:
        body["markdown_description"] = desc

    if args.status:
        body["status"] = args.status

    assign_user = getattr(args, "assign_user", None)
    if assign_user:
        body["assignees"] = [int(assign_user)]

    if client.dry_run:
        return {
            "dry_run": True,
            "body": body,
            "space": args.space,
            "list_id": list_id,
        }

    return client.post_v2(f"/list/{list_id}/task", data=body)


def _parse_custom_field(raw):
    """Parse a --custom-field FIELD_ID=VALUE token."""
    if "=" not in raw:
        error(f"Invalid --custom-field value (expected FIELD_ID=VALUE): {raw}")
    field_id, _, value = raw.partition("=")
    field_id = field_id.strip()
    if not field_id:
        error(f"Invalid --custom-field value (empty field id): {raw}")
    return field_id, value


def cmd_tasks_update(client, args):
    desc = read_content(args.desc, args.desc_file, "--desc")

    body = {}
    if args.name:
        body["name"] = args.name
    if args.status:
        body["status"] = args.status
    if desc is not None:
        body["markdown_description"] = desc
    if args.priority:
        body["priority"] = _resolve_priority(args.priority)

    add_assignees = [int(u) for u in (getattr(args, "add_assignees", None) or [])]
    rem_assignees = [int(u) for u in (getattr(args, "remove_assignees", None) or [])]
    if add_assignees or rem_assignees:
        body["assignees"] = {"add": add_assignees, "rem": rem_assignees}

    add_tags = [t.lower() for t in (getattr(args, "add_tags", None) or [])]
    remove_tags = [t.lower() for t in (getattr(args, "remove_tags", None) or [])]
    custom_fields = [
        _parse_custom_field(raw)
        for raw in (getattr(args, "custom_fields", None) or [])
    ]

    if not body and not add_tags and not remove_tags and not custom_fields:
        error(
            "Nothing to update — provide at least one of: --name, --status, --desc, "
            "--desc-file, --priority, --add-assignee, --remove-assignee, --add-tag, "
            "--remove-tag, --custom-field"
        )

    plan = {
        "task_id": args.task_id,
        "put_body": body or None,
        "tag_adds": add_tags,
        "tag_removes": remove_tags,
        "custom_fields": [{"field_id": fid, "value": val} for fid, val in custom_fields],
    }

    if client.dry_run:
        return {"dry_run": True, "action": "update_task", **plan}

    result = None
    if body:
        result = client.put_v2(f"/task/{args.task_id}", data=body)

    for tag in add_tags:
        client.post_v2(f"/task/{args.task_id}/tag/{tag}", data={})
    for tag in remove_tags:
        client.delete_v2(f"/task/{args.task_id}/tag/{tag}")

    for field_id, value in custom_fields:
        client.post_v2(f"/task/{args.task_id}/field/{field_id}", data={"value": value})

    if result is None:
        # Side-effect-only update — fetch the current task state to return.
        result = client.get_v2(f"/task/{args.task_id}")

    return result


def cmd_tasks_search(client, args):
    if client.dry_run:
        return {"dry_run": True, "action": "search_tasks", "query": args.query}

    # Auto-apply --name-prefix when query looks like a task ID (e.g. PROJ-39)
    name_prefix = getattr(args, "name_prefix", None)
    if not name_prefix and _TASK_ID_PATTERN.match(args.query):
        name_prefix = args.query

    params = {"search": args.query}
    if args.include_closed:
        params["include_closed"] = "true"
    if args.space:
        params["list_ids[]"] = _resolve_scope_list_ids(client, args.space)
    if hasattr(args, "list_id") and args.list_id:
        params["list_ids[]"] = args.list_id
    if hasattr(args, "folder_id") and args.folder_id:
        params["project_ids[]"] = args.folder_id

    all_tasks = _paginate_tasks(client, f"/team/{WORKSPACE_ID}/task", params)

    if getattr(args, "include_archived", False):
        archived_params = dict(params)
        archived_params["archived"] = "true"
        all_tasks.extend(
            _paginate_tasks(client, f"/team/{WORKSPACE_ID}/task", archived_params)
        )

    if name_prefix:
        all_tasks = [
            task
            for task in all_tasks
            if task.get("name", "").startswith(name_prefix)
        ]

    tag_filter = getattr(args, "tags", None)
    if tag_filter:
        all_tasks = _filter_by_tags(all_tasks, tag_filter)

    return _format_and_wrap(all_tasks, args)


def cmd_tasks_delete(client, args):
    """Delete a task by ID."""
    if client.dry_run:
        return {"dry_run": True, "action": "delete", "task_id": args.task_id}
    client.delete_v2(f"/task/{args.task_id}")
    return {"status": "ok", "action": "deleted", "task_id": args.task_id}


def cmd_tasks_move(client, args):
    """Move a task to a different list (v3 endpoint)."""
    space = SPACES.get(args.to_list)
    list_id = space["list_id"] if space else args.to_list

    if client.dry_run:
        return {
            "dry_run": True,
            "action": "move",
            "task_id": args.task_id,
            "destination_list_id": list_id,
        }
    return client.put_v3(
        f"/workspaces/{WORKSPACE_ID}/tasks/{args.task_id}/home_list/{list_id}"
    )


def cmd_tasks_depend(client, args):
    """Dispatch `tasks depend {add,remove,list}` subcommands."""
    sub = getattr(args, "subcommand", None)
    if sub == "add":
        return _tasks_depend_add(client, args)
    if sub == "remove":
        return _tasks_depend_remove(client, args)
    if sub == "list":
        return _tasks_depend_list(client, args)
    error(f"Unknown tasks depend subcommand: {sub}")


def _depend_body(args):
    """Build the dependency body from --depends-on / --depended-on-by."""
    if getattr(args, "depends_on", None):
        return {"depends_on": args.depends_on}
    if getattr(args, "dependency_of", None):
        return {"dependency_of": args.dependency_of}
    error("Provide either --depends-on <task_id> or --depended-on-by <task_id>")


def _tasks_depend_add(client, args):
    body = _depend_body(args)
    if client.dry_run:
        return {"dry_run": True, "action": "depend_add", "task_id": args.task_id, **body}
    client.post_v2(f"/task/{args.task_id}/dependency", data=body)
    return {"status": "ok", "action": "depend_added", "task_id": args.task_id, **body}


def _tasks_depend_remove(client, args):
    body = _depend_body(args)
    if client.dry_run:
        return {"dry_run": True, "action": "depend_remove", "task_id": args.task_id, **body}
    client.delete_v2(f"/task/{args.task_id}/dependency", params=body)
    return {"status": "ok", "action": "depend_removed", "task_id": args.task_id, **body}


def _tasks_depend_list(client, args):
    task = client.get_v2(f"/task/{args.task_id}")
    dependencies = task.get("dependencies", []) or []
    # ClickUp stores dependencies as {task_id (the waiter), depends_on (the blocker)}.
    # From this task's POV:
    #   - depends_on      : entries where the waiter is us
    #   - depended_on_by  : entries where the blocker is us
    depends_on = [d for d in dependencies if d.get("task_id") == args.task_id]
    depended_on_by = [d for d in dependencies if d.get("depends_on") == args.task_id]
    return {
        "task_id": args.task_id,
        "depends_on": depends_on,
        "depended_on_by": depended_on_by,
    }


def cmd_tasks_merge(client, args):
    """Merge source tasks into a target task."""
    source_ids = [tid.strip() for tid in args.source_ids.split(",")]

    if client.dry_run:
        return {
            "dry_run": True,
            "action": "merge",
            "target_task_id": args.task_id,
            "source_task_ids": source_ids,
        }
    return client.post_v2(f"/task/{args.task_id}/merge", data={"task_ids": source_ids})
