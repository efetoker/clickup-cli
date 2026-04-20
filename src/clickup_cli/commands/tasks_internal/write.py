"""Write-oriented task handlers behind the facade."""

from datetime import datetime, timezone
import re

from ...helpers import error, read_content
from .shared import (
    _first_folderless_list_id,
    _infer_space_from_list,
    _resolve_list_id,
    _resolve_priority,
)


_TIME_ESTIMATE_RE = re.compile(r"^(\d+)([mhd])$")


def _parse_date_to_clickup_timestamp(raw, flag_name):
    """Convert YYYY-MM-DD input into ClickUp's millisecond timestamp string."""
    try:
        parsed = datetime.strptime(raw, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        error(f"Invalid {flag_name} value (expected YYYY-MM-DD): {raw}")
    return str(int(parsed.timestamp() * 1000))


def _parse_time_estimate(raw):
    """Convert compact duration strings into ClickUp milliseconds."""
    match = _TIME_ESTIMATE_RE.fullmatch(raw.strip())
    if not match:
        error(f"Invalid --time-estimate value (expected <int><m|h|d>): {raw}")

    amount = int(match.group(1))
    unit = match.group(2)
    multipliers = {"m": 60_000, "h": 3_600_000, "d": 86_400_000}
    return amount * multipliers[unit]


def _parse_points(raw):
    """Normalize points to an int when possible, otherwise a float."""
    try:
        value = float(raw)
    except ValueError:
        error(f"Invalid --points value (expected a number): {raw}")

    if value.is_integer():
        return int(value)
    return value


def _resolve_task_type(client, raw_task_type):
    """Validate an explicit task/custom item type against workspace metadata."""
    response = client.get_v2(
        f"/team/{client.runtime.workspace_id}/custom_item",
        allow_dry_run=True,
    )
    task_types = response.get("custom_items", [])
    if not task_types:
        error(
            "--task-type requires an available workspace custom item type; "
            "run `clickup task-types list` first"
        )

    for task_type in task_types:
        if task_type.get("id") == raw_task_type or task_type.get("name") == raw_task_type:
            return {"id": task_type["id"], "source": "workspace_custom_item_types"}

    error(
        f"Unknown --task-type value: {raw_task_type}. "
        "Run `clickup task-types list` to discover valid IDs."
    )


def cmd_tasks_create(client, args):
    """Create a task in the resolved target list.

    When only `--list` is provided, infer `--space` so dry-run output and error
    messages still report the same target context as normal runs.
    """
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

    start_date = getattr(args, "start_date", None)
    if start_date:
        body["start_date"] = _parse_date_to_clickup_timestamp(start_date, "--start-date")
        body["start_date_time"] = True

    due_date = getattr(args, "due_date", None)
    if due_date:
        body["due_date"] = _parse_date_to_clickup_timestamp(due_date, "--due-date")
        body["due_date_time"] = True

    time_estimate = getattr(args, "time_estimate", None)
    if time_estimate:
        body["time_estimate"] = _parse_time_estimate(time_estimate)

    points = getattr(args, "points", None)
    if points:
        body["points"] = _parse_points(points)

    custom_fields = [
        _parse_custom_field(raw)
        for raw in (getattr(args, "custom_fields", None) or [])
    ]

    task_type = None
    raw_task_type = getattr(args, "task_type", None)
    if raw_task_type:
        task_type = _resolve_task_type(client, raw_task_type)
        body["custom_item_id"] = task_type["id"]

    if client.dry_run:
        if custom_fields or task_type:
            return {
                "dry_run": True,
                "action": "create_task",
                "create_body": body,
                "post_create_custom_fields": [
                    {"field_id": field_id, "value": value}
                    for field_id, value in custom_fields
                ],
                "task_type": task_type,
                "space": args.space,
                "list_id": list_id,
            }
        return {
            "dry_run": True,
            "body": body,
            "space": args.space,
            "list_id": list_id,
        }

    result = client.post_v2(f"/list/{list_id}/task", data=body)

    for field_id, value in custom_fields:
        client.post_v2(f"/task/{result['id']}/field/{field_id}", data={"value": value})

    if custom_fields:
        return client.get_v2(f"/task/{result['id']}")

    return result


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
    """Apply core field updates plus per-tag and per-custom-field mutations.

    The ClickUp API splits these concerns across endpoints, so dry-run returns a
    single execution plan even though live runs may make multiple requests.
    """
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

    add_assignees = [int(user_id) for user_id in (getattr(args, "add_assignees", None) or [])]
    rem_assignees = [int(user_id) for user_id in (getattr(args, "remove_assignees", None) or [])]
    if add_assignees or rem_assignees:
        body["assignees"] = {"add": add_assignees, "rem": rem_assignees}

    add_tags = [tag.lower() for tag in (getattr(args, "add_tags", None) or [])]
    remove_tags = [tag.lower() for tag in (getattr(args, "remove_tags", None) or [])]
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
        "custom_fields": [{"field_id": field_id, "value": value} for field_id, value in custom_fields],
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
        result = client.get_v2(f"/task/{args.task_id}")

    return result


def cmd_tasks_delete(client, args):
    """Delete a task by ID."""
    if client.dry_run:
        return {"dry_run": True, "action": "delete", "task_id": args.task_id}
    client.delete_v2(f"/task/{args.task_id}")
    return {"status": "ok", "action": "deleted", "task_id": args.task_id}


def cmd_tasks_move(client, args):
    """Move a task by resolving `--to` as a space alias or raw list ID."""
    space = client.runtime.spaces.get(args.to_list)
    if space:
        list_id = space.get("list_id") or _first_folderless_list_id(client, space["space_id"])
    else:
        list_id = args.to_list

    if client.dry_run:
        return {
            "dry_run": True,
            "action": "move",
            "task_id": args.task_id,
            "destination_list_id": list_id,
        }
    return client.put_v3(
        f"/workspaces/{client.runtime.workspace_id}/tasks/{args.task_id}/home_list/{list_id}"
    )


def cmd_tasks_depend(client, args):
    """Dispatch `tasks depend {add,remove,list}` subcommands."""
    subcommand = getattr(args, "subcommand", None)
    if subcommand == "add":
        return _tasks_depend_add(client, args)
    if subcommand == "remove":
        return _tasks_depend_remove(client, args)
    if subcommand == "list":
        return _tasks_depend_list(client, args)
    error(f"Unknown tasks depend subcommand: {subcommand}")


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
    depends_on = [dependency for dependency in dependencies if dependency.get("task_id") == args.task_id]
    depended_on_by = [dependency for dependency in dependencies if dependency.get("depends_on") == args.task_id]
    return {
        "task_id": args.task_id,
        "depends_on": depends_on,
        "depended_on_by": depended_on_by,
    }


def cmd_tasks_merge(client, args):
    """Merge source tasks into a target task."""
    source_ids = [task_id.strip() for task_id in args.source_ids.split(",")]

    if client.dry_run:
        return {
            "dry_run": True,
            "action": "merge",
            "target_task_id": args.task_id,
            "source_task_ids": source_ids,
        }
    return client.post_v2(f"/task/{args.task_id}/merge", data={"task_ids": source_ids})
