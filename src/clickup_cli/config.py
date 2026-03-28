"""ClickUp CLI configuration — lazy-loaded from JSON file or environment variables.

Config resolution order:
1. CLICKUP_CONFIG_PATH env var → exact file path
2. ~/.config/clickup-cli/config.json → XDG-ish default
3. clickup-config.json in current working directory → project-local override
4. Environment variables only (CLICKUP_API_TOKEN + CLICKUP_WORKSPACE_ID)
"""

import json
import os
import sys

_config_cache = None


def _find_config_path():
    """Find config file using the fallback chain. Returns path or None."""
    # 1. Explicit env var
    env_path = os.environ.get("CLICKUP_CONFIG_PATH")
    if env_path:
        if os.path.exists(env_path):
            return env_path
        print(
            f"Error: CLICKUP_CONFIG_PATH points to a missing file: {env_path}",
            file=sys.stderr,
        )
        sys.exit(1)

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
            print(f"Error: Invalid JSON in {path}: {e}", file=sys.stderr)
            sys.exit(1)

    # Allow env var to override token from file
    env_token = os.environ.get("CLICKUP_API_TOKEN")
    if env_token:
        config["api_token"] = env_token

    # Validate required fields
    missing = []
    for field in ("api_token", "workspace_id"):
        if not config.get(field):
            missing.append(field)
    if missing:
        print(
            f"Error: Missing required fields in {path}: {', '.join(missing)}\n"
            "See clickup-config.example.json for the expected schema.",
            file=sys.stderr,
        )
        sys.exit(1)

    return config


def _load_from_env():
    """Build minimal config from environment variables only."""
    token = os.environ.get("CLICKUP_API_TOKEN")
    workspace_id = os.environ.get("CLICKUP_WORKSPACE_ID")

    if not token:
        return None

    if not workspace_id:
        print(
            "Error: CLICKUP_API_TOKEN is set but CLICKUP_WORKSPACE_ID is missing.\n"
            "Either set CLICKUP_WORKSPACE_ID or run: clickup init",
            file=sys.stderr,
        )
        sys.exit(1)

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

    print(
        "Error: No ClickUp configuration found.\n\n"
        "Set up with one of:\n"
        "  clickup init                          # interactive setup\n"
        "  clickup init --token pk_YOUR_TOKEN    # non-interactive setup\n\n"
        "Or configure manually:\n"
        "  1. Copy clickup-config.example.json to ~/.config/clickup-cli/config.json\n"
        "  2. Fill in your API token and workspace ID\n\n"
        "Or set environment variables:\n"
        "  export CLICKUP_API_TOKEN=pk_YOUR_TOKEN\n"
        "  export CLICKUP_WORKSPACE_ID=YOUR_WORKSPACE_ID",
        file=sys.stderr,
    )
    sys.exit(1)


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
    "DRAFT_TAG": lambda c: c.get("draft_tag", "draft"),
    "GOOD_AS_IS_TAG": lambda c: c.get("good_as_is_tag", "good as is"),
    "DEFAULT_PRIORITY": lambda c: c.get("default_priority", 4),
}


def __getattr__(name):
    if name in _ATTR_MAP:
        config = load_config()
        return _ATTR_MAP[name](config)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
