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
    resolve_id_args,
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


class ParserComprehensiveTests(unittest.TestCase):
    """Parser tests for every command group — safety net for build_parser() refactor."""

    def setUp(self):
        self.parser = cli.build_parser()

    def _parse(self, argv):
        return self.parser.parse_args(cli.normalize_cli_argv(argv))

    # --- comments ---

    def test_comments_list(self):
        args = self._parse(["comments", "list", "task1"])
        self.assertEqual(args.group, "comments")
        self.assertEqual(args.command, "list")
        self.assertEqual(args.task_id, "task1")

    def test_comments_add(self):
        args = self._parse(["comments", "add", "task1", "--text", "hello"])
        self.assertEqual(args.command, "add")
        self.assertEqual(args.text, "hello")

    def test_comments_update(self):
        args = self._parse(["comments", "update", "c1", "--text", "fixed"])
        self.assertEqual(args.command, "update")
        self.assertEqual(args.comment_id, "c1")

    def test_comments_update_resolve(self):
        args = self._parse(["comments", "update", "c1", "--resolve"])
        self.assertTrue(args.resolved)

    def test_comments_update_unresolve(self):
        args = self._parse(["comments", "update", "c1", "--unresolve"])
        self.assertFalse(args.resolved)

    def test_comments_delete(self):
        args = self._parse(["comments", "delete", "c1"])
        self.assertEqual(args.command, "delete")
        self.assertEqual(args.comment_id, "c1")

    def test_comments_thread(self):
        args = self._parse(["comments", "thread", "c1"])
        self.assertEqual(args.command, "thread")
        self.assertEqual(args.comment_id, "c1")

    def test_comments_reply(self):
        args = self._parse(["comments", "reply", "c1", "--text", "ok"])
        self.assertEqual(args.command, "reply")
        self.assertEqual(args.text, "ok")

    # --- docs ---

    def test_docs_list(self):
        args = self._parse(["docs", "list"])
        self.assertEqual(args.group, "docs")
        self.assertEqual(args.command, "list")

    def test_docs_list_with_space(self):
        args = self._parse(["docs", "list", "--space", "personal"])
        self.assertEqual(args.space, "personal")

    def test_docs_get(self):
        args = self._parse(["docs", "get", "doc_abc"])
        self.assertEqual(args.command, "get")
        self.assertEqual(args.doc_id, "doc_abc")

    def test_docs_create(self):
        args = self._parse(["docs", "create", "--space", "personal", "--name", "My doc"])
        self.assertEqual(args.command, "create")
        self.assertEqual(args.name, "My doc")

    def test_docs_pages(self):
        args = self._parse(["docs", "pages", "doc_abc"])
        self.assertEqual(args.command, "pages")
        self.assertEqual(args.doc_id, "doc_abc")

    def test_docs_get_page(self):
        args = self._parse(["docs", "get-page", "doc_abc", "page_xyz"])
        self.assertEqual(args.command, "get-page")
        self.assertEqual(args.page_id, "page_xyz")

    def test_docs_get_page_format(self):
        args = self._parse(["docs", "get-page", "doc_abc", "page_xyz", "--format", "plain"])
        self.assertEqual(args.format, "plain")

    def test_docs_edit_page(self):
        args = self._parse(["docs", "edit-page", "doc_abc", "page_xyz", "--content", "hi"])
        self.assertEqual(args.command, "edit-page")
        self.assertEqual(args.content, "hi")

    def test_docs_edit_page_append(self):
        args = self._parse(["docs", "edit-page", "doc_abc", "page_xyz", "--content", "hi", "--append"])
        self.assertTrue(args.append)

    def test_docs_create_page(self):
        args = self._parse(["docs", "create-page", "doc_abc", "--name", "Notes"])
        self.assertEqual(args.command, "create-page")
        self.assertEqual(args.name, "Notes")

    # --- spaces ---

    def test_spaces_list(self):
        args = self._parse(["spaces", "list"])
        self.assertEqual(args.group, "spaces")
        self.assertEqual(args.command, "list")

    def test_spaces_get(self):
        args = self._parse(["spaces", "get", "myspace"])
        self.assertEqual(args.command, "get")
        self.assertEqual(args.space, "myspace")

    def test_spaces_statuses(self):
        args = self._parse(["spaces", "statuses", "myspace"])
        self.assertEqual(args.command, "statuses")
        self.assertEqual(args.space, "myspace")

    # --- folders ---

    def test_folders_list(self):
        args = self._parse(["folders", "list", "--space", "personal"])
        self.assertEqual(args.group, "folders")
        self.assertEqual(args.command, "list")

    def test_folders_get(self):
        args = self._parse(["folders", "get", "f123"])
        self.assertEqual(args.command, "get")
        self.assertEqual(args.folder_id, "f123")

    def test_folders_create(self):
        args = self._parse(["folders", "create", "--space", "personal", "--name", "Sprint 1"])
        self.assertEqual(args.command, "create")
        self.assertEqual(args.name, "Sprint 1")

    def test_folders_update(self):
        args = self._parse(["folders", "update", "f123", "--name", "Renamed"])
        self.assertEqual(args.command, "update")
        self.assertEqual(args.name, "Renamed")

    def test_folders_delete(self):
        args = self._parse(["folders", "delete", "f123"])
        self.assertEqual(args.command, "delete")
        self.assertEqual(args.folder_id, "f123")

    # --- team ---

    def test_team_whoami(self):
        args = self._parse(["team", "whoami"])
        self.assertEqual(args.group, "team")
        self.assertEqual(args.command, "whoami")

    def test_team_members(self):
        args = self._parse(["team", "members"])
        self.assertEqual(args.command, "members")

    # --- tags ---

    def test_tags_list(self):
        args = self._parse(["tags", "list", "--space", "personal"])
        self.assertEqual(args.group, "tags")
        self.assertEqual(args.command, "list")

    def test_tags_add(self):
        args = self._parse(["tags", "add", "task1", "--tag", "urgent"])
        self.assertEqual(args.command, "add")
        self.assertEqual(args.tag, "urgent")

    def test_tags_remove(self):
        args = self._parse(["tags", "remove", "task1", "--tag", "draft"])
        self.assertEqual(args.command, "remove")
        self.assertEqual(args.tag, "draft")

    # --- tasks (additional to existing) ---

    def test_tasks_list(self):
        args = self._parse(["tasks", "list", "--space", "jump"])
        self.assertEqual(args.group, "tasks")
        self.assertEqual(args.command, "list")

    def test_tasks_get(self):
        args = self._parse(["tasks", "get", "abc123"])
        self.assertEqual(args.command, "get")
        self.assertEqual(args.task_id, "abc123")

    def test_tasks_get_no_comments(self):
        args = self._parse(["tasks", "get", "abc123", "--no-comments"])
        self.assertTrue(args.no_comments)

    def test_tasks_create(self):
        args = self._parse(["tasks", "create", "--space", "jump", "--name", "Bug"])
        self.assertEqual(args.command, "create")
        self.assertEqual(args.name, "Bug")

    def test_tasks_update(self):
        args = self._parse(["tasks", "update", "abc123", "--status", "done"])
        self.assertEqual(args.command, "update")
        self.assertEqual(args.status, "done")

    def test_tasks_delete(self):
        args = self._parse(["tasks", "delete", "abc123"])
        self.assertEqual(args.command, "delete")

    def test_tasks_move(self):
        args = self._parse(["tasks", "move", "abc123", "--to", "personal"])
        self.assertEqual(args.command, "move")
        self.assertEqual(args.to_list, "personal")

    def test_tasks_merge(self):
        args = self._parse(["tasks", "merge", "abc123", "--sources", "d,e"])
        self.assertEqual(args.command, "merge")
        self.assertEqual(args.source_ids, "d,e")

    def test_tasks_search(self):
        args = self._parse(["tasks", "search", "bug", "--space", "jump", "--full"])
        self.assertEqual(args.command, "search")
        self.assertTrue(args.full)


class FilterTaskFieldsTests(unittest.TestCase):
    """Tests for filter_task_fields — safety net for DRY extraction."""

    def test_filter_extracts_status_name(self):
        from clickup_cli.helpers import filter_task_fields
        task = {"status": {"status": "in progress", "type": "custom"}}
        result = filter_task_fields(task, ["status"])
        self.assertEqual(result["status"], "in progress")

    def test_filter_extracts_priority_name(self):
        from clickup_cli.helpers import filter_task_fields
        task = {"priority": {"priority": "high", "orderindex": 2}}
        result = filter_task_fields(task, ["priority"])
        self.assertEqual(result["priority"], "high")

    def test_filter_priority_none(self):
        from clickup_cli.helpers import filter_task_fields
        task = {"priority": None}
        result = filter_task_fields(task, ["priority"])
        self.assertIsNone(result["priority"])

    def test_filter_priority_falls_back_to_orderindex(self):
        from clickup_cli.helpers import filter_task_fields
        task = {"priority": {"priority": None, "orderindex": 1}}
        result = filter_task_fields(task, ["priority"])
        self.assertEqual(result["priority"], "urgent")

    def test_filter_plain_fields(self):
        from clickup_cli.helpers import filter_task_fields
        task = {"id": "t1", "name": "Do stuff", "url": "https://x"}
        result = filter_task_fields(task, ["id", "name", "url"])
        self.assertEqual(result, {"id": "t1", "name": "Do stuff", "url": "https://x"})

    def test_filter_fields_via_format_tasks(self):
        tasks = [
            {
                "id": "t1",
                "name": "Task 1",
                "status": {"status": "open"},
                "priority": {"priority": "low", "orderindex": 4},
                "url": "https://x",
                "extra": "ignored",
            }
        ]
        result = format_tasks(tasks, fields=["id", "status", "priority"])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], {"id": "t1", "status": "open", "priority": "low"})
        self.assertNotIn("extra", result[0])


class TasksListPaginationTests(unittest.TestCase):
    """Tests for cmd_tasks_list pagination — safety net for pagination refactor."""

    def test_single_page(self):
        from clickup_cli.commands.tasks import cmd_tasks_list
        client = FakeClient(
            task_pages=[
                {
                    "tasks": [
                        {"id": "t1", "name": "A", "status": {"status": "open"}, "priority": None, "url": "u1"},
                    ],
                    "last_page": True,
                }
            ]
        )
        args = Namespace(
            space="jump", list_id=None, include_closed=False, status=None,
            subtasks=False, fields=None, full=False,
        )
        result = cmd_tasks_list(client, args)
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["tasks"][0]["id"], "t1")

    def test_multi_page(self):
        from clickup_cli.commands.tasks import cmd_tasks_list
        client = FakeClient(
            task_pages=[
                {
                    "tasks": [
                        {"id": "t1", "name": "A", "status": {"status": "open"}, "priority": None, "url": "u1"},
                        {"id": "t2", "name": "B", "status": {"status": "open"}, "priority": None, "url": "u2"},
                    ],
                    "last_page": False,
                },
                {
                    "tasks": [
                        {"id": "t3", "name": "C", "status": {"status": "done"}, "priority": None, "url": "u3"},
                    ],
                    "last_page": True,
                },
            ]
        )
        args = Namespace(
            space="jump", list_id=None, include_closed=False, status=None,
            subtasks=False, fields=None, full=False,
        )
        result = cmd_tasks_list(client, args)
        self.assertEqual(result["count"], 3)
        ids = [t["id"] for t in result["tasks"]]
        self.assertEqual(ids, ["t1", "t2", "t3"])

    def test_full_flag_returns_raw(self):
        from clickup_cli.commands.tasks import cmd_tasks_list
        client = FakeClient(
            task_pages=[
                {
                    "tasks": [
                        {"id": "t1", "name": "A", "status": {"status": "open"}, "priority": None, "url": "u1", "extra": "data"},
                    ],
                    "last_page": True,
                }
            ]
        )
        args = Namespace(
            space="jump", list_id=None, include_closed=False, status=None,
            subtasks=False, fields=None, full=True,
        )
        result = cmd_tasks_list(client, args)
        self.assertIn("extra", result["tasks"][0])


class TaskSearchPaginationTests(unittest.TestCase):
    """Tests for multi-page search — safety net for pagination refactor."""

    def test_search_multi_page(self):
        client = FakeClient(
            task_pages=[
                {
                    "tasks": [
                        {"id": "t1", "name": "Bug A", "status": {"status": "open"}, "priority": None, "url": "u1"},
                    ],
                    "last_page": False,
                },
                {
                    "tasks": [
                        {"id": "t2", "name": "Bug B", "status": {"status": "open"}, "priority": None, "url": "u2"},
                    ],
                    "last_page": True,
                },
            ]
        )
        args = Namespace(
            query="Bug", include_closed=False, space=None,
            list_id=None, folder_id=None, name_prefix=None,
            fields=None, full=False,
        )
        result = cmd_tasks_search(client, args)
        self.assertEqual(result["count"], 2)

    def test_search_dry_run(self):
        client = FakeClient(dry_run=True)
        args = Namespace(
            query="test", include_closed=False, space=None,
            list_id=None, folder_id=None, name_prefix=None,
        )
        result = cmd_tasks_search(client, args)
        self.assertTrue(result["dry_run"])


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
        self.assertIn("1.2.0", result.stdout)


class ConfigFallbackTests(unittest.TestCase):
    """Tests for config resolution."""

    def test_config_reset_clears_cache(self):
        from clickup_cli.config import _reset
        _reset()
        from clickup_cli import config
        self.assertIsNone(config._config_cache)

    def test_config_auto_detects_workspace_when_missing(self):
        """When config has token but no workspace_id, auto-detect fills it in."""
        import json
        import tempfile
        from clickup_cli.config import _reset, load_config
        _reset()

        # Create temp config with only api_token, no workspace_id
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump({"api_token": "pk_test"}, f)
            tmp_path = f.name

        try:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.ok = True
            mock_resp.json.return_value = {
                "teams": [{"id": "12345", "name": "Test Workspace"}]
            }

            with patch.dict(os.environ, {"CLICKUP_CONFIG_PATH": tmp_path}):
                with patch("requests.get", return_value=mock_resp):
                    config = load_config()

            self.assertEqual(config["workspace_id"], "12345")
        finally:
            os.unlink(tmp_path)
            _reset()


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


class FlagAliasTests(unittest.TestCase):
    """Tests for positional-or-flag argument aliases."""

    def setUp(self):
        self.parser = cli.build_parser()

    def _parse(self, argv):
        args = self.parser.parse_args(cli.normalize_cli_argv(argv))
        resolve_id_args(args)
        return args

    # -- flag form works --

    def test_tasks_get_flag_form(self):
        args = self._parse(["tasks", "get", "--task-id", "abc123"])
        self.assertEqual(args.task_id, "abc123")

    def test_tasks_search_query_flag(self):
        args = self._parse(["tasks", "search", "--query", "login bug"])
        self.assertEqual(args.query, "login bug")

    def test_comments_add_task_id_flag(self):
        args = self._parse(["comments", "add", "--task-id", "xyz", "--text", "hi"])
        self.assertEqual(args.task_id, "xyz")

    def test_comments_update_comment_id_flag(self):
        args = self._parse(["comments", "update", "--comment-id", "c1", "--text", "fix"])
        self.assertEqual(args.comment_id, "c1")

    def test_docs_get_page_both_flags(self):
        args = self._parse(["docs", "get-page", "--doc-id", "d1", "--page-id", "p1"])
        self.assertEqual(args.doc_id, "d1")
        self.assertEqual(args.page_id, "p1")

    def test_folders_get_flag_form(self):
        args = self._parse(["folders", "get", "--folder-id", "f123"])
        self.assertEqual(args.folder_id, "f123")

    def test_lists_get_flag_form(self):
        args = self._parse(["lists", "get", "--list-id", "l456"])
        self.assertEqual(args.list_id, "l456")

    def test_spaces_get_flag_form(self):
        args = self._parse(["spaces", "get", "--space", "personal"])
        self.assertEqual(args.space, "personal")

    def test_tags_add_flag_form(self):
        args = self._parse(["tags", "add", "--task-id", "t1", "--tag", "urgent"])
        self.assertEqual(args.task_id, "t1")

    # -- positional still works (regression) --

    def test_tasks_get_positional_still_works(self):
        args = self._parse(["tasks", "get", "abc123"])
        self.assertEqual(args.task_id, "abc123")

    def test_tasks_search_positional_still_works(self):
        args = self._parse(["tasks", "search", "bug", "--space", "jump"])
        self.assertEqual(args.query, "bug")

    # -- both provided errors --

    def test_tasks_get_both_forms_errors(self):
        with self.assertRaises(SystemExit):
            self._parse(["tasks", "get", "abc", "--task-id", "def"])

    # -- neither provided errors --

    def test_tasks_get_missing_errors(self):
        with self.assertRaises(SystemExit):
            self._parse(["tasks", "get"])

    # -- _flag attrs are cleaned up --

    def test_flag_attrs_cleaned_after_resolve(self):
        args = self._parse(["tasks", "get", "--task-id", "abc123"])
        self.assertFalse(hasattr(args, "_task_id_flag"))


class SpaceInferenceTests(unittest.TestCase):
    """Tests for auto-inferring --space from --list via API lookup."""

    def test_tasks_create_infers_space_from_list(self):
        """When --list provided without --space, space is inferred via API."""
        client = FakeClient(dry_run=True)
        original_get = client.get_v2

        def mock_get(path, params=None, allow_dry_run=False):
            if path.startswith("/list/"):
                return {"space": {"id": "901810236409"}}
            return original_get(path, params, allow_dry_run)

        client.get_v2 = mock_get
        args = Namespace(
            space=None,
            list_id="901816702978",
            name="Test",
            desc=None,
            desc_file=None,
            good_as_is=False,
            priority=None,
            status=None,
            no_assign=False,
            skip_dedup=False,
        )
        result = cmd_tasks_create(client, args)
        self.assertTrue(result["dry_run"])
        self.assertIsNotNone(args.space)

    def test_tasks_create_errors_without_space_or_list(self):
        """When neither --space nor --list provided, errors with helpful message."""
        client = FakeClient(dry_run=True)
        args = Namespace(
            space=None,
            list_id=None,
            name="Test",
            desc=None,
            desc_file=None,
            good_as_is=False,
            priority=None,
            status=None,
            no_assign=False,
            skip_dedup=False,
        )
        with self.assertRaises(SystemExit):
            cmd_tasks_create(client, args)

    def test_tasks_create_space_still_works(self):
        """Explicit --space still works as before."""
        client = FakeClient(dry_run=True)
        args = Namespace(
            space="personal",
            list_id=None,
            name="Test",
            desc=None,
            desc_file=None,
            good_as_is=False,
            priority=None,
            status=None,
            no_assign=False,
            skip_dedup=False,
        )
        result = cmd_tasks_create(client, args)
        self.assertTrue(result["dry_run"])
        self.assertEqual(args.space, "personal")


if __name__ == "__main__":
    unittest.main()
