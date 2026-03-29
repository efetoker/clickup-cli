"""Tests for config.py — load_config, fallback chain, auto-detect, lazy attrs."""

import json
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from clickup_cli.config import (
    _auto_detect_workspace,
    _find_config_path,
    _load_from_env,
    _load_from_file,
    _reset,
    _save_field_to_config,
    load_config,
)


class LoadConfigCacheTests(unittest.TestCase):
    """Tests for config caching behavior."""

    def setUp(self):
        _reset()

    def tearDown(self):
        _reset()

    def test_cache_hit_returns_same_object(self):
        config1 = load_config()
        config2 = load_config()
        self.assertIs(config1, config2)

    def test_reset_clears_cache(self):
        load_config()
        _reset()
        from clickup_cli import config as cfg
        self.assertIsNone(cfg._config_cache)


class LoadFromEnvTests(unittest.TestCase):
    """Tests for _load_from_env()."""

    def test_no_token_returns_none(self):
        with patch.dict(os.environ, {}, clear=True):
            # Remove CLICKUP_API_TOKEN if set
            os.environ.pop("CLICKUP_API_TOKEN", None)
            os.environ.pop("CLICKUP_CONFIG_PATH", None)
            result = _load_from_env()
        self.assertIsNone(result)

    def test_token_with_workspace_id(self):
        env = {
            "CLICKUP_API_TOKEN": "pk_test",
            "CLICKUP_WORKSPACE_ID": "12345",
        }
        with patch.dict(os.environ, env):
            result = _load_from_env()
        self.assertEqual(result["api_token"], "pk_test")
        self.assertEqual(result["workspace_id"], "12345")
        self.assertEqual(result["spaces"], {})

    def test_token_without_workspace_triggers_autodetect(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.ok = True
        mock_resp.json.return_value = {"teams": [{"id": "999", "name": "Auto"}]}

        with patch.dict(os.environ, {"CLICKUP_API_TOKEN": "pk_test"}):
            os.environ.pop("CLICKUP_WORKSPACE_ID", None)
            with patch("requests.get", return_value=mock_resp):
                result = _load_from_env()
        self.assertEqual(result["workspace_id"], "999")

    def test_user_id_from_env(self):
        env = {
            "CLICKUP_API_TOKEN": "pk_test",
            "CLICKUP_WORKSPACE_ID": "12345",
            "CLICKUP_USER_ID": "777",
        }
        with patch.dict(os.environ, env):
            result = _load_from_env()
        self.assertEqual(result["user_id"], "777")


class LoadFromFileTests(unittest.TestCase):
    """Tests for _load_from_file()."""

    def _write_config(self, data):
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        json.dump(data, f)
        f.close()
        return f.name

    def test_valid_config_loads(self):
        path = self._write_config({
            "api_token": "pk_test",
            "workspace_id": "12345",
        })
        try:
            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop("CLICKUP_API_TOKEN", None)
                result = _load_from_file(path)
            self.assertEqual(result["api_token"], "pk_test")
            self.assertEqual(result["workspace_id"], "12345")
        finally:
            os.unlink(path)

    def test_invalid_json_exits(self):
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        f.write("not valid json {{{")
        f.close()
        try:
            with self.assertRaises(SystemExit):
                _load_from_file(f.name)
        finally:
            os.unlink(f.name)

    def test_missing_token_exits(self):
        path = self._write_config({"workspace_id": "12345"})
        try:
            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop("CLICKUP_API_TOKEN", None)
                with self.assertRaises(SystemExit):
                    _load_from_file(path)
        finally:
            os.unlink(path)

    def test_env_token_overrides_file_token(self):
        path = self._write_config({
            "api_token": "pk_file",
            "workspace_id": "12345",
        })
        try:
            with patch.dict(os.environ, {"CLICKUP_API_TOKEN": "pk_env"}):
                result = _load_from_file(path)
            self.assertEqual(result["api_token"], "pk_env")
        finally:
            os.unlink(path)

    def test_missing_workspace_triggers_autodetect(self):
        path = self._write_config({"api_token": "pk_test"})
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.ok = True
        mock_resp.json.return_value = {"teams": [{"id": "999", "name": "WS"}]}

        try:
            with patch("requests.get", return_value=mock_resp):
                result = _load_from_file(path)
            self.assertEqual(result["workspace_id"], "999")
        finally:
            os.unlink(path)


class FindConfigPathTests(unittest.TestCase):
    """Tests for _find_config_path() fallback chain."""

    def test_env_path_found(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            tmp = f.name
        try:
            with patch.dict(os.environ, {"CLICKUP_CONFIG_PATH": tmp}):
                result = _find_config_path()
            self.assertEqual(result, tmp)
        finally:
            os.unlink(tmp)

    def test_env_path_missing_file_exits(self):
        with patch.dict(os.environ, {"CLICKUP_CONFIG_PATH": "/nonexistent/config.json"}):
            with self.assertRaises(SystemExit):
                _find_config_path()

    def test_no_env_no_xdg_no_cwd_returns_none(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CLICKUP_CONFIG_PATH", None)
            with patch("os.path.exists", return_value=False):
                result = _find_config_path()
        self.assertIsNone(result)

    def test_xdg_path_found(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CLICKUP_CONFIG_PATH", None)

            def exists_side(path):
                return "/.config/clickup-cli/config.json" in path

            with patch("os.path.exists", side_effect=exists_side):
                result = _find_config_path()
            self.assertIn("config.json", result)


class NoConfigErrorTests(unittest.TestCase):
    """Tests for load_config when no config is available anywhere."""

    def setUp(self):
        _reset()

    def tearDown(self):
        _reset()

    def test_no_config_found_exits(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CLICKUP_CONFIG_PATH", None)
            os.environ.pop("CLICKUP_API_TOKEN", None)
            with patch("clickup_cli.config._find_config_path", return_value=None):
                with self.assertRaises(SystemExit):
                    load_config()


class AutoDetectWorkspaceTests(unittest.TestCase):
    """Tests for _auto_detect_workspace()."""

    def test_connection_error_exits(self):
        import requests as req
        with patch("requests.get", side_effect=req.ConnectionError("offline")):
            with self.assertRaises(SystemExit):
                _auto_detect_workspace("pk_test")

    def test_401_exits(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.ok = False
        with patch("requests.get", return_value=mock_resp):
            with self.assertRaises(SystemExit):
                _auto_detect_workspace("pk_test")

    def test_non_ok_exits(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.ok = False
        mock_resp.text = "Internal Server Error"
        with patch("requests.get", return_value=mock_resp):
            with self.assertRaises(SystemExit):
                _auto_detect_workspace("pk_test")

    def test_no_teams_exits(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.ok = True
        mock_resp.json.return_value = {"teams": []}
        with patch("requests.get", return_value=mock_resp):
            with self.assertRaises(SystemExit):
                _auto_detect_workspace("pk_test")

    def test_single_team_returns_id(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.ok = True
        mock_resp.json.return_value = {"teams": [{"id": 12345, "name": "My WS"}]}
        with patch("requests.get", return_value=mock_resp):
            result = _auto_detect_workspace("pk_test")
        self.assertEqual(result, "12345")

    def test_multiple_teams_exits(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.ok = True
        mock_resp.json.return_value = {
            "teams": [
                {"id": 111, "name": "WS1"},
                {"id": 222, "name": "WS2"},
            ]
        }
        with patch("requests.get", return_value=mock_resp):
            with self.assertRaises(SystemExit):
                _auto_detect_workspace("pk_test")


class SaveFieldToConfigTests(unittest.TestCase):
    """Tests for _save_field_to_config()."""

    def test_saves_field_to_existing_config(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"api_token": "pk_test"}, f)
            tmp = f.name
        try:
            _save_field_to_config(tmp, "workspace_id", "99999")
            with open(tmp) as f:
                saved = json.load(f)
            self.assertEqual(saved["workspace_id"], "99999")
            self.assertEqual(saved["api_token"], "pk_test")
        finally:
            os.unlink(tmp)

    def test_bad_path_does_not_crash(self):
        # Non-critical — should silently fail
        _save_field_to_config("/nonexistent/path/config.json", "key", "val")


class LazyAttrTests(unittest.TestCase):
    """Tests for module-level lazy attribute access (__getattr__)."""

    def test_workspace_id(self):
        from clickup_cli import config
        self.assertEqual(config.WORKSPACE_ID, "test_workspace")

    def test_user_id(self):
        from clickup_cli import config
        self.assertEqual(config.USER_ID, "12345")

    def test_spaces(self):
        from clickup_cli import config
        self.assertIn("testspace", config.SPACES)
        self.assertEqual(config.SPACES["testspace"]["space_id"], "111")

    def test_default_tags(self):
        from clickup_cli import config
        self.assertEqual(config.DEFAULT_TAGS, [])

    def test_draft_tag(self):
        from clickup_cli import config
        self.assertEqual(config.DRAFT_TAG, "draft")

    def test_good_as_is_tag(self):
        from clickup_cli import config
        self.assertEqual(config.GOOD_AS_IS_TAG, "good as is")

    def test_default_priority(self):
        from clickup_cli import config
        self.assertEqual(config.DEFAULT_PRIORITY, 4)

    def test_unknown_attr_raises(self):
        from clickup_cli import config
        with self.assertRaises(AttributeError):
            _ = config.NONEXISTENT_ATTR


if __name__ == "__main__":
    unittest.main()
