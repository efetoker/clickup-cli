"""Space command handlers — list, get, statuses, privacy."""

from ..helpers import resolve_space_id, add_id_argument
from .privacy import handle_privacy_request, register_privacy_subcommand


def register_parser(subparsers, F):
    """Register all spaces subcommands on the given subparsers object."""
    spaces_parser = subparsers.add_parser(
        "spaces",
        formatter_class=F,
        help="List spaces, view details, and discover statuses",
        description="""\
Inspect workspace spaces — list all spaces, view space details, discover
valid statuses, and toggle space privacy.

Subcommands:
  list      — list all spaces in the workspace
  get       — fetch full details of a specific space
  statuses  — list valid statuses for a space
  privacy   — make a space private or public (mutating)

list / get / statuses are read-only. privacy is mutating and supports
--dry-run. Configured space names and raw ClickUp space IDs are both
accepted.""",
        epilog="""\
examples:
  clickup spaces list
  clickup spaces get <space>
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

COMMAND_MANIFEST = {
    "group": "spaces",
    "register_parser": register_parser,
    "handlers": {
        "list": cmd_spaces_list,
        "get": cmd_spaces_get,
        "statuses": cmd_spaces_statuses,
        "privacy": cmd_spaces_privacy,
    },
}
