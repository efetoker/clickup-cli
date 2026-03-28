"""Space command handlers — list, get, statuses."""

from ..config import WORKSPACE_ID
from ..helpers import resolve_space_id


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
