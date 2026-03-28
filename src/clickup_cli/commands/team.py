"""Team command handlers — whoami, members."""

from ..config import WORKSPACE_ID


def register_parser(subparsers, F):
    """Register all team subcommands on the given subparsers object."""
    team_parser = subparsers.add_parser(
        "team",
        formatter_class=F,
        help="Workspace and team member information",
        description="""\
Inspect workspace and team details — authenticated user info and member list.

Subcommands:
  whoami   — show workspace info and authenticated user context
  members  — list all members of the workspace

All commands are read-only.""",
        epilog="""\
examples:
  clickup team whoami
  clickup team members
  clickup --pretty team whoami""",
    )
    team_sub = team_parser.add_subparsers(dest="command", required=True)

    # team whoami
    team_sub.add_parser(
        "whoami",
        formatter_class=F,
        help="Show workspace info and member context",
        description="""\
Show the workspace name, ID, and all members visible to the authenticated
user. Use this as a quick sanity check to confirm which workspace and
identity the CLI is operating under.""",
        epilog="""\
returns:
  {"workspace": {"id": ..., "name": ...}, "members": [...], "member_count": N}

examples:
  clickup team whoami
  clickup --pretty team whoami""",
    )

    # team members
    team_sub.add_parser(
        "members",
        formatter_class=F,
        help="List all workspace members",
        description="""\
List all members of the workspace with their IDs, usernames, emails,
and roles. Use this to discover user IDs for task assignment or to
verify team membership.""",
        epilog="""\
returns:
  {"members": [...], "count": N}

  Each member has: id, username, email, role, initials.

examples:
  clickup team members
  clickup --pretty team members""",
    )


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
