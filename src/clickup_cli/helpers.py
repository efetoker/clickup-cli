"""Shared helper functions for output, errors, and content reading."""

import json
import sys


def output(data, pretty=False):
    """Print JSON to stdout."""
    if pretty:
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        print(json.dumps(data, ensure_ascii=False))


def error(msg):
    """Print error to stderr and exit."""
    print(f"Error: {msg}", file=sys.stderr)
    sys.exit(1)


def read_content(inline, file_path, flag_name="--content"):
    """Read content from inline string or file path. Returns string or None."""
    if inline and file_path:
        error(f"Cannot use both {flag_name} and {flag_name}-file")
    if file_path:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            error(f"File not found: {file_path}")
    return inline


def resolve_space_id(space_arg):
    """Resolve a space name (from config) or raw space ID."""
    from .config import SPACES

    if space_arg in SPACES:
        return SPACES[space_arg]["space_id"]
    return space_arg


def fetch_all_comments(client, task_id):
    """Fetch all comments for a task, paginating through all pages."""
    resp = client.get_v2(f"/task/{task_id}/comment")
    comments = resp.get("comments", [])
    all_comments = list(comments)
    while len(comments) >= 25:
        last = comments[-1]
        params = {"start": str(last["date"]), "start_id": last["id"]}
        resp = client.get_v2(f"/task/{task_id}/comment", params=params)
        comments = resp.get("comments", [])
        if not comments:
            break
        all_comments.extend(comments)
    return all_comments


# Default fields for compact task output
COMPACT_FIELDS = ["id", "name", "status", "priority", "url"]

# Reverse map for priority numbers to names
PRIORITY_NAMES = {1: "urgent", 2: "high", 3: "normal", 4: "low"}


def compact_task(task):
    """Return a compact view of a task with only essential fields."""
    status = task.get("status")
    status_name = status.get("status") if isinstance(status, dict) else status

    priority = task.get("priority")
    if isinstance(priority, dict) and priority:
        priority_name = priority.get("priority") or PRIORITY_NAMES.get(
            priority.get("orderindex"), "unknown"
        )
    else:
        priority_name = None

    return {
        "id": task.get("id"),
        "name": task.get("name"),
        "status": status_name,
        "priority": priority_name,
        "url": task.get("url"),
    }


def filter_task_fields(task, fields):
    """Return only the requested fields from a task.

    Supports nested status/priority extraction: if 'status' or 'priority'
    is requested, returns the string name rather than the nested object.
    """
    result = {}
    for field in fields:
        if field == "status":
            status = task.get("status")
            result["status"] = (
                status.get("status") if isinstance(status, dict) else status
            )
        elif field == "priority":
            priority = task.get("priority")
            if isinstance(priority, dict) and priority:
                result["priority"] = priority.get("priority") or PRIORITY_NAMES.get(
                    priority.get("orderindex"), "unknown"
                )
            else:
                result["priority"] = None
        else:
            result[field] = task.get(field)
    return result


def format_tasks(tasks, full=False, fields=None):
    """Apply compact/fields/full formatting to a list of tasks.

    - full=True: return raw API objects unchanged
    - fields: return only those fields per task
    - default: return compact view (id, name, status, priority, url)
    """
    if full:
        return tasks
    if fields:
        return [filter_task_fields(t, fields) for t in tasks]
    return [compact_task(t) for t in tasks]
