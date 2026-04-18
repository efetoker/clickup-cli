"""Shared helper functions for output, errors, and content reading."""

import argparse
import json
import sys


def add_id_argument(parser, name, help_text):
    """Add an argument that accepts both positional and --flag forms.

    This adds both so either style works (e.g. `command abc123` or `command --task-id abc123`).

    Example:
        add_id_argument(parser, 'task_id', 'ClickUp task ID')
        # Accepts: `command abc123` OR `command --task-id abc123`
    """
    parser.add_argument(name, nargs="?", default=None, help=help_text)
    flag = f"--{name.replace('_', '-')}"
    parser.add_argument(
        flag, dest=f"_{name}_flag", default=None, help=argparse.SUPPRESS
    )


def resolve_id_args(args):
    """Resolve positional-or-flag ID arguments after parsing.

    For each _<name>_flag attribute, merges with the positional <name>:
    - If flag provided, use it
    - If positional provided, use it
    - If both provided, error
    - If neither provided, error with helpful message
    """
    flag_attrs = [a for a in vars(args) if a.endswith("_flag") and a.startswith("_")]
    for flag_attr in flag_attrs:
        base_attr = flag_attr[1:-5]  # strip _ prefix and _flag suffix
        flag_val = getattr(args, flag_attr)
        pos_val = getattr(args, base_attr, None)
        flag_name = f"--{base_attr.replace('_', '-')}"

        if flag_val is not None and pos_val is not None:
            error(f"Provide {base_attr} as positional or {flag_name}, not both")

        if flag_val is not None:
            setattr(args, base_attr, flag_val)
        elif pos_val is None:
            error(f"Missing required argument: {base_attr} (positional or {flag_name})")

        delattr(args, flag_attr)


def output(data, pretty=False):
    """Print JSON to stdout."""
    print(json.dumps(data, indent=2 if pretty else None, ensure_ascii=False))


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


def resolve_space_id(space_arg, spaces=None):
    """Resolve a space name (from config/runtime) or raw space ID."""
    if spaces is None:
        from .config import SPACES

        spaces = SPACES

    if space_arg in spaces:
        return spaces[space_arg]["space_id"]
    # If it's not numeric, it's likely a misspelled config name
    if not space_arg.isdigit():
        available = ", ".join(sorted(spaces.keys())) if spaces else "(none configured)"
        error(f"Unknown space: {space_arg}. Available: {available}")
    return space_arg


def fetch_all_comments(client, task_id, all_pages=False):
    """Fetch task comments with a bounded default and explicit exhaustive mode."""
    first_page = client.get_v2(f"/task/{task_id}/comment", params=None)
    comments = first_page.get("comments", [])
    if not comments:
        return {"comments": [], "complete": True, "truncated": False}

    last = comments[-1]
    params = {"start": str(last["date"]), "start_id": last["id"]}
    next_page = client.get_v2(f"/task/{task_id}/comment", params=params)
    next_comments = next_page.get("comments", [])

    if not all_pages:
        return {
            "comments": comments,
            "complete": not bool(next_comments),
            "truncated": bool(next_comments),
        }

    all_comments = list(comments)
    while next_comments:
        all_comments.extend(next_comments)
        last = next_comments[-1]
        params = {"start": str(last["date"]), "start_id": last["id"]}
        next_page = client.get_v2(f"/task/{task_id}/comment", params=params)
        next_comments = next_page.get("comments", [])

    return {"comments": all_comments, "complete": True, "truncated": False}


# Default fields for compact task output
COMPACT_FIELDS = ["id", "name", "status", "priority", "url"]

# Reverse map for priority numbers to names
PRIORITY_NAMES = {1: "urgent", 2: "high", 3: "normal", 4: "low"}


def _extract_status(task):
    """Extract the status string from a task's status field."""
    status = task.get("status")
    return status.get("status") if isinstance(status, dict) else status


def _normalize_status_shape(task):
    """Return a copy of `task` where the status field is always a dict.

    The ClickUp API sometimes returns status as a plain string on certain
    endpoints and as a dict ({status, color, type, orderindex}) on others.
    Normalize to the dict shape so agent scripts can always access
    `task["status"]["status"]` without defensive isinstance checks.
    """
    status = task.get("status")
    if isinstance(status, str):
        normalized = dict(task)
        normalized["status"] = {
            "status": status,
            "color": None,
            "type": None,
            "orderindex": None,
        }
        return normalized
    return task


def _extract_priority(task):
    """Extract the priority string from a task's priority field."""
    priority = task.get("priority")
    if isinstance(priority, dict) and priority:
        return priority.get("priority") or PRIORITY_NAMES.get(
            priority.get("orderindex"), "unknown"
        )
    return None


def compact_task(task):
    """Return a compact view of a task with only essential fields."""
    return {
        "id": task.get("id"),
        "name": task.get("name"),
        "status": _extract_status(task),
        "priority": _extract_priority(task),
        "url": task.get("url"),
    }


def filter_task_fields(task, fields):
    """Return only the requested fields from a task.

    Supports nested status/priority extraction: if 'status' or 'priority'
    is requested, returns the string name rather than the nested object.
    """
    extractors = {"status": _extract_status, "priority": _extract_priority}
    result = {}
    for field in fields:
        extractor = extractors.get(field)
        result[field] = extractor(task) if extractor else task.get(field)
    return result


def format_tasks(tasks, full=False, fields=None):
    """Apply compact/fields/full formatting to a list of tasks.

    - full=True: return raw API objects with status normalized to a dict shape
    - fields: return only those fields per task (status flattened to string)
    - default: return compact view (id, name, status, priority, url) —
      status is a flat string
    """
    if full:
        return [_normalize_status_shape(t) for t in tasks]
    if fields:
        return [filter_task_fields(t, fields) for t in tasks]
    return [compact_task(t) for t in tasks]
