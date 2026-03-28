"""Task command handlers — list, get, create, update, search, delete, move, merge."""

import re
import sys

import requests

from ..config import WORKSPACE_ID, SPACES, USER_ID, DEFAULT_TAGS, DRAFT_TAG, GOOD_AS_IS_TAG, DEFAULT_PRIORITY
from ..helpers import read_content, error, format_tasks, fetch_all_comments

PRIORITY_MAP = {"urgent": 1, "high": 2, "normal": 3, "low": 4}

# Pattern for task ID queries like PER-39, JMP-12, MTM-8
_TASK_ID_PATTERN = re.compile(r"^[A-Z]+-\d+$")


def _parse_fields(args):
    """Parse --fields arg into a list, or None."""
    raw = getattr(args, "fields", None)
    if not raw:
        return None
    return [f.strip() for f in raw.split(",") if f.strip()]


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

    all_tasks = []
    page = 0
    while True:
        params["page"] = str(page)
        resp = client.get_v2(f"/list/{list_id}/task", params=params)
        tasks = resp.get("tasks", [])
        all_tasks.extend(tasks)
        if resp.get("last_page", False):
            break
        page += 1

    fields = _parse_fields(args)
    full = getattr(args, "full", False)
    formatted = format_tasks(all_tasks, full=full, fields=fields)
    return {"tasks": formatted, "count": len(formatted)}


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


def cmd_tasks_create(client, args):
    if not args.space:
        error("--space is required for task creation (needed to resolve target list)")

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

    all_tasks = []
    page = 0
    while True:
        params["page"] = str(page)
        resp = client.get_v2(f"/team/{WORKSPACE_ID}/task", params=params)
        tasks = resp.get("tasks", [])
        all_tasks.extend(tasks)
        if resp.get("last_page", False):
            break
        page += 1

    if name_prefix:
        all_tasks = [
            task
            for task in all_tasks
            if task.get("name", "").startswith(name_prefix)
        ]

    fields = _parse_fields(args)
    full = getattr(args, "full", False)
    formatted = format_tasks(all_tasks, full=full, fields=fields)
    return {"tasks": formatted, "count": len(formatted)}


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
