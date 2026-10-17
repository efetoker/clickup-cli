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
        help="Discover custom fields at List, Folder, Space, or Workspace scope",
        description="""\
Inspect custom field metadata before searching or creating tasks.

Subcommands:
  list  - inspect List, Folder, Space, or Workspace custom fields

Use --list to target a specific list directly, or --space to use the same
default-list resolution pattern used elsewhere in the CLI. If both are given,
--list takes precedence. Use --space-level, --folder, or --workspace for the
other scopes; run fields list --help for details.""",
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
        description="""\
List custom fields for one ClickUp list.

Use --list to inspect a specific list directly. If --list is omitted, --space
resolves to the configured default list for that space; if no default list is
configured, the CLI uses the first folderless list returned by ClickUp.

The response includes fields, count, and scope. The scope object reports the
requested space/list and the resolved list ID that was inspected.

Use --space <name|id> --space-level for Space-level fields, --folder <id> for
Folder-level fields, or --workspace for Workspace-level fields. These scopes
are not recursive inventories of lower-level fields. Space/Folder endpoints
may also return inherited Workspace fields. New scope selectors cannot be
combined with --list or with one another.""",
        epilog="""\
examples:
  clickup fields list --space <name>
  clickup fields list --list 12345

returns:
  {"fields": [...], "count": N, "scope": {"resolved_list_id": "..."}}

notes:
  Folder-contained list fields require --list because the --space fallback
  can only inspect the configured default list or first folderless list.""",
    )
    list_parser.add_argument("--space", type=str, help="Space name or raw ID")
    list_parser.add_argument(
        "--list",
        type=str,
        dest="list_id",
        help="List ID (overrides --space)",
    )
    scopes = list_parser.add_mutually_exclusive_group()
    scopes.add_argument("--space-level", action="store_true", help="Inspect Space-level fields; requires --space")
    scopes.add_argument("--folder", dest="folder_id", help="Inspect Folder-level fields by raw folder ID")
    scopes.add_argument("--workspace", action="store_true", help="Inspect fields on the configured Workspace")


def cmd_fields_list(client, args):
    space_level = getattr(args, "space_level", False)
    folder_id = getattr(args, "folder_id", None)
    workspace = getattr(args, "workspace", False)
    if sum(bool(value) for value in (space_level, folder_id, workspace)) > 1:
        error("Choose only one of --space-level, --folder, or --workspace")
    if space_level or folder_id or workspace:
        if getattr(args, "list_id", None) or (not space_level and getattr(args, "space", None)):
            error("New field scopes cannot be combined with --list or unrelated --space")
        if space_level:
            if not getattr(args, "space", None):
                error("--space-level requires --space <name|id>")
            resolved = resolve_space_id(args.space, spaces=client.runtime.spaces)
            scope = {"type": "space", "space": args.space, "resolved_space_id": resolved}
            path = f"/space/{resolved}/field"
        elif folder_id:
            scope = {"type": "folder", "resolved_folder_id": folder_id}
            path = f"/folder/{folder_id}/field"
        else:
            resolved = client.runtime.workspace_id
            scope = {"type": "workspace", "resolved_workspace_id": resolved}
            path = f"/team/{resolved}/field"
        response = client.get_v2(path)
        fields = response.get("fields", [])
        return {"fields": fields, "count": len(fields), "scope": scope}
    scope = _resolve_list_scope(client, args)
    response = client.get_v2(f"/list/{scope['resolved_list_id']}/field")
    fields = response.get("fields", [])
    return {"fields": fields, "count": len(fields), "scope": scope}


COMMAND_MANIFEST = {
    "group": "fields",
    "register_parser": register_parser,
    "handlers": {"list": cmd_fields_list},
}
