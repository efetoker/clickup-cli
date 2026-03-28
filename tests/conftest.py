"""Test configuration — sets up a test config file before any clickup_cli imports."""

import json
import os
import tempfile

# This must run at import time (before test modules import clickup_cli)
# to prevent config loading from failing during test collection.
_test_config = {
    "api_token": "pk_test_token",
    "workspace_id": "test_workspace",
    "user_id": "12345",
    "spaces": {
        "testspace": {"space_id": "111", "list_id": "222"},
        "personal": {"space_id": "333", "list_id": "444"},
        "jump": {"space_id": "555", "list_id": "666"},
    },
    "default_tags": [],
    "draft_tag": "draft",
    "good_as_is_tag": "good as is",
    "default_priority": 4,
}

_test_dir = tempfile.mkdtemp()
_test_config_path = os.path.join(_test_dir, "config.json")
with open(_test_config_path, "w") as f:
    json.dump(_test_config, f)

os.environ["CLICKUP_CONFIG_PATH"] = _test_config_path
