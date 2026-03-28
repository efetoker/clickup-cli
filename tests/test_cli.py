import os
import subprocess
import sys
import time
import unittest
from argparse import Namespace
from unittest.mock import MagicMock, patch

from clickup_cli import cli
from clickup_cli.client import ClickUpClient
from clickup_cli.commands.comments import cmd_comments_add
from clickup_cli.commands.docs import cmd_docs_edit_page
from clickup_cli.commands.folders import cmd_folders_create
from clickup_cli.commands.tasks import (
    cmd_tasks_create,
    cmd_tasks_delete,
    cmd_tasks_search,
    cmd_tasks_update,
)
from clickup_cli.helpers import (
    compact_task,
    format_tasks,
    read_content,
    resolve_space_id,
)


class FakeClient:
    def __init__(self, dry_run=False, task_pages=None, page_content=""):
        self.dry_run = dry_run
        self.task_pages = task_pages or []
        self.page_content = page_content
        self.v2_calls = []
        self.v3_get_calls = []
        self.v3_put_calls = []

    def get_v2(self, path, params=None, allow_dry_run=False):
        self.v2_calls.append((path, params, allow_dry_run))
        page = int((params or {}).get("page", "0"))
        return self.task_pages[page]

    def get_v3(self, path, params=None, allow_dry_run=False):
        self.v3_get_calls.append((path, params, allow_dry_run))
        return {"id": "page-1", "content": self.page_content}

    def put_v3(self, path, data=None):
        self.v3_put_calls.append((path, data))
        return {"id": "page-1", **(data or {})}


class CliArgumentTests(unittest.TestCase):
    def test_normalize_cli_argv_moves_global_flags_to_front(self):
        argv = ["tasks", "search", "JMP", "--pretty", "--dry-run", "--space", "jump"]

        normalized = cli.normalize_cli_argv(argv)

        self.assertEqual(
            normalized,
            ["--pretty", "--dry-run", "tasks", "search", "JMP", "--space", "jump"],
        )

    def test_parser_accepts_pretty_after_subcommand_when_normalized(self):
        parser = cli.build_parser()

        args = parser.parse_args(
            cli.normalize_cli_argv(["tasks", "list", "--space", "jump", "--pretty"])
        )

        self.assertTrue(args.pretty)
        self.assertEqual(args.group, "tasks")
        self.assertEqual(args.command, "list")
        self.assertEqual(args.space, "jump")

    def test_normalize_cli_argv_deduplicates_repeated_global_flags(self):
        argv = ["tasks", "list", "--pretty", "--space", "jump", "--pretty", "--dry-run"]

        normalized = cli.normalize_cli_argv(argv)

        self.assertEqual(
            normalized,
            ["--pretty", "--dry-run", "tasks", "list", "--space", "jump"],
        )

    def test_parser_accepts_init_command(self):
        parser = cli.build_parser()
        args = parser.parse_args(["init"])
        self.assertEqual(args.group, "init")

    def test_parser_accepts_init_with_token(self):
        parser = cli.build_parser()
        args = parser.parse_args(["init", "--token", "pk_test123"])
        self.assertEqual(args.group, "init")
        self.assertEqual(args.token, "pk_test123")


class TaskSearchTests(unittest.TestCase):
    def test_tasks_search_name_prefix_filters_broad_matches(self):
        client = FakeClient(
            task_pages=[
                {
                    "tasks": [
                        {"name": "JMP-9: WOS-18 Perf work"},
                        {"name": "JMP-19: Another task"},
                        {"name": "prefix JMP-9 in middle"},
                    ],
                    "last_page": True,
                }
            ]
        )
        args = Namespace(
            query="JMP",
            include_closed=False,
            space=None,
            list_id=None,
            folder_id=None,
            name_prefix="JMP-9",
        )

        result = cmd_tasks_search(client, args)

        self.assertEqual(result["count"], 1)
        self.assertEqual(result["tasks"][0]["name"], "JMP-9: WOS-18 Perf work")


class DocsEditPageTests(unittest.TestCase):
    def test_docs_edit_page_append_combines_existing_and_new_content(self):
        client = FakeClient(page_content="# Existing")
        args = Namespace(
            doc_id="doc-1",
            page_id="page-1",
            content="## Added",
            content_file=None,
            name=None,
            append=True,
        )

        result = cmd_docs_edit_page(client, args)

        self.assertEqual(result["content"], "# Existing\n\n## Added")
        self.assertEqual(len(client.v3_get_calls), 1)
        self.assertEqual(len(client.v3_put_calls), 1)

    def test_docs_edit_page_append_dry_run_previews_final_body(self):
        client = FakeClient(dry_run=True, page_content="# Existing")
        args = Namespace(
            doc_id="doc-1",
            page_id="page-1",
            content="## Added",
            content_file=None,
            name=None,
            append=True,
        )

        result = cmd_docs_edit_page(client, args)

        self.assertTrue(result["dry_run"])
        self.assertEqual(result["action"], "edit_page")
        self.assertEqual(result["body"]["content"], "# Existing\n\n## Added")
        self.assertEqual(len(client.v3_get_calls), 1)
        self.assertEqual(len(client.v3_put_calls), 0)

    def test_docs_edit_page_append_requires_content(self):
        client = FakeClient()
        args = Namespace(
            doc_id="doc-1",
            page_id="page-1",
            content=None,
            content_file=None,
            name=None,
            append=True,
        )

        with self.assertRaises(SystemExit):
            cmd_docs_edit_page(client, args)


class ListsMutualExclusionTests(unittest.TestCase):
    def setUp(self):
        self.parser = cli.build_parser()

    def _parse(self, argv):
        return self.parser.parse_args(cli.normalize_cli_argv(argv))

    def test_lists_list_rejects_both_folder_and_space(self):
        with self.assertRaises(SystemExit) as ctx:
            self._parse(["lists", "list", "--folder", "123", "--space", "myspace"])
        self.assertEqual(ctx.exception.code, 2)

    def test_lists_create_rejects_both_folder_and_space(self):
        with self.assertRaises(SystemExit) as ctx:
            self._parse(
                [
                    "lists",
                    "create",
                    "--folder",
                    "123",
                    "--space",
                    "myspace",
                    "--name",
                    "test",
                ]
            )
        self.assertEqual(ctx.exception.code, 2)

    def test_lists_list_requires_folder_or_space(self):
        with self.assertRaises(SystemExit) as ctx:
            self._parse(["lists", "list"])
        self.assertEqual(ctx.exception.code, 2)

    def test_lists_list_accepts_folder_alone(self):
        args = self._parse(["lists", "list", "--folder", "123"])
        self.assertEqual(args.folder, "123")
        self.assertIsNone(args.space)

    def test_lists_list_accepts_space_alone(self):
        args = self._parse(["lists", "list", "--space", "myspace"])
        self.assertEqual(args.space, "myspace")
        self.assertIsNone(args.folder)

    def test_lists_create_accepts_folder_alone(self):
        args = self._parse(["lists", "create", "--folder", "123", "--name", "Tasks"])
        self.assertEqual(args.folder, "123")
        self.assertIsNone(args.space)

    def test_lists_create_accepts_space_alone(self):
        args = self._parse(["lists", "create", "--space", "myspace", "--name", "Backlog"])
        self.assertEqual(args.space, "myspace")
        self.assertIsNone(args.folder)


class ClientTests(unittest.TestCase):
    """Tests for ClickUpClient._request behavior."""

    def _make_client(self, **kwargs):
        return ClickUpClient("fake-token", **kwargs)

    def test_client_401_exits_with_auth_error(self):
        client = self._make_client()
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.ok = False
        mock_resp.text = "Unauthorized"
        client.session.request = MagicMock(return_value=mock_resp)

        with self.assertRaises(SystemExit) as ctx:
            client.get_v2("/test")
        self.assertEqual(ctx.exception.code, 1)

    def test_client_connection_error_exits(self):
        client = self._make_client()
        import requests as req

        client.session.request = MagicMock(side_effect=req.ConnectionError("offline"))

        with self.assertRaises(SystemExit) as ctx:
            client.get_v2("/test")
        self.assertEqual(ctx.exception.code, 1)

    def test_client_empty_body_returns_empty_dict(self):
        client = self._make_client()
        mock_resp = MagicMock()
        mock_resp.status_code = 204
        mock_resp.ok = True
        mock_resp.text = ""
        mock_resp.headers = {}
        client.session.request = MagicMock(return_value=mock_resp)

        result = client.delete_v2("/test")
        self.assertEqual(result, {})

    def test_client_dry_run_skips_request(self):
        client = self._make_client(dry_run=True)
        client.session.request = MagicMock()

        result = client.post_v2("/test", data={"name": "x"})

        client.session.request.assert_not_called()
        self.assertTrue(result["dry_run"])
        self.assertEqual(result["method"], "POST")

    @patch("time.sleep")
    def test_client_429_retries_once(self, mock_sleep):
        client = self._make_client()

        mock_429 = MagicMock()
        mock_429.status_code = 429
        mock_429.ok = False
        mock_429.headers = {"X-RateLimit-Reset": str(int(time.time()) + 1)}

        mock_200 = MagicMock()
        mock_200.status_code = 200
        mock_200.ok = True
        mock_200.text = '{"ok": true}'
        mock_200.json.return_value = {"ok": True}
        mock_200.headers = {}

        client.session.request = MagicMock(side_effect=[mock_429, mock_200])

        result = client.get_v2("/test")
        self.assertEqual(result, {"ok": True})
        self.assertEqual(client.session.request.call_count, 2)
        mock_sleep.assert_called_once()


class DryRunTests(unittest.TestCase):
    """Tests for dry-run behavior on mutating commands."""

    def _make_fake_client(self):
        fake = FakeClient(dry_run=True)
        return fake

    def test_tasks_create_dry_run(self):
        client = self._make_fake_client()
        args = Namespace(
            space="jump",
            name="Test task",
            desc="A description",
            desc_file=None,
            good_as_is=False,
            priority=None,
            status=None,
            no_assign=False,
            list_id=None,
        )

        result = cmd_tasks_create(client, args)

        self.assertTrue(result["dry_run"])
        self.assertEqual(result["space"], "jump")
        self.assertIn("name", result["body"])
        self.assertEqual(result["body"]["name"], "Test task")

    def test_tasks_delete_dry_run(self):
        client = self._make_fake_client()
        args = Namespace(task_id="abc123")

        result = cmd_tasks_delete(client, args)

        self.assertTrue(result["dry_run"])
        self.assertEqual(result["action"], "delete")
        self.assertEqual(result["task_id"], "abc123")

    def test_tasks_update_dry_run(self):
        """Update goes through client.put_v2 which respects dry_run at client level."""
        client = ClickUpClient("fake-token", dry_run=True)
        args = Namespace(
            task_id="abc123",
            name="Updated",
            status=None,
            desc=None,
            desc_file=None,
            priority=None,
        )

        result = cmd_tasks_update(client, args)

        self.assertTrue(result["dry_run"])
        self.assertEqual(result["method"], "PUT")

    def test_comments_add_dry_run(self):
        """Comments add goes through client.post_v2 which respects dry_run at client level."""
        client = ClickUpClient("fake-token", dry_run=True)
        args = Namespace(
            task_id="abc123",
            text="Hello world",
            file=None,
        )

        result = cmd_comments_add(client, args)

        self.assertTrue(result["dry_run"])
        self.assertEqual(result["method"], "POST")

    def test_folders_create_dry_run(self):
        client = self._make_fake_client()
        args = Namespace(space="jump", name="New Folder")

        result = cmd_folders_create(client, args)

        self.assertTrue(result["dry_run"])
        self.assertEqual(result["action"], "create_folder")
        self.assertIn("name", result["body"])


class HelperTests(unittest.TestCase):
    """Tests for helper functions."""

    def test_resolve_space_id_raw_id(self):
        self.assertEqual(resolve_space_id("99999"), "99999")

    def test_read_content_inline(self):
        self.assertEqual(read_content("hello", None), "hello")

    def test_read_content_both_errors(self):
        with self.assertRaises(SystemExit):
            read_content("a", "b")

    def test_compact_task_extracts_status(self):
        task = {
            "id": "t1",
            "name": "Do stuff",
            "status": {"status": "in progress", "type": "custom"},
            "priority": {"priority": "high", "orderindex": 2},
            "url": "https://example.com/t1",
        }
        result = compact_task(task)
        self.assertEqual(result["status"], "in progress")
        self.assertEqual(result["priority"], "high")
        self.assertEqual(result["id"], "t1")

    def test_format_tasks_default_compact(self):
        tasks = [
            {
                "id": "t1",
                "name": "Task 1",
                "status": {"status": "open"},
                "priority": None,
                "url": "https://example.com/t1",
                "extra_field": "ignored",
            }
        ]
        result = format_tasks(tasks, full=False)
        self.assertEqual(len(result), 1)
        self.assertNotIn("extra_field", result[0])
        self.assertEqual(result[0]["status"], "open")


class EntrypointTests(unittest.TestCase):
    """Tests for package entrypoint behavior."""

    def test_package_module_execution(self):
        result = subprocess.run(
            [sys.executable, "-m", "clickup_cli", "--help"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("ClickUp CLI", result.stdout)

    def test_version_flag(self):
        result = subprocess.run(
            [sys.executable, "-m", "clickup_cli", "--version"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("1.0.0", result.stdout)


class ConfigFallbackTests(unittest.TestCase):
    """Tests for config resolution."""

    def test_config_reset_clears_cache(self):
        from clickup_cli.config import _reset
        _reset()
        from clickup_cli import config
        self.assertIsNone(config._config_cache)

    def test_config_env_only_without_workspace_id_exits(self):
        from clickup_cli.config import _reset
        _reset()

        with patch.dict(os.environ, {"CLICKUP_API_TOKEN": "pk_test"}, clear=False):
            # Remove CLICKUP_WORKSPACE_ID if set
            env = os.environ.copy()
            env.pop("CLICKUP_WORKSPACE_ID", None)
            env.pop("CLICKUP_CONFIG_PATH", None)
            result = subprocess.run(
                [sys.executable, "-c",
                 "from clickup_cli.config import load_config; load_config()"],
                capture_output=True,
                text=True,
                env=env,
                cwd="/tmp",  # avoid picking up local config
            )
            self.assertNotEqual(result.returncode, 0)


class PreCreateDedupTests(unittest.TestCase):
    def _make_args(self, name="Test task", space="personal", skip_dedup=False):
        return Namespace(
            name=name,
            space=space,
            list_id=None,
            desc=None,
            desc_file=None,
            good_as_is=False,
            priority=None,
            status=None,
            no_assign=False,
            skip_dedup=skip_dedup,
        )

    def test_tasks_create_finds_duplicate(self):
        """When a task with the same name exists, return it instead of creating."""
        client = FakeClient(dry_run=False)
        original_get = client.get_v2
        def mock_get(path, params=None, allow_dry_run=False):
            if "/team/" in path and params and "search" in params:
                return {"tasks": [{"id": "abc123", "name": "Test task", "url": "https://..."}]}
            return original_get(path, params, allow_dry_run)
        client.get_v2 = mock_get

        args = self._make_args(name="Test task")
        result = cmd_tasks_create(client, args)
        self.assertEqual(result["duplicate_of"], "abc123")

    def test_tasks_create_skip_dedup_bypasses_search(self):
        """With --skip-dedup, no search is performed."""
        client = FakeClient(dry_run=False)
        search_called = []
        original_get = client.get_v2
        def mock_get(path, params=None, allow_dry_run=False):
            if "/team/" in path:
                search_called.append(True)
            return original_get(path, params, allow_dry_run)
        client.get_v2 = mock_get
        client.post_v2 = lambda path, data=None: {"id": "new123", "name": data["name"]}

        args = self._make_args(name="Test task", skip_dedup=True)
        result = cmd_tasks_create(client, args)
        self.assertEqual(len(search_called), 0)
        self.assertEqual(result["id"], "new123")

    def test_tasks_create_no_duplicate_proceeds(self):
        """When no duplicate found, create normally."""
        client = FakeClient(dry_run=False)
        original_get = client.get_v2
        def mock_get(path, params=None, allow_dry_run=False):
            if "/team/" in path and params and "search" in params:
                return {"tasks": []}
            return original_get(path, params, allow_dry_run)
        client.get_v2 = mock_get
        client.post_v2 = lambda path, data=None: {"id": "new456", "name": data["name"]}

        args = self._make_args(name="Unique task")
        result = cmd_tasks_create(client, args)
        self.assertEqual(result["id"], "new456")


if __name__ == "__main__":
    unittest.main()
