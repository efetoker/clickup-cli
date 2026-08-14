"""Space command handlers — list, get, create, update, delete, privacy."""

from ..helpers import add_id_argument, error, resolve_space_id
from .privacy import handle_privacy_request, register_privacy_subcommand

DEFAULT_SPACE_FEATURES = {
    "due_dates": {"enabled": True, "start_date": False, "remap_due_dates": False, "remap_closed_due_date": False},
    "time_tracking": {"enabled": True},
    "tags": {"enabled": True},
    "time_estimates": {"enabled": True},
    "checklists": {"enabled": True},
    "custom_fields": {"enabled": True},
    "remap_dependencies": {"enabled": True},
    "dependency_warning": {"enabled": True},
    "portfolios": {"enabled": True},
}


def _add_assignee_mode_flags(parser, *, required):
    """Add a bounded assignee-mode toggle for space mutations."""
    mode = parser.add_mutually_exclusive_group(required=required)
    mode.add_argument(
        "--multiple-assignees",
        dest="multiple_assignees",
        action="store_const",
        const=True,
        default=None,
        help="Allow multiple assignees per task",
    )
    mode.add_argument(
        "--single-assignee",
        dest="multiple_assignees",
        action="store_const",
        const=False,
        default=None,
        help="Restrict tasks to a single assignee",
    )


def _build_space_update_body(current_space, args):
    """Preserve required space fields while applying bounded CLI updates."""
    body = {
        "name": current_space["name"],
        "color": current_space["color"],
        "private": current_space["private"],
        "admin_can_manage": current_space["admin_can_manage"],
        "multiple_assignees": current_space["multiple_assignees"],
        "features": current_space["features"],
    }

    changed = False
    if args.name:
        body["name"] = args.name
        changed = True
    if args.multiple_assignees is not None:
        body["multiple_assignees"] = args.multiple_assignees
        changed = True

    if not changed:
        error("Nothing to update — provide at least one of: --name, --multiple-assignees, --single-assignee")

    return body


def register_parser(subparsers, F):
    """Register all spaces subcommands on the given subparsers object."""
    spaces_parser = subparsers.add_parser(
        "spaces",
        formatter_class=F,
        help="Full space CRUD: list, get, create, update, delete",
        description="""\
Inspect workspace spaces — list all spaces, view space details, create,
update, delete, discover valid statuses, and toggle space privacy.

Subcommands:
  list      — list all spaces in the workspace
  get       — fetch full details of a specific space
  create    — create a new space in the current workspace (mutating)
  update    — update a space's bounded attributes (mutating)
  delete    — delete a space (destructive)
  statuses  — list valid statuses for a space
  privacy   — make a space private or public (mutating)

list / get / statuses are read-only. create / update / delete / privacy
are mutating and support --dry-run. Configured space names and raw
ClickUp space IDs are both accepted where a target space is required.""",
        epilog="""\
examples:
  clickup spaces list
  clickup spaces get <space>
  clickup spaces create --name "Platform" --multiple-assignees
  clickup spaces update <space> --name "Platform API"
  clickup --dry-run spaces delete <space>
  clickup spaces statuses <space>
  clickup spaces privacy <space> --private
  clickup --dry-run spaces privacy <space> --public

notes:
  Read commands hit the API directly — no caching.
  Use 'spaces statuses' to find valid status names before setting
  task statuses, avoiding "Status does not exist" errors.""",
    )
    spaces_sub = spaces_parser.add_subparsers(dest="command", required=True)

    # spaces list
    spaces_sub.add_parser(
        "list",
        formatter_class=F,
        help="List all spaces in the workspace",
        description="""\
List all spaces in the workspace. Returns space names, IDs, and basic
metadata for every space the authenticated user can access.

Use this for discovery — find available spaces and their IDs without
relying on hardcoded configuration.""",
        epilog="""\
returns:
  {"spaces": [...], "count": N}

examples:
  clickup spaces list
  clickup --pretty spaces list""",
    )

    # spaces get
    sg = spaces_sub.add_parser(
        "get",
        formatter_class=F,
        help="Fetch full details of a specific space",
        description="""\
Fetch full details of a space including statuses, features, and members.

Accepts a configured space name or a raw ClickUp space ID.
Use 'spaces list' to discover available spaces.""",
        epilog="""\
returns:
  One space JSON object with all fields (statuses, features, members, etc.)

examples:
  clickup spaces get <space>
  clickup spaces get 901810200000
  clickup --pretty spaces get <space>""",
    )
    add_id_argument(sg, "space", "Space name (from config) or raw space ID")

    # spaces create
    sc = spaces_sub.add_parser(
        "create",
        formatter_class=F,
        help="Create a new space in the current workspace",
        description="""\
Create a new space in the current runtime workspace. This is a mutating
command.

Use --dry-run to preview the request body without creating the space.
Global flags may appear before or after the command group:
  clickup --dry-run spaces create --name "Platform" --multiple-assignees""",
        epilog="""\
returns:
  The created space object from the API.

examples:
  clickup spaces create --name "Platform" --multiple-assignees
  clickup --dry-run spaces create --name "Platform" --single-assignee""",
    )
    sc.add_argument("--name", required=True, help="Space name (required)")
    _add_assignee_mode_flags(sc, required=True)

    # spaces update
    su = spaces_sub.add_parser(
        "update",
        formatter_class=F,
        help="Update a space (name, assignee mode)",
        description="""\
Update a space's bounded attributes. This is a mutating command.

At least one mutable field is required: --name, --multiple-assignees, or
--single-assignee. Use --dry-run to preview the merged request body
without applying changes.""",
        epilog="""\
returns:
  The updated space object from the API.

examples:
  clickup spaces update <space> --name "Platform API"
  clickup --dry-run spaces update <space> --multiple-assignees
  clickup spaces update --space <space> --single-assignee""",
    )
    add_id_argument(su, "space", "Space name (from config) or raw space ID to update")
    su.add_argument("--name", type=str, help="New space name")
    _add_assignee_mode_flags(su, required=False)

    # spaces delete
    sd = spaces_sub.add_parser(
        "delete",
        formatter_class=F,
        help="Delete a space (destructive)",
        description="""\
Delete a space permanently. This is a destructive, irreversible command.

Deleting a space removes its folders, lists, and tasks. Use with extreme
caution.

Use --dry-run to preview the operation without deleting anything.""",
        epilog="""\
returns:
  {"status": "ok", "action": "deleted", "space_id": "..."}

examples:
  clickup --dry-run spaces delete <space>
  clickup spaces delete --space <space>""",
    )
    add_id_argument(sd, "space", "Space name (from config) or raw space ID to delete")

    # spaces statuses
    ss = spaces_sub.add_parser(
        "statuses",
        formatter_class=F,
        help="List valid statuses for a space",
        description="""\
List the valid workflow statuses for a space. Returns the status name,
type (open, closed, custom), color, and order.

Use this before setting a task status to avoid "Status does not exist"
errors. Status names are space-specific — each space has its own set.""",
        epilog="""\
returns:
  {"space": "<name>", "statuses": [...], "count": N}

  Each status has: status (name), type, color, orderindex.

examples:
  clickup spaces statuses <space>
  clickup spaces statuses 901810200000
  clickup --pretty spaces statuses <space>

notes:
  Accepts a configured space name or raw space ID.
  Statuses can only be modified via the ClickUp UI, not the API.""",
    )
    add_id_argument(ss, "space", "Space name (from config) or raw space ID")

    register_privacy_subcommand(
        spaces_sub,
        F,
        object_type="space",
        id_argument="space",
        id_help="Space name (from config) or raw space ID",
        description="""\
Toggle the privacy of a space via the v3 ACLs endpoint. This flips the
private/public boolean only — it does not grant or revoke individual
member or guest access. Use the ClickUp UI for granular sharing.

Exactly one of --private or --public is required.

This is a mutating command. Use --dry-run to preview the request body.""",
        epilog="""\
returns:
  {"status": "ok", "action": "set_privacy",
   "object_type": "space", "object_id": "...", "private": true|false}

examples:
  clickup spaces privacy <space> --private
  clickup spaces privacy <space> --public
  clickup spaces privacy --space <space> --private
  clickup --dry-run spaces privacy 901810200000 --private

notes:
  Accepts a configured space name or raw space ID.
  Hits PATCH /v3/workspaces/{wid}/space/{id}/acls.""",
    )


def cmd_spaces_list(client, args):
    """List all spaces in the workspace."""
    resp = client.get_v2(f"/team/{client.runtime.workspace_id}/space")
    spaces = resp.get("spaces", [])
    return {"spaces": spaces, "count": len(spaces)}


def cmd_spaces_get(client, args):
    """Get full details of a specific space."""
    space_id = resolve_space_id(args.space)
    return client.get_v2(f"/space/{space_id}")


def cmd_spaces_create(client, args):
    """Create a space in the current runtime workspace."""
    body = {
        "name": args.name,
        "multiple_assignees": args.multiple_assignees,
        "features": DEFAULT_SPACE_FEATURES,
    }

    if client.dry_run:
        return {
            "dry_run": True,
            "action": "create_space",
            "workspace_id": client.runtime.workspace_id,
            "body": body,
        }

    return client.post_v2(f"/team/{client.runtime.workspace_id}/space", data=body)


def cmd_spaces_update(client, args):
    """Update a space's bounded attributes."""
    space_id = resolve_space_id(args.space)

    if not args.name and args.multiple_assignees is None:
        error("Nothing to update — provide at least one of: --name, --multiple-assignees, --single-assignee")

    current_space = client.get_v2(f"/space/{space_id}", allow_dry_run=True)
    body = _build_space_update_body(current_space, args)

    if client.dry_run:
        return {"dry_run": True, "action": "update_space", "space_id": space_id, "body": body}

    return client.put_v2(f"/space/{space_id}", data=body)


def cmd_spaces_statuses(client, args):
    """List valid statuses for a space."""
    space_id = resolve_space_id(args.space)
    resp = client.get_v2(f"/space/{space_id}")
    statuses = resp.get("statuses", [])
    return {
        "space": args.space,
        "statuses": [
            {
                "status": s.get("status"),
                "type": s.get("type"),
                "color": s.get("color"),
                "orderindex": s.get("orderindex"),
            }
            for s in statuses
        ],
        "count": len(statuses),
    }


def cmd_spaces_privacy(client, args):
    """Set a space private or public via the v3 ACLs endpoint."""
    space_id = resolve_space_id(args.space)
    return handle_privacy_request(
        client,
        args,
        object_type="space",
        object_id=space_id,
        path_segment="space",
    )


def cmd_spaces_delete(client, args):
    """Delete a space by configured alias or raw ID."""
    space_id = resolve_space_id(args.space)

    if client.dry_run:
        return {"dry_run": True, "action": "delete_space", "space_id": space_id}

    client.delete_v2(f"/space/{space_id}")
    return {"status": "ok", "action": "deleted", "space_id": space_id}

COMMAND_MANIFEST = {
    "group": "spaces",
    "register_parser": register_parser,
    "handlers": {
        "list": cmd_spaces_list,
        "get": cmd_spaces_get,
        "create": cmd_spaces_create,
        "update": cmd_spaces_update,
        "delete": cmd_spaces_delete,
        "statuses": cmd_spaces_statuses,
        "privacy": cmd_spaces_privacy,
    },
}
