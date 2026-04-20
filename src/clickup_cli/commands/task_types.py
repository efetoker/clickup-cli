"""Task type discovery commands."""

from .fields import _resolve_list_scope


def register_parser(subparsers, F):
    task_types_parser = subparsers.add_parser(
        "task-types",
        formatter_class=F,
        help="Discover custom task types for the workspace",
        description="""\
Inspect custom task type metadata before task creation flows.

Subcommands:
  list  - list workspace-level custom task types

The ClickUp endpoint is workspace-scoped. --space and --list are accepted for
UX consistency and echoed back in the JSON response, but they do not narrow the
API result.""",
        epilog="""\
examples:
  clickup task-types list --space <name>
  clickup task-types list --list 12345""",
    )
    task_types_sub = task_types_parser.add_subparsers(dest="command", required=True)

    list_parser = task_types_sub.add_parser(
        "list",
        formatter_class=F,
        help="List workspace custom task types",
    )
    list_parser.add_argument("--space", type=str, help="Space name or raw ID")
    list_parser.add_argument(
        "--list",
        type=str,
        dest="list_id",
        help="List ID (overrides --space)",
    )


def cmd_task_types_list(client, args):
    scope = _resolve_list_scope(client, args) if getattr(args, "space", None) or getattr(args, "list_id", None) else {
        "space": None,
        "requested_list_id": None,
        "resolved_list_id": None,
    }
    response = client.get_v2(f"/team/{client.runtime.workspace_id}/custom_item")
    task_types = response.get("custom_items", [])
    result = {
        "task_types": task_types,
        "count": len(task_types),
        "scope": scope,
        "available": bool(task_types),
        "scope_applied": False,
        "source": "workspace_custom_item_types",
    }
    if not task_types:
        result["reason"] = "workspace_has_no_custom_item_types"
    return result


COMMAND_MANIFEST = {
    "group": "task-types",
    "register_parser": register_parser,
    "handlers": {"list": cmd_task_types_list},
}
