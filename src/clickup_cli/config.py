"""ClickUp CLI configuration — lazy-loaded from JSON file or environment variables.

Config resolution order:
1. CLICKUP_CONFIG_PATH env var → exact file path
2. ~/.config/clickup-cli/config.json → XDG-ish default
3. clickup-config.json in current working directory → project-local override
4. Environment variables only (CLICKUP_API_TOKEN + CLICKUP_WORKSPACE_ID)

workspace_id is auto-detected from the API when missing (single-workspace accounts).
"""

import json
import os
import sys

from .helpers import error

_config_cache = None


def _auto_detect_workspace(token):
    """Auto-detect workspace ID when only a token is available.

    Returns workspace_id string. Exits with error if detection fails.
    """
    import requests

    print("Auto-detecting workspace...", file=sys.stderr)
    headers = {"Authorization": token, "Content-Type": "application/json"}

    try:
        resp = requests.get(
            "https://api.clickup.com/api/v2/team", headers=headers, timeout=15
        )
    except requests.ConnectionError:
        error("Could not reach ClickUp API to auto-detect workspace")

    if resp.status_code == 401:
        error("Authentication failed — check your API token")

    if not resp.ok:
        error(f"API error {resp.status_code} while detecting workspace: {resp.text}")

    teams = resp.json().get("teams", [])

    if not teams:
        error("No workspaces found for this token")

    if len(teams) == 1:
        workspace_id = str(teams[0]["id"])
        print(
            f"Found workspace: {teams[0]['name']} (ID: {workspace_id})",
            file=sys.stderr,
        )
        return workspace_id

    # Multiple workspaces — can't auto-select
    lines = ["Multiple workspaces found — set workspace_id manually:"]
    for t in teams:
        lines.append(f"  {t['name']}: {t['id']}")
    lines.append("\nSet it in your config file or via: export CLICKUP_WORKSPACE_ID=<id>")
    error("\n".join(lines))


def _save_field_to_config(path, field, value):
    """Update a single field in an existing config file."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            config = json.load(f)
        config[field] = value
        with open(path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
            f.write("\n")
        print(f"Saved {field} to {path}", file=sys.stderr)
    except (OSError, json.JSONDecodeError):
        pass  # Non-critical — config works in memory even if save fails


def _find_config_path():
    """Find config file using the fallback chain. Returns path or None."""
    # 1. Explicit env var
    env_path = os.environ.get("CLICKUP_CONFIG_PATH")
    if env_path:
        if os.path.exists(env_path):
            return env_path
        error(f"CLICKUP_CONFIG_PATH points to a missing file: {env_path}")

    # 2. XDG-ish default
    xdg_path = os.path.expanduser("~/.config/clickup-cli/config.json")
    if os.path.exists(xdg_path):
        return xdg_path

    # 3. Current working directory
    cwd_path = os.path.join(os.getcwd(), "clickup-config.json")
    if os.path.exists(cwd_path):
        return cwd_path

    return None


def _load_from_file(path):
    """Load and validate config from a JSON file."""
    with open(path, "r", encoding="utf-8") as f:
        try:
            config = json.load(f)
        except json.JSONDecodeError as e:
            error(f"Invalid JSON in {path}: {e}")

    # Allow env var to override token from file
    env_token = os.environ.get("CLICKUP_API_TOKEN")
    if env_token:
        config["api_token"] = env_token

    if not config.get("api_token"):
        error(
            f"Missing required field in {path}: api_token\n"
            "See clickup-config.example.json for the expected schema."
        )

    # Auto-detect workspace_id if missing
    if not config.get("workspace_id"):
        config["workspace_id"] = _auto_detect_workspace(config["api_token"])
        _save_field_to_config(path, "workspace_id", config["workspace_id"])

    return config


def _load_from_env():
    """Build minimal config from environment variables only."""
    token = os.environ.get("CLICKUP_API_TOKEN")
    if not token:
        return None

    workspace_id = os.environ.get("CLICKUP_WORKSPACE_ID")
    if not workspace_id:
        workspace_id = _auto_detect_workspace(token)

    return {
        "api_token": token,
        "workspace_id": workspace_id,
        "user_id": os.environ.get("CLICKUP_USER_ID", ""),
        "spaces": {},
    }


def load_config():
    """Load config from file or environment. Caches after first call."""
    global _config_cache
    if _config_cache is not None:
        return _config_cache

    path = _find_config_path()

    if path:
        _config_cache = _load_from_file(path)
        return _config_cache

    env_config = _load_from_env()
    if env_config:
        _config_cache = env_config
        return _config_cache

    error(
        "No ClickUp configuration found.\n\n"
        "Set up with one of:\n"
        "  clickup init                          # interactive setup\n"
        "  clickup init --token pk_YOUR_TOKEN    # non-interactive setup\n\n"
        "Or configure manually:\n"
        "  1. Copy clickup-config.example.json to ~/.config/clickup-cli/config.json\n"
        "  2. Fill in your API token and workspace ID\n\n"
        "Or set environment variables:\n"
        "  export CLICKUP_API_TOKEN=pk_YOUR_TOKEN\n"
        "  export CLICKUP_WORKSPACE_ID=YOUR_WORKSPACE_ID"
    )


def _reset():
    """Reset cached config (for testing)."""
    global _config_cache
    _config_cache = None


# Lazy attribute access — config is loaded on first use, not at import time.
# This allows `clickup init` to run before any config file exists.
_ATTR_MAP = {
    "WORKSPACE_ID": lambda c: c["workspace_id"],
    "USER_ID": lambda c: c.get("user_id", ""),
    "SPACES": lambda c: c.get("spaces", {}),
    "DEFAULT_TAGS": lambda c: c.get("default_tags", []),
}


def __getattr__(name):
    if name in _ATTR_MAP:
        config = load_config()
        return _ATTR_MAP[name](config)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
