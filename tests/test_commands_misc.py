"""Handler tests for tags, team, init, and dispatch wiring."""

import unittest
from argparse import Namespace
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import requests

from clickup_cli.commands.docs import cmd_docs_create
from clickup_cli.commands.init import cmd_init
from clickup_cli.commands import tags as tags_commands
from clickup_cli.commands.tags import cmd_tags_add, cmd_tags_list, cmd_tags_remove
from clickup_cli.commands.team import cmd_team_members, cmd_team_whoami

from command_fakes import FlexClient

class TagsListTests(unittest.TestCase):

    def test_list_tags(self):
        client = FlexClient(responses={
            "/tag": {"tags": [{"name": "draft"}, {"name": "urgent"}]}
        })
        args = Namespace(space="testspace")
        result = cmd_tags_list(client, args)
        self.assertEqual(result["count"], 2)


class TagsAddTests(unittest.TestCase):

    def test_add_lowercases_tag(self):
        client = FlexClient()
        args = Namespace(task_id="t1", tag="URGENT")
        result = cmd_tags_add(client, args)
        self.assertEqual(result["tag"], "urgent")
        self.assertEqual(result["action"], "tag_added")

    def test_add_dry_run(self):
        client = FlexClient(dry_run=True)
        args = Namespace(task_id="t1", tag="draft")
        result = cmd_tags_add(client, args)
        self.assertTrue(result["dry_run"])
        self.assertEqual(result["tag"], "draft")


class TagsRemoveTests(unittest.TestCase):

    def test_remove_lowercases_tag(self):
        client = FlexClient()
        args = Namespace(task_id="t1", tag="Draft")
        result = cmd_tags_remove(client, args)
        self.assertEqual(result["tag"], "draft")
        self.assertEqual(result["action"], "tag_removed")

    def test_remove_dry_run(self):
        client = FlexClient(dry_run=True)
        args = Namespace(task_id="t1", tag="draft")
        result = cmd_tags_remove(client, args)
        self.assertTrue(result["dry_run"])


class TagsLifecycleTests(unittest.TestCase):

    def test_create_space_tag_dry_run(self):
        client = FlexClient(dry_run=True)
        args = Namespace(space="testspace", tag="Urgent", fg_color="#fff", bg_color="#f00")

        result = tags_commands.cmd_tags_create(client, args)

        self.assertEqual(result["action"], "create_space_tag")
        self.assertEqual(result["space_id"], "111")
        self.assertEqual(result["tag"], "urgent")
        self.assertEqual(
            result["body"],
            {"tag": {"name": "urgent", "tag_fg": "#fff", "tag_bg": "#f00"}},
        )
        self.assertEqual(client.calls, [])

    def test_create_space_tag_live_posts_body(self):
        client = FlexClient(responses={"/space/111/tag": {"tag": {"name": "urgent"}}})
        args = Namespace(space="testspace", tag="Urgent", fg_color=None, bg_color=None)

        result = tags_commands.cmd_tags_create(client, args)

        self.assertEqual(result, {"tag": {"name": "urgent"}})
        self.assertEqual(client.calls[0]["method"], "POST")
        self.assertEqual(client.calls[0]["path"], "/space/111/tag")
        self.assertEqual(client.calls[0]["data"], {"tag": {"name": "urgent"}})

    def test_delete_space_tag_dry_run_warns_blast_radius(self):
        client = FlexClient(dry_run=True)
        args = Namespace(space="testspace", tag="In Review")

        result = tags_commands.cmd_tags_delete(client, args)

        self.assertEqual(result["action"], "delete_space_tag")
        self.assertEqual(result["tag"], "in review")
        self.assertEqual(result["encoded_tag"], "in%20review")
        self.assertIn("all tasks in this Space", result["warning"])
        self.assertEqual(client.calls, [])

    def test_delete_space_tag_live_uses_encoded_path(self):
        client = FlexClient()
        args = Namespace(space="testspace", tag="In Review")

        result = tags_commands.cmd_tags_delete(client, args)

        self.assertEqual(result["action"], "space_tag_deleted")
        self.assertEqual(client.calls[0]["method"], "DELETE")
        self.assertEqual(client.calls[0]["path"], "/space/111/tag/in%20review")


class TagsUsageTests(unittest.TestCase):

    def test_usage_scans_space_tasks_with_bounded_default(self):
        client = FlexClient(
            responses={
                "/space/111/list": {"lists": [{"id": "list-1"}]},
                "/space/111/folder": {"folders": []},
                "/list/list-1/task": {
                    "tasks": [
                        {"id": "t1", "name": "Match", "url": "u1", "status": {"status": "open"}, "tags": [{"name": "urgent"}]},
                        {"id": "t2", "name": "Skip", "url": "u2", "status": {"status": "open"}, "tags": []},
                    ],
                    "last_page": True,
                },
            }
        )
        args = Namespace(
            space="testspace",
            tag="Urgent",
            include_closed=False,
            include_archived=False,
            subtasks=False,
            all_pages=False,
        )

        result = tags_commands.cmd_tags_usage(client, args)

        self.assertEqual(result["tag"], "urgent")
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["tasks"][0]["id"], "t1")
        self.assertEqual(result["lists_scanned"], 1)
        self.assertEqual(result["pages_fetched"], 1)
        self.assertTrue(result["results_complete"])

    def test_usage_exhaustive_flags_forward_to_task_scan(self):
        client = FlexClient(
            responses={
                "/space/111/list": {"lists": [{"id": "list-1"}]},
                "/space/111/folder": {"folders": []},
                "/list/list-1/task": {"tasks": [], "last_page": True},
            }
        )
        args = Namespace(
            space="testspace",
            tag="urgent",
            include_closed=True,
            include_archived=True,
            subtasks=True,
            all_pages=True,
        )

        tags_commands.cmd_tags_usage(client, args)

        task_calls = [call for call in client.calls if call["path"] == "/list/list-1/task"]
        self.assertEqual(
            [call["params"] for call in task_calls],
            [
                {
                    "archived": "false",
                    "include_closed": "true",
                    "subtasks": "true",
                    "page": "0",
                },
                {
                    "archived": "true",
                    "include_closed": "true",
                    "subtasks": "true",
                    "page": "0",
                },
            ],
        )

    def test_usage_include_archived_merges_active_and_archived_tasks(self):
        def _tasks(path, kwargs):
            archived = kwargs.get("params", {}).get("archived")
            if archived == "true":
                return {
                    "tasks": [
                        {"id": "archived", "name": "Archived", "url": "u2", "status": {"status": "open"}, "tags": [{"name": "urgent"}]}
                    ],
                    "last_page": True,
                }
            return {
                "tasks": [
                    {"id": "active", "name": "Active", "url": "u1", "status": {"status": "open"}, "tags": [{"name": "urgent"}]}
                ],
                "last_page": True,
            }

        client = FlexClient(
            responses={
                "/space/111/list": {"lists": [{"id": "list-1"}]},
                "/space/111/folder": {"folders": []},
                "/list/list-1/task": _tasks,
            }
        )
        args = Namespace(
            space="testspace",
            tag="urgent",
            include_closed=False,
            include_archived=True,
            subtasks=False,
            all_pages=False,
        )

        result = tags_commands.cmd_tags_usage(client, args)

        task_calls = [call for call in client.calls if call["path"] == "/list/list-1/task"]
        self.assertEqual({call["params"]["archived"] for call in task_calls}, {"false", "true"})
        self.assertEqual({task["id"] for task in result["tasks"]}, {"active", "archived"})
        self.assertEqual(result["count"], 2)


# ─── Team ─────────────────────────────────────────────────────────────────


class TeamWhoamiTests(unittest.TestCase):

    def test_whoami_matching_workspace(self):
        client = FlexClient(responses={
            "/team": {
                "teams": [
                    {
                        "id": "test_workspace",
                        "name": "Test WS",
                        "color": "#fff",
                        "members": [
                            {"user": {"id": 1, "username": "testuser", "email": "test@example.com",
                                      "role_key": "admin", "initials": "ET"}}
                        ],
                    }
                ]
            }
        })
        args = Namespace()
        result = cmd_team_whoami(client, args)
        self.assertEqual(result["workspace"]["id"], "test_workspace")
        self.assertEqual(result["member_count"], 1)
        self.assertEqual(result["members"][0]["username"], "testuser")

    def test_whoami_fallback_to_first_team(self):
        """When workspace_id doesn't match, falls back to first team."""
        client = FlexClient(responses={
            "/team": {
                "teams": [
                    {"id": "other_ws", "name": "Other", "members": []}
                ]
            }
        })
        args = Namespace()
        result = cmd_team_whoami(client, args)
        self.assertEqual(result["workspace"]["id"], "other_ws")

    def test_whoami_no_teams(self):
        client = FlexClient(responses={"/team": {"teams": []}})
        args = Namespace()
        result = cmd_team_whoami(client, args)
        # When no teams, _get_workspace returns the raw resp dict
        # which has "teams" key, and whoami wraps it
        self.assertEqual(result["member_count"], 0)

    def test_whoami_prefers_runtime_workspace_id(self):
        client = FlexClient(
            responses={
                "/team": {
                    "teams": [
                        {"id": "other_ws", "name": "Other", "members": []},
                        {"id": "runtime_ws", "name": "Runtime", "members": []},
                    ]
                }
            },
            runtime=SimpleNamespace(workspace_id="runtime_ws", user_id="", spaces={}),
        )

        result = cmd_team_whoami(client, Namespace())

        self.assertEqual(result["workspace"]["id"], "runtime_ws")


class TeamMembersTests(unittest.TestCase):

    def test_members_list(self):
        client = FlexClient(responses={
            "/team": {
                "teams": [
                    {
                        "id": "test_workspace",
                        "name": "WS",
                        "members": [
                            {"user": {"id": 1, "username": "alice", "email": "a@a.com",
                                      "role_key": "member", "initials": "A"}},
                            {"user": {"id": 2, "username": "bob", "email": "b@b.com",
                                      "role_key": "admin", "initials": "B"}},
                        ],
                    }
                ]
            }
        })
        args = Namespace()
        result = cmd_team_members(client, args)
        self.assertEqual(result["count"], 2)
        self.assertEqual(result["members"][0]["username"], "alice")

    def test_members_empty(self):
        client = FlexClient(responses={
            "/team": {"teams": [{"id": "test_workspace", "name": "WS", "members": []}]}
        })
        args = Namespace()
        result = cmd_team_members(client, args)
        self.assertEqual(result["count"], 0)


# ─── Tasks (additional coverage) ──────────────────────────────────────────


class DispatchTests(unittest.TestCase):

    def test_dispatch_known_handler(self):
        from clickup_cli.cli import dispatch
        client = FlexClient(responses={"/space": {"spaces": []}})
        args = Namespace(group="spaces", command="list")
        result = dispatch(client, args)
        self.assertIn("spaces", result)

    def test_dispatch_unknown_handler(self):
        from clickup_cli.cli import dispatch
        client = FlexClient()
        args = Namespace(group="fake", command="nope")
        with self.assertRaises(SystemExit):
            dispatch(client, args)


class DocsCreateContentTests(unittest.TestCase):
    """Tests for cmd_docs_create with initial content writing."""

    def test_create_with_content_writes_to_default_page(self):
        """When content is provided, it writes to the auto-created default page."""
        call_log = []

        def track_handler(method, path, **kwargs):
            call_log.append({"method": method, "path": path, **kwargs})
            if method == "POST_V3" and "/docs" in path and "/pages" not in path:
                return {"id": "doc_new", "name": "Doc"}
            if method == "GET_V3" and "/pages" in path:
                return {"pages": [{"id": "page_default"}]}
            if method == "PUT_V3" and "/pages/page_default" in path:
                return {"updated": True}
            return {}

        client = FlexClient()
        client._handle = lambda method, path, **kw: track_handler(method, path, **kw)
        client.dry_run = False

        args = Namespace(space="testspace", name="Doc", content="# Hello",
                         content_file=None, visibility=None)
        result = cmd_docs_create(client, args)
        self.assertEqual(result["id"], "doc_new")
        self.assertTrue(result.get("_initial_content_written"))
        self.assertEqual(result.get("_page_id"), "page_default")

    def test_create_with_content_no_pages_returned(self):
        """When API returns no pages, content is silently skipped."""
        def track_handler(method, path, **kwargs):
            if method == "POST_V3" and "/docs" in path and "/pages" not in path:
                return {"id": "doc_new", "name": "Doc"}
            if method == "GET_V3" and "/pages" in path:
                return {"pages": []}
            return {}

        client = FlexClient()
        client._handle = lambda method, path, **kw: track_handler(method, path, **kw)
        client.dry_run = False

        args = Namespace(space="testspace", name="Doc", content="# Hello",
                         content_file=None, visibility=None)
        result = cmd_docs_create(client, args)
        self.assertEqual(result["id"], "doc_new")
        self.assertNotIn("_initial_content_written", result)

    def test_create_with_content_no_doc_id(self):
        """When API returns no doc ID, content writing is skipped."""
        def track_handler(method, path, **kwargs):
            if method == "POST_V3":
                return {"name": "Doc"}  # No "id" field
            return {}

        client = FlexClient()
        client._handle = lambda method, path, **kw: track_handler(method, path, **kw)
        client.dry_run = False

        args = Namespace(space="testspace", name="Doc", content="# Hello",
                         content_file=None, visibility=None)
        result = cmd_docs_create(client, args)
        self.assertNotIn("_initial_content_written", result)


# ─── Init Command ─────────────────────────────────────────────────────────


class InitTokenFlagTests(unittest.TestCase):
    """Tests for cmd_init with --token flag path."""

    @patch("clickup_cli.commands.init.requests.get")
    def test_token_flag_skips_input_prompt(self, mock_get):
        """--token flag bypasses interactive input."""
        mock_team_resp = MagicMock()
        mock_team_resp.status_code = 200
        mock_team_resp.ok = True
        mock_team_resp.json.return_value = {
            "teams": [{
                "id": "ws1", "name": "TestWS",
                "members": [{"user": {"id": "u1", "username": "testuser"}}]
            }]
        }

        mock_spaces_resp = MagicMock()
        mock_spaces_resp.status_code = 200
        mock_spaces_resp.ok = True
        mock_spaces_resp.json.return_value = {"spaces": []}

        # side_effect: first call = /team, second call = /space
        mock_get.side_effect = [mock_team_resp, mock_spaces_resp]

        args = Namespace(token="pk_test_123")
        with patch("builtins.open", unittest.mock.mock_open()):
            with patch("os.makedirs"):
                with patch("clickup_cli.commands.init.os.chmod"):
                    cmd_init(args)

        # Should NOT have called input() — token was provided via flag
        self.assertEqual(mock_get.call_count, 2)

    @patch("clickup_cli.commands.init.os.chmod")
    @patch("clickup_cli.commands.init.os.makedirs")
    @patch("clickup_cli.commands.init.requests.get")
    def test_token_flag_hardens_config_directory_and_file(
        self, mock_get, mock_makedirs, mock_chmod
    ):
        """Init hardens the config directory and written config file."""
        mock_team_resp = MagicMock()
        mock_team_resp.status_code = 200
        mock_team_resp.ok = True
        mock_team_resp.json.return_value = {
            "teams": [{
                "id": "ws1", "name": "TestWS",
                "members": [{"user": {"id": "u1", "username": "testuser"}}]
            }]
        }

        mock_spaces_resp = MagicMock()
        mock_spaces_resp.status_code = 200
        mock_spaces_resp.ok = True
        mock_spaces_resp.json.return_value = {"spaces": []}
        mock_get.side_effect = [mock_team_resp, mock_spaces_resp]

        args = Namespace(token="pk_test_123")
        with patch("builtins.open", unittest.mock.mock_open()):
            cmd_init(args)

        mock_makedirs.assert_called_once_with(
            unittest.mock.ANY, mode=0o700, exist_ok=True
        )
        self.assertEqual(
            mock_chmod.call_args_list,
            [
                unittest.mock.call(unittest.mock.ANY, 0o700),
                unittest.mock.call(unittest.mock.ANY, 0o600),
            ],
        )


class InitErrorTests(unittest.TestCase):
    """Tests for cmd_init error paths."""

    def test_empty_token_exits(self):
        """Empty token after input prompt exits."""
        args = Namespace(token=None)
        with patch("builtins.input", return_value=""):
            with self.assertRaises(SystemExit):
                cmd_init(args)

    @patch("clickup_cli.commands.init.requests.get")
    def test_connection_error_exits(self, mock_get):
        """Network error when fetching teams exits."""
        mock_get.side_effect = requests.ConnectionError("Network down")
        args = Namespace(token="pk_test")
        with self.assertRaises(SystemExit):
            cmd_init(args)

    @patch("clickup_cli.commands.init.requests.get")
    def test_401_invalid_token_exits(self, mock_get):
        """401 response exits with auth error."""
        resp = MagicMock()
        resp.status_code = 401
        resp.ok = False
        mock_get.return_value = resp
        args = Namespace(token="pk_bad")
        with self.assertRaises(SystemExit):
            cmd_init(args)

    @patch("clickup_cli.commands.init.requests.get")
    def test_non_ok_response_exits(self, mock_get):
        """Non-200 non-401 response exits."""
        resp = MagicMock()
        resp.status_code = 500
        resp.ok = False
        resp.text = "Server Error"
        mock_get.return_value = resp
        args = Namespace(token="pk_test")
        with self.assertRaises(SystemExit):
            cmd_init(args)

    @patch("clickup_cli.commands.init.requests.get")
    def test_no_workspaces_exits(self, mock_get):
        """Empty teams list exits."""
        resp = MagicMock()
        resp.status_code = 200
        resp.ok = True
        resp.json.return_value = {"teams": []}
        mock_get.return_value = resp
        args = Namespace(token="pk_test")
        with self.assertRaises(SystemExit):
            cmd_init(args)


class InitWorkspaceSelectionTests(unittest.TestCase):
    """Tests for workspace and member selection in cmd_init."""

    def _make_team_response(self, teams):
        resp = MagicMock()
        resp.status_code = 200
        resp.ok = True
        resp.json.return_value = {"teams": teams}
        return resp

    def _make_spaces_response(self, spaces=None):
        resp = MagicMock()
        resp.status_code = 200
        resp.ok = True
        resp.json.return_value = {"spaces": spaces or []}
        return resp

    @patch("clickup_cli.commands.init.requests.get")
    def test_single_workspace_auto_selects(self, mock_get):
        """Single workspace is auto-selected without prompting."""
        team = {"id": "ws1", "name": "MyWS",
                "members": [{"user": {"id": "u1", "username": "testuser"}}]}
        mock_get.side_effect = [
            self._make_team_response([team]),
            self._make_spaces_response(),
        ]
        args = Namespace(token="pk_test")
        with patch("builtins.open", unittest.mock.mock_open()) as mock_file:
            with patch("os.makedirs"):
                with patch("clickup_cli.commands.init.os.chmod"):
                    cmd_init(args)

        # Verify config was written with correct workspace_id
        written = mock_file().write.call_args_list
        written_text = "".join(call[0][0] for call in written)
        self.assertIn("ws1", written_text)

    @patch("clickup_cli.commands.init.requests.get")
    def test_multiple_workspaces_prompts_selection(self, mock_get):
        """Multiple workspaces prompts user for selection."""
        teams = [
            {"id": "ws1", "name": "WS1", "members": [{"user": {"id": "u1", "username": "testuser"}}]},
            {"id": "ws2", "name": "WS2", "members": []},
        ]
        mock_get.side_effect = [
            self._make_team_response(teams),
            self._make_spaces_response(),
        ]
        args = Namespace(token="pk_test")
        with patch("builtins.input", return_value="2"):
            with patch("builtins.open", unittest.mock.mock_open()) as mock_file:
                with patch("os.makedirs"):
                    with patch("clickup_cli.commands.init.os.chmod"):
                        cmd_init(args)

        written = mock_file().write.call_args_list
        written_text = "".join(call[0][0] for call in written)
        self.assertIn("ws2", written_text)

    @patch("clickup_cli.commands.init.requests.get")
    def test_multiple_members_skip_selection(self, mock_get):
        """When user presses Enter on member selection, user_id stays empty."""
        team = {"id": "ws1", "name": "MyWS", "members": [
            {"user": {"id": "u1", "username": "alice", "email": "a@x.com"}},
            {"user": {"id": "u2", "username": "bob", "email": "b@x.com"}},
        ]}
        mock_get.side_effect = [
            self._make_team_response([team]),
            self._make_spaces_response(),
        ]
        args = Namespace(token="pk_test")
        with patch("builtins.input", return_value=""):
            with patch("builtins.open", unittest.mock.mock_open()) as mock_file:
                with patch("os.makedirs"):
                    with patch("clickup_cli.commands.init.os.chmod"):
                        cmd_init(args)

        written = mock_file().write.call_args_list
        written_text = "".join(call[0][0] for call in written)
        self.assertIn('"user_id": ""', written_text)

    @patch("clickup_cli.commands.init.requests.get")
    def test_spaces_fetched_and_config_written(self, mock_get):
        """Spaces are written with canonical space_id values only."""
        team = {"id": "ws1", "name": "MyWS",
                "members": [{"user": {"id": "u1", "username": "testuser"}}]}

        spaces_resp = self._make_spaces_response([
            {"id": "s1", "name": "Personal"},
        ])

        mock_get.side_effect = [
            self._make_team_response([team]),
            spaces_resp,
        ]
        args = Namespace(token="pk_test")
        with patch("builtins.open", unittest.mock.mock_open()) as mock_file:
            with patch("os.makedirs"):
                with patch("clickup_cli.commands.init.os.chmod"):
                    cmd_init(args)

        written = mock_file().write.call_args_list
        written_text = "".join(call[0][0] for call in written)
        self.assertIn("personal", written_text)
        self.assertIn("s1", written_text)
        self.assertNotIn("list_id", written_text)
        self.assertEqual(mock_get.call_count, 2)

    @patch("clickup_cli.commands.init.requests.get")
    def test_eof_during_workspace_selection_exits(self, mock_get):
        """EOFError during workspace selection aborts gracefully."""
        teams = [
            {"id": "ws1", "name": "WS1", "members": []},
            {"id": "ws2", "name": "WS2", "members": []},
        ]
        mock_get.return_value = self._make_team_response(teams)
        args = Namespace(token="pk_test")
        with patch("builtins.input", side_effect=EOFError):
            with self.assertRaises(SystemExit):
                cmd_init(args)

    def test_eof_during_token_input_exits(self):
        """EOFError during token input aborts gracefully."""
        args = Namespace(token=None)
        with patch("builtins.input", side_effect=EOFError):
            with self.assertRaises(SystemExit):
                cmd_init(args)
