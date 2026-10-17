"""Shared task helpers used across read and write flows."""

import re
from datetime import datetime, timedelta

from ...helpers import error, format_tasks, resolve_space_id

PRIORITY_MAP = {"urgent": 1, "high": 2, "normal": 3, "low": 4}
DEFAULT_TASK_PAGE_BUDGET = 2
_TASK_ID_PATTERN = re.compile(r"^[A-Z]+-\d+$")


def _task_filter_params(args):
    """Validate filters and translate whole local dates into API bounds."""
    if getattr(args, "untagged", False) and getattr(args, "tags", None):
        error("--untagged cannot be combined with --tag")
    bounds = {}
    for flag, key, next_day in [
        ("due_before", "due_date_lt", False),
        ("due_after", "due_date_gt", True),
    ]:
        raw = getattr(args, flag, None)
        if raw is None:
            continue
        try:
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
                raise ValueError
            day = datetime.strptime(raw, "%Y-%m-%d")
            if next_day:
                day += timedelta(days=1)
            bounds[key] = int(day.timestamp() * 1000) - int(next_day)
        except (ValueError, OverflowError, OSError):
            error(f"Invalid --{flag.replace('_', '-')} value (expected YYYY-MM-DD): {raw}")
    if getattr(args, "overdue", False):
        now = int(datetime.now().timestamp() * 1000)
        bounds["due_date_lt"] = min(bounds.get("due_date_lt", now), now)
    if ("due_date_gt" in bounds and "due_date_lt" in bounds
            and bounds["due_date_gt"] + 1 >= bounds["due_date_lt"]):
        error("Due-date filters define an empty range")
    return bounds


def _filter_task_results(tasks, args):
    """Apply tag and overdue-status filters before the output limit."""
    required = getattr(args, "tags", None)
    if required:
        tasks = _filter_by_tags(tasks, required)
    excluded = {tag.lower() for tag in (getattr(args, "exclude_tags", None) or [])}
    result = []
    for task in tasks:
        tags = {tag.get("name", "").lower() for tag in task.get("tags", [])}
        if (getattr(args, "untagged", False) and tags) or tags & excluded:
            continue
        if getattr(args, "overdue", False):
            status = task.get("status") or {}
            kind = status.get("type", "") if isinstance(status, dict) else status
            if not task.get("due_date") or kind.lower() in {"closed", "done", "complete", "completed"}:
                continue
        result.append(task)
    return result


def _parse_fields(args):
    """Parse --fields arg into a list, or None."""
    raw = getattr(args, "fields", None)
    if not raw:
        return None
    return [field.strip() for field in raw.split(",") if field.strip()]


def _format_and_wrap(tasks, args):
    """Format tasks and wrap in the standard response dict."""
    limit = getattr(args, "limit", None)
    if limit is not None:
        tasks = tasks[:limit]
    fields = _parse_fields(args)
    full = getattr(args, "full", False)
    formatted = format_tasks(tasks, full=full, fields=fields)
    return {"tasks": formatted, "count": len(formatted)}


def _budget_metadata(pages_fetched, complete):
    return {
        "pages_fetched": pages_fetched,
        "results_complete": complete,
        "results_truncated": not complete,
    }


def _resolve_priority(priority_arg):
    """Resolve a priority name or number to the API integer value."""
    if priority_arg is None:
        return None
    if priority_arg in PRIORITY_MAP:
        return PRIORITY_MAP[priority_arg]
    if priority_arg.isdigit() and int(priority_arg) in (1, 2, 3, 4):
        return int(priority_arg)
    error(f"Invalid priority: {priority_arg}. Use: urgent, high, normal, low (or 1-4)")


def _first_folderless_list_id(client, space_id):
    """Return the first folderless list ID in a space, via API lookup."""
    response = client.get_v2(f"/space/{space_id}/list", allow_dry_run=True)
    lists = response.get("lists", [])
    if not lists:
        error(
            f"Space {space_id} has no folderless lists. "
            "Pass --list <list_id> to target a list inside a folder."
        )
    return lists[0]["id"]


def _resolve_list_id(args, client=None):
    """Resolve the target list ID from --list or --space args."""
    if hasattr(args, "list_id") and args.list_id:
        return args.list_id
    if hasattr(args, "space") and args.space:
        if client is None:
            error(
                f"Space {args.space} needs an API lookup but no client is available. "
                "Use --list <list_id> instead."
            )
        spaces = client.runtime.spaces
        space_cfg = spaces.get(args.space)
        if space_cfg and space_cfg.get("list_id"):
            return space_cfg["list_id"]
        space_id = resolve_space_id(args.space, spaces=spaces)
        return _first_folderless_list_id(client, space_id)
    error("Provide either --space <name|id> or --list <list_id>")


def _scope_items(response, key, require_complete):
    if require_complete and not isinstance(response.get(key), list):
        error(f"Cannot establish scan completeness: missing {key} inventory")
    return response.get(key, [])


def _resolve_scope_list_ids(client, space_arg, include_archived=False, allow_empty=False,
                            require_complete=False):
    """Expand a space to every list ID it owns for search scoping.

    This includes folderless lists plus lists nested under each folder so
    `tasks search --space ...` behaves like a whole-space search. Returned IDs
    are de-duplicated in discovery order because folder traversals can surface
    overlapping list references.

    `include_archived=True` forwards `archived=true` through the folderless,
    folder, and per-folder list lookups so callers can build archived-only scope
    expansions. When no lists are found, `allow_empty=True` returns `[]` so the
    caller can decide whether to skip a pass; otherwise this raises the standard
    "no lists available" CLI error.
    """
    space_id = resolve_space_id(space_arg, spaces=client.runtime.spaces)
    params = {"archived": "true"} if include_archived else None

    folderless_response = client.get_v2(
        f"/space/{space_id}/list", params=params, allow_dry_run=True
    )
    folderless_lists = _scope_items(folderless_response, "lists", require_complete)

    folder_response = client.get_v2(
        f"/space/{space_id}/folder", params=params, allow_dry_run=True
    )
    folders = _scope_items(folder_response, "folders", require_complete)

    list_ids = [item["id"] for item in folderless_lists]
    for folder in folders:
        folder_lists_response = client.get_v2(
            f"/folder/{folder['id']}/list", params=params, allow_dry_run=True
        )
        list_ids.extend(item["id"] for item in _scope_items(folder_lists_response, "lists", require_complete))

    list_ids = list(dict.fromkeys(list_ids))
    if not list_ids and not allow_empty:
        error(
            f"Space {space_arg} has no lists available for search scoping. "
            "Pass --list <list_id> or --folder <folder_id> instead."
        )
    return list_ids


def _parse_search_custom_fields(raw_filters):
    """Parse repeatable FIELD_ID=VALUE search filters for the ClickUp API."""
    parsed = []
    for raw_filter in raw_filters or []:
        field_id, separator, value = raw_filter.partition("=")
        if not separator or not field_id or value == "":
            error(
                "Invalid --custom-field value: "
                f"{raw_filter}. Use FIELD_ID=VALUE"
            )
        parsed.append({"field_id": field_id, "operator": "=", "value": value})
    return parsed


def _paginate_tasks(client, path, params, budget=None, require_complete=False):
    """Fetch paginated task results until exhaustion or the shared page budget.

    The optional mutable `budget` lets callers cap multiple related scans, such
    as active plus archived passes, under one bounded default.
    """
    all_tasks = []
    page = 0
    pages_fetched = 0
    complete = True
    seen = set()
    while True:
        if budget is not None and budget["remaining"] <= 0:
            complete = False
            break
        params["page"] = str(page)
        response = client.get_v2(path, params=params, allow_dry_run=require_complete)
        pages_fetched += 1
        if budget is not None:
            budget["remaining"] -= 1
        tasks = response.get("tasks", [])
        if require_complete:
            if not isinstance(response.get("tasks"), list) or not isinstance(response.get("last_page"), bool):
                error("Cannot establish task scan completeness: invalid pagination response")
            ids = {task.get("id") for task in tasks}
            if None in ids or (tasks and ids <= seen) or (not tasks and not response["last_page"]):
                error("Cannot establish task scan completeness: task pagination did not advance")
            if any(not isinstance(task.get("tags"), list) for task in tasks):
                error("Cannot establish task scan completeness: missing task tags")
            seen.update(ids)
        all_tasks.extend(tasks)
        if response.get("last_page", False):
            break
        if budget is not None and budget["remaining"] <= 0:
            complete = False
            break
        page += 1
    return {"tasks": all_tasks, "pages_fetched": pages_fetched, "complete": complete}


def _filter_by_tags(tasks, tag_names):
    """Client-side filter: keep tasks that have all specified tags."""
    required = {tag.lower() for tag in tag_names}
    return [
        task
        for task in tasks
        if required <= {tag.get("name", "").lower() for tag in task.get("tags", [])}
    ]


def _infer_space_from_list(client, list_id):
    """Look up a list via API to find its parent space."""
    response = client.get_v2(f"/list/{list_id}", allow_dry_run=True)
    space_info = response.get("space", {})
    space_id = space_info.get("id")
    if not space_id:
        return None
    for name, config in client.runtime.spaces.items():
        if config.get("space_id") == str(space_id):
            return name
    return str(space_id)
