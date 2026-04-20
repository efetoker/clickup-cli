"""Custom field discovery commands."""

from ..helpers import error, resolve_space_id


def _resolve_list_scope(client, args):
    requested_list_id = getattr(args, "list_id", None)
    if requested_list_id:
        return {
            "space": getattr(args, "space", None),
            "requested_list_id": requested_list_id,
            "resolved_list_id": requested_list_id,
        }

    space = getattr(args, "space", None)
    if not space:
        error("Provide either --space <name|id> or --list <list_id>")

    spaces = client.runtime.spaces
    space_cfg = spaces.get(space)
    resolved_list_id = space_cfg.get("list_id") if space_cfg else None
    if not resolved_list_id:
        space_id = resolve_space_id(space, spaces=spaces)
        response = client.get_v2(f"/space/{space_id}/list", allow_dry_run=True)
        lists = response.get("lists", [])
        if not lists:
            error(
                f"Space {space} has no folderless lists. "
                "Pass --list <list_id> to target a list inside a folder."
            )
        resolved_list_id = lists[0]["id"]

    return {
        "space": space,
        "requested_list_id": None,
        "resolved_list_id": resolved_list_id,
    }


def register_parser(subparsers, F):
    fields_parser = subparsers.add_parser(
        "fields",
        formatter_class=F,
        help="Discover custom fields for a list or space",
        description="""\
Inspect custom field metadata before searching or creating tasks.

Subcommands:
  list  - list custom fields for a list or a space's default list

Use --list to target a specific list directly, or --space to use the same
default-list resolution pattern used elsewhere in the CLI. If both are given,
--list takes precedence.""",
        epilog="""\
examples:
  clickup fields list --space <name>
  clickup fields list --list 12345""",
    )
    fields_sub = fields_parser.add_subparsers(dest="command", required=True)

    list_parser = fields_sub.add_parser(
        "list",
        formatter_class=F,
        help="List custom fields in scope",
    )
    list_parser.add_argument("--space", type=str, help="Space name or raw ID")
    list_parser.add_argument(
        "--list",
        type=str,
        dest="list_id",
        help="List ID (overrides --space)",
    )


def cmd_fields_list(client, args):
    scope = _resolve_list_scope(client, args)
    response = client.get_v2(f"/list/{scope['resolved_list_id']}/field")
    fields = response.get("fields", [])
    return {"fields": fields, "count": len(fields), "scope": scope}


COMMAND_MANIFEST = {
    "group": "fields",
    "register_parser": register_parser,
    "handlers": {"list": cmd_fields_list},
}
