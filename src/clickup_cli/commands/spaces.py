"""Space command handlers — list, get, statuses."""

from ..config import WORKSPACE_ID
from ..helpers import resolve_space_id, add_id_argument


def register_parser(subparsers, F):
    """Register all spaces subcommands on the given subparsers object."""
    spaces_parser = subparsers.add_parser(
        "spaces",
        formatter_class=F,
        help="List spaces, view details, and discover statuses",
        description="""\
Inspect workspace spaces — list all spaces, view space details, and
discover valid statuses per space.

Subcommands:
  list      — list all spaces in the workspace
  get       — fetch full details of a specific space
  statuses  — list valid statuses for a space

All commands are read-only. Configured space names and raw ClickUp
space IDs are both accepted.""",
        epilog="""\
examples:
  clickup spaces list
  clickup spaces get <space>
  clickup spaces statuses <space>

notes:
  These commands hit the API directly — no caching.
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


def cmd_spaces_list(client, args):
    """List all spaces in the workspace."""
    resp = client.get_v2(f"/team/{WORKSPACE_ID}/space")
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
