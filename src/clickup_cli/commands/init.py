"""Init command — interactive workspace setup."""

import json
import os
import sys

import requests


def cmd_init(args):
    """Set up ClickUp CLI configuration interactively or via --token."""
    token = getattr(args, "token", None)

    if not token:
        print("Enter your ClickUp API token (starts with pk_):")
        print("  Find it at: https://app.clickup.com/settings/apps")
        try:
            token = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nAborted.", file=sys.stderr)
            sys.exit(1)

    if not token:
        print("Error: API token is required.", file=sys.stderr)
        sys.exit(1)

    # Fetch workspaces
    print("Fetching workspaces...", file=sys.stderr)
    headers = {"Authorization": token, "Content-Type": "application/json"}

    try:
        resp = requests.get(
            "https://api.clickup.com/api/v2/team", headers=headers, timeout=15
        )
    except requests.ConnectionError:
        print("Error: Could not reach ClickUp API. Check your network.", file=sys.stderr)
        sys.exit(1)

    if resp.status_code == 401:
        print("Error: Invalid API token.", file=sys.stderr)
        sys.exit(1)

    if not resp.ok:
        print(f"Error: API returned {resp.status_code}: {resp.text}", file=sys.stderr)
        sys.exit(1)

    teams = resp.json().get("teams", [])
    if not teams:
        print("Error: No workspaces found for this token.", file=sys.stderr)
        sys.exit(1)

    # Select workspace
    if len(teams) == 1:
        team = teams[0]
        print(f"Found workspace: {team['name']} (ID: {team['id']})", file=sys.stderr)
    else:
        print(f"\nFound {len(teams)} workspaces:", file=sys.stderr)
        for i, t in enumerate(teams, 1):
            print(f"  {i}. {t['name']} (ID: {t['id']})", file=sys.stderr)
        try:
            choice = input(f"Select workspace [1-{len(teams)}]: ").strip()
            idx = int(choice) - 1
            if idx < 0 or idx >= len(teams):
                raise ValueError
            team = teams[idx]
        except (ValueError, EOFError, KeyboardInterrupt):
            print("\nAborted.", file=sys.stderr)
            sys.exit(1)

    workspace_id = str(team["id"])

    # Find authenticated user
    user_id = ""
    members = team.get("members", [])
    if len(members) == 1:
        u = members[0].get("user", {})
        user_id = str(u.get("id", ""))
        print(f"Found user: {u.get('username', 'unknown')} (ID: {user_id})", file=sys.stderr)
    elif members:
        print(f"\nFound {len(members)} members:", file=sys.stderr)
        for i, m in enumerate(members, 1):
            u = m.get("user", {})
            print(
                f"  {i}. {u.get('username', 'unknown')} — {u.get('email', '')} (ID: {u.get('id')})",
                file=sys.stderr,
            )
        try:
            choice = input(f"Which one is you? [1-{len(members)}] (Enter to skip): ").strip()
            if choice:
                idx = int(choice) - 1
                if 0 <= idx < len(members):
                    u = members[idx].get("user", {})
                    user_id = str(u.get("id", ""))
                else:
                    raise ValueError
        except (ValueError, EOFError, KeyboardInterrupt):
            print("Skipped — set user_id in config later if needed.", file=sys.stderr)

    # Fetch spaces
    print("Fetching spaces...", file=sys.stderr)
    try:
        resp = requests.get(
            f"https://api.clickup.com/api/v2/team/{workspace_id}/space",
            headers=headers,
            timeout=15,
        )
    except requests.ConnectionError:
        print("Error: Could not fetch spaces.", file=sys.stderr)
        sys.exit(1)

    spaces_raw = resp.json().get("spaces", [])

    # Build spaces config
    spaces = {}
    for s in spaces_raw:
        # Use lowercase name as key, sanitized for CLI use
        key = s["name"].lower().replace(" ", "-")
        lists_resp = requests.get(
            f"https://api.clickup.com/api/v2/space/{s['id']}/list",
            headers=headers,
            timeout=15,
        )
        lists = lists_resp.json().get("lists", [])
        default_list_id = lists[0]["id"] if lists else ""
        spaces[key] = {"space_id": str(s["id"]), "list_id": default_list_id}
        status = f" (default list: {default_list_id})" if default_list_id else " (no lists)"
        print(f"  {key}: {s['name']}{status}", file=sys.stderr)

    config = {
        "api_token": token,
        "workspace_id": workspace_id,
        "user_id": user_id,
        "spaces": spaces,
        "default_tags": [],
    }

    # Write config
    config_dir = os.path.expanduser("~/.config/clickup-cli")
    config_path = os.path.join(config_dir, "config.json")
    os.makedirs(config_dir, exist_ok=True)

    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"\nConfig saved to {config_path}", file=sys.stderr)
    print(f"Workspace: {team['name']} ({len(spaces)} spaces)", file=sys.stderr)
    print("\nTry it out:", file=sys.stderr)
    print("  clickup spaces list", file=sys.stderr)
    print("  clickup team whoami", file=sys.stderr)
