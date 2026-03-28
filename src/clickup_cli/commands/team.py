"""Team command handlers — whoami, members."""

from ..config import WORKSPACE_ID


def _get_workspace(client):
    """Fetch teams and find the configured workspace."""
    resp = client.get_v2("/team")
    teams = resp.get("teams", [])
    for team in teams:
        if str(team.get("id")) == WORKSPACE_ID:
            return team
    # Shouldn't happen, but return first team if workspace ID doesn't match
    if teams:
        return teams[0]
    return resp


def _format_member(m):
    """Extract user fields from a member object."""
    u = m.get("user", {})
    return {
        "id": u.get("id"),
        "username": u.get("username"),
        "email": u.get("email"),
        "role": u.get("role_key"),
        "initials": u.get("initials"),
    }


def cmd_team_whoami(client, args):
    """Show authenticated user and workspace info."""
    team = _get_workspace(client)
    members = team.get("members", [])
    return {
        "workspace": {
            "id": team.get("id"),
            "name": team.get("name"),
            "color": team.get("color"),
        },
        "members": [_format_member(m) for m in members],
        "member_count": len(members),
    }


def cmd_team_members(client, args):
    """List workspace members."""
    team = _get_workspace(client)
    members = team.get("members", [])
    return {
        "members": [_format_member(m) for m in members],
        "count": len(members),
    }
