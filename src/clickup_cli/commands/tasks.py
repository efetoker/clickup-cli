"""Task command handlers — list, get, create, update, search, delete, move, merge."""

import re
import sys

import requests

from ..config import WORKSPACE_ID, SPACES, USER_ID, DEFAULT_TAGS, DRAFT_TAG, GOOD_AS_IS_TAG, DEFAULT_PRIORITY
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
or including closed tasks.""",
        epilog="""\
returns:
  {"tasks": [...], "count": N}

examples:
  clickup tasks list --space <name>
  clickup tasks list --space <name> --full
  clickup tasks list --space <name> --fields id,name,url
  clickup tasks list --space <name> --include-closed
  clickup tasks list --space <name> --status "in progress"
  clickup tasks list --space <name> --subtasks

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
        "--status", type=str, help="Filter tasks by status name (space-specific)"
    )
    tl.add_argument(
        "--subtasks",
        action="store_true",
        help="Include subtasks (nested child tasks) in results",
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

Tags are applied automatically based on config (default_tags, draft_tag).

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
  clickup --dry-run tasks create --space <name> --name "Test" --good-as-is

notes:
  --space is always required (to resolve target list). --list is optional.
  If --list is given, the task is created in that list instead of the
  space's default list.
  --desc and --desc-file are mutually exclusive. Using both is an error.
  --good-as-is marks the task as intentionally simple (no draft tag).
  --no-assign skips the default assignee.
  --priority defaults to the value in your config (default: low).
  Does not support: checklists, custom fields, attachments, or due dates.""",
    )
    tc.add_argument(
        "--space",
        type=str,
        help="Target space (auto-inferred from --list if omitted)",
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
    tc.add_argument("--no-assign", action="store_true", help="Skip default assignee")
    tc.add_argument(
        "--good-as-is",
        action="store_true",
        help="Mark task as intentionally simple (no draft tag)",
    )
    tc.add_argument(
        "--skip-dedup",
        action="store_true",
        default=False,
        help="Skip duplicate check and create the task even if one with the same name exists",
    )

    # tasks update
    tu = tasks_sub.add_parser(
        "update",
        formatter_class=F,
        help="Update fields on an existing task",
        description="""\
Update one or more fields on an existing task. This is a mutating command.

At least one mutable field is required: --name, --status, --priority,
--desc, or --desc-file. If none are provided, the command exits with an error.

Use --desc for inline text or --desc-file for file-based content.
Do not use both at the same time.

Use --dry-run to preview the request body without applying changes.
Global flags may appear before or after the command group:
  clickup --dry-run tasks update abc123 --status "complete" """,
        epilog="""\
returns:
  The updated task object from the API.

examples:
  clickup tasks update abc123 --name "Renamed task"
  clickup tasks update abc123 --status "complete"
  clickup tasks update abc123 --desc-file updated_spec.md
  clickup --dry-run tasks update abc123 --status "in progress"

notes:
  --desc and --desc-file are mutually exclusive. Using both is an error.
  Does not support: changing assignees, tags, or custom fields.""",
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

Use --space, --list, or --folder to scope results. Without any scope
filter, results may include tasks from all spaces.

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
        "--space", type=str, help="Scope search to a specific space"
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

PRIORITY_MAP = {"urgent": 1, "high": 2, "normal": 3, "low": 4}

# Pattern for task ID queries like PER-39, JMP-12, MTM-8
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


def _resolve_list_id(args):
    """Resolve the target list ID from --list or --space args."""
    if hasattr(args, "list_id") and args.list_id:
        return args.list_id
    if hasattr(args, "space") and args.space:
        space = SPACES.get(args.space)
        if not space:
            error(f"Unknown space: {args.space}. Check your config file.")
        return space["list_id"]
    error("Provide either --space <name> or --list <list_id>")


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


def cmd_tasks_list(client, args):
    list_id = _resolve_list_id(args)
    if client.dry_run:
        return {"dry_run": True, "action": "list_tasks", "list_id": list_id}

    params = {"archived": "false"}
    if args.include_closed:
        params["include_closed"] = "true"
    if args.status:
        params["statuses[]"] = args.status
    if args.subtasks:
        params["subtasks"] = "true"

    all_tasks = _paginate_tasks(client, f"/list/{list_id}/task", params)
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
            print(
                f"hint: inferred --space {inferred} from --list {args.list_id}",
                file=sys.stderr,
            )
    if not args.space:
        error("--space is required (or provide --list to auto-infer the space)")

    list_id = _resolve_list_id(args)
    desc = read_content(args.desc, args.desc_file, "--desc")

    tags = list(DEFAULT_TAGS)  # copy to avoid mutating config
    if args.good_as_is:
        tags.append(GOOD_AS_IS_TAG)
    elif not desc:
        tags.append(DRAFT_TAG)

    priority = _resolve_priority(args.priority) if args.priority else DEFAULT_PRIORITY

    body = {"name": args.name, "tags": tags, "priority": priority}

    if desc:
        body["markdown_description"] = desc

    if args.status:
        body["status"] = args.status

    if not args.no_assign:
        user_id = USER_ID
        if user_id:
            body["assignees"] = [int(user_id)]

    if client.dry_run:
        return {
            "dry_run": True,
            "body": body,
            "space": args.space,
            "list_id": list_id,
        }

    # Pre-create duplicate search
    if not getattr(args, "skip_dedup", False):
        search_resp = client.get_v2(
            f"/team/{WORKSPACE_ID}/task",
            params={"search": args.name, "list_ids[]": list_id},
        )
        existing = [
            t for t in search_resp.get("tasks", [])
            if t.get("name", "").lower() == args.name.lower()
        ]
        if existing:
            match = existing[0]
            print(
                f"warning: found existing task with same name: "
                f"{match.get('id')} — {match.get('url', 'no url')}",
                file=sys.stderr,
            )
            match["duplicate_of"] = match["id"]
            return match

    return client.post_v2(f"/list/{list_id}/task", data=body)


def cmd_tasks_update(client, args):
    desc = read_content(args.desc, args.desc_file, "--desc")
    body = {}
    if args.name:
        body["name"] = args.name
    if args.status:
        body["status"] = args.status
    if desc:
        body["markdown_description"] = desc
    if args.priority:
        body["priority"] = _resolve_priority(args.priority)

    if not body:
        error(
            "Nothing to update — provide at least one of: --name, --status, --desc, --desc-file, --priority"
        )

    return client.put_v2(f"/task/{args.task_id}", data=body)


def cmd_tasks_search(client, args):
    if client.dry_run:
        return {"dry_run": True, "action": "search_tasks", "query": args.query}

    # Auto-apply --name-prefix when query looks like a task ID (e.g. PER-39)
    name_prefix = getattr(args, "name_prefix", None)
    if not name_prefix and _TASK_ID_PATTERN.match(args.query):
        name_prefix = args.query
        print(
            f"hint: query \"{args.query}\" looks like a task ID — "
            f"auto-applying --name-prefix \"{args.query}\" to filter exact matches",
            file=sys.stderr,
        )

    params = {"search": args.query}
    if args.include_closed:
        params["include_closed"] = "true"
    if args.space:
        space = SPACES.get(args.space)
        if space:
            params["list_ids[]"] = space["list_id"]
    if hasattr(args, "list_id") and args.list_id:
        params["list_ids[]"] = args.list_id
    if hasattr(args, "folder_id") and args.folder_id:
        params["project_ids[]"] = args.folder_id

    all_tasks = _paginate_tasks(client, f"/team/{WORKSPACE_ID}/task", params)

    if name_prefix:
        all_tasks = [
            task
            for task in all_tasks
            if task.get("name", "").startswith(name_prefix)
        ]

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
