"""Handler tests for task commands."""

import argparse
import contextlib
import io
import json
import tempfile
import unittest
from argparse import Namespace
from types import SimpleNamespace
from unittest.mock import MagicMock

from clickup_cli.commands import tasks as tasks_commands
from clickup_cli.commands.tasks import (
    cmd_tasks_add_to_list,
    cmd_tasks_create,
    cmd_tasks_depend,
    cmd_tasks_get,
    cmd_tasks_link,
    cmd_tasks_list,
    cmd_tasks_lists,
    cmd_tasks_merge,
    cmd_tasks_move,
    cmd_tasks_remove_from_list,
    cmd_tasks_search,
    cmd_tasks_update,
    register_parser as register_tasks_parser,
)

from command_fakes import FlexClient

class TasksGetTests(unittest.TestCase):

    def test_get_with_bounded_comments_by_default(self):
        client = MagicMock()
        client.dry_run = False
        client.get_v2.side_effect = [
            {"id": "t1", "name": "Task"},  # GET /task/t1
            {"comments": [
                {"id": "c1", "comment_text": "Hello", "user": {"username": "testuser"}, "date": "1000"}
            ]},  # GET /task/t1/comment (first call)
            {"comments": [
                {"id": "c2", "comment_text": "Later", "user": {"username": "other"}, "date": "2000"}
            ]},  # bounded completeness probe finds more
        ]
        args = Namespace(task_id="t1", no_comments=False, all_comments=False)
        result = cmd_tasks_get(client, args)

        self.assertEqual(result["id"], "t1")
        self.assertEqual(result["comment_count"], 1)
        self.assertEqual(result["comment_count_returned"], 1)
        self.assertFalse(result["comments_complete"])
        self.assertTrue(result["comments_truncated"])
        self.assertEqual(result["comments"][0]["user"], "testuser")

    def test_get_with_all_comments_fetches_every_page(self):
        client = MagicMock()
        client.dry_run = False
        client.get_v2.side_effect = [
            {"id": "t1", "name": "Task"},
            {"comments": [
                {"id": "c1", "comment_text": "Hello", "user": {"username": "testuser"}, "date": "1000"}
            ]},
            {"comments": [
                {"id": "c2", "comment_text": "Later", "user": {"username": "other"}, "date": "2000"}
            ]},
            {"comments": []},
        ]

        result = cmd_tasks_get(
            client,
            Namespace(task_id="t1", no_comments=False, all_comments=True),
        )

        self.assertEqual(result["comment_count"], 2)
        self.assertEqual(result["comment_count_returned"], 2)
        self.assertTrue(result["comments_complete"])
        self.assertFalse(result["comments_truncated"])
        self.assertEqual([comment["id"] for comment in result["comments"]], ["c1", "c2"])

    def test_get_no_comments_flag(self):
        client = MagicMock()
        client.dry_run = False
        client.get_v2.return_value = {"id": "t1", "name": "Task"}
        args = Namespace(task_id="t1", no_comments=True, all_comments=False)
        result = cmd_tasks_get(client, args)
        self.assertEqual(result["id"], "t1")
        self.assertNotIn("comments", result)
        # Only one call (the task fetch), no comment fetch
        client.get_v2.assert_called_once()

    def test_get_comment_fetch_error_warns(self):
        import requests as req

        client = MagicMock()
        client.dry_run = False
        client.get_v2.side_effect = [
            {"id": "t1", "name": "Task"},  # task fetch
            req.RequestException("timeout"),  # comment fetch fails
        ]
        args = Namespace(task_id="t1", no_comments=False, all_comments=False)
        result = cmd_tasks_get(client, args)
        self.assertEqual(result["comment_count"], 0)
        self.assertEqual(result["comment_count_returned"], 0)
        self.assertFalse(result["comments_complete"])
        self.assertFalse(result["comments_truncated"])
        self.assertEqual(result["comments"], [])

    def test_get_fields_filters_hydrated_task(self):
        client = MagicMock()
        client.dry_run = False
        client.get_v2.side_effect = [
            {"id": "t1", "name": "Task", "status": {"status": "open"}},
            {"comments": []},
        ]
        args = Namespace(
            task_id="t1",
            no_comments=False,
            all_comments=False,
            fields="id,name,comment_count",
            full=False,
        )

        result = cmd_tasks_get(client, args)

        self.assertEqual(result, {"id": "t1", "name": "Task", "comment_count": 0})

    def test_get_full_no_comments_returns_raw_task(self):
        client = MagicMock()
        client.dry_run = False
        client.get_v2.return_value = {"id": "t1", "name": "Task", "extra": "kept"}
        args = Namespace(
            task_id="t1",
            no_comments=True,
            all_comments=False,
            fields=None,
            full=True,
        )

        result = cmd_tasks_get(client, args)

        self.assertEqual(result, {"id": "t1", "name": "Task", "extra": "kept"})
        client.get_v2.assert_called_once()


class TasksMoveTests(unittest.TestCase):

    def test_move_with_space_name(self):
        client = FlexClient(responses={"/home_list/": {"id": "t1"}})
        args = Namespace(task_id="t1", to_list="testspace")
        cmd_tasks_move(client, args)
        # Should resolve testspace -> list_id 222
        self.assertIn("/home_list/222", client.calls[0]["path"])

    def test_move_with_raw_id(self):
        client = FlexClient(responses={"/home_list/": {"id": "t1"}})
        args = Namespace(task_id="t1", to_list="99999")
        cmd_tasks_move(client, args)
        self.assertIn("/home_list/99999", client.calls[0]["path"])

    def test_move_dry_run(self):
        client = FlexClient(dry_run=True)
        args = Namespace(task_id="t1", to_list="testspace")
        result = cmd_tasks_move(client, args)
        self.assertTrue(result["dry_run"])
        self.assertEqual(result["destination_list_id"], "222")

    def test_move_uses_runtime_workspace_and_lazy_default_list(self):
        client = FlexClient(
            responses={
                "/space/runtime_space/list": {"lists": [{"id": "runtime_list"}]},
                "/home_list/": {"id": "t1"},
            },
            runtime=SimpleNamespace(
                workspace_id="runtime_ws",
                user_id="",
                spaces={"runtime": {"space_id": "runtime_space"}},
            ),
        )

        cmd_tasks_move(client, Namespace(task_id="t1", to_list="runtime"))

        self.assertIn("/space/runtime_space/list", client.calls[0]["path"])
        self.assertIn(
            "/workspaces/runtime_ws/tasks/t1/home_list/runtime_list",
            client.calls[-1]["path"],
        )


class TasksMergeTests(unittest.TestCase):

    def test_merge_dry_run(self):
        client = FlexClient(dry_run=True)
        args = Namespace(task_id="target", source_ids="a,b,c")
        result = cmd_tasks_merge(client, args)
        self.assertTrue(result["dry_run"])
        self.assertEqual(result["source_task_ids"], ["a", "b", "c"])

    def test_merge_actual(self):
        client = FlexClient(responses={"/merge": {"id": "target"}})
        args = Namespace(task_id="target", source_ids="a,b")
        cmd_tasks_merge(client, args)
        body = client.calls[-1]["data"]
        self.assertEqual(body["task_ids"], ["a", "b"])


class TasksListDryRunTests(unittest.TestCase):

    def test_list_dry_run(self):
        client = FlexClient(dry_run=True)
        args = Namespace(space="testspace", list_id=None, include_closed=False,
                         status=None, subtasks=False, fields=None, full=False)
        result = cmd_tasks_list(client, args)
        self.assertTrue(result["dry_run"])
        self.assertEqual(result["action"], "list_tasks")

    def test_list_with_list_id_overrides_space(self):
        client = FlexClient(dry_run=True)
        args = Namespace(space="testspace", list_id="custom_list", include_closed=False,
                         status=None, subtasks=False, fields=None, full=False)
        result = cmd_tasks_list(client, args)
        self.assertEqual(result["list_id"], "custom_list")

    def test_list_alias_without_cached_list_uses_lazy_lookup(self):
        client = FlexClient(
            dry_run=True,
            responses={"/space/runtime_space/list": {"lists": [{"id": "runtime_list"}]}},
            runtime=SimpleNamespace(
                workspace_id="runtime_ws",
                user_id="",
                spaces={"runtime": {"space_id": "runtime_space"}},
            ),
        )

        result = cmd_tasks_list(
            client,
            Namespace(
                space="runtime",
                list_id=None,
                include_closed=False,
                status=None,
                subtasks=False,
                fields=None,
                full=False,
            ),
        )

        self.assertEqual(result["list_id"], "runtime_list")
        self.assertEqual(client.calls[0]["path"], "/space/runtime_space/list")


class TasksUpdateBehaviorTests(unittest.TestCase):

    def test_update_name(self):
        client = FlexClient(responses={"/task/": {"id": "t1", "name": "New"}})
        args = Namespace(task_id="t1", name="New", status=None,
                         desc=None, desc_file=None, priority=None)
        cmd_tasks_update(client, args)
        body = client.calls[-1]["data"]
        self.assertEqual(body["name"], "New")

    def test_update_status(self):
        client = FlexClient(responses={"/task/": {"id": "t1"}})
        args = Namespace(task_id="t1", name=None, status="done",
                         desc=None, desc_file=None, priority=None)
        cmd_tasks_update(client, args)
        body = client.calls[-1]["data"]
        self.assertEqual(body["status"], "done")

    def test_update_priority(self):
        client = FlexClient(responses={"/task/": {"id": "t1"}})
        args = Namespace(task_id="t1", name=None, status=None,
                         desc=None, desc_file=None, priority="high")
        cmd_tasks_update(client, args)
        body = client.calls[-1]["data"]
        self.assertEqual(body["priority"], 2)

    def test_update_empty_body_errors(self):
        client = FlexClient()
        args = Namespace(task_id="t1", name=None, status=None,
                         desc=None, desc_file=None, priority=None)
        with self.assertRaises(SystemExit):
            cmd_tasks_update(client, args)


class TasksUpdateExpandedFieldsTests(unittest.TestCase):
    """Coverage for assignee/tag/custom-field support on tasks update."""

    def _args(self, **overrides):
        defaults = dict(
            task_id="t1", name=None, status=None, desc=None, desc_file=None,
            priority=None, add_assignees=None, remove_assignees=None,
            add_tags=None, remove_tags=None, custom_fields=None,
        )
        defaults.update(overrides)
        return Namespace(**defaults)

    def test_assignee_diff_packed_into_put_body(self):
        client = FlexClient(responses={"/task/": {"id": "t1"}})
        cmd_tasks_update(client, self._args(
            add_assignees=["123", "456"], remove_assignees=["789"]))
        put_call = next(c for c in client.calls if c["method"] == "PUT")
        self.assertEqual(put_call["data"]["assignees"], {"add": [123, 456], "rem": [789]})

    def test_tag_add_issues_post_per_tag(self):
        client = FlexClient(responses={
            "/task/t1": {"id": "t1"},
        })
        cmd_tasks_update(client, self._args(
            add_tags=["Urgent", "In Review"]))
        post_calls = [c for c in client.calls if c["method"] == "POST"]
        tag_names = [c["path"].rsplit("/", 1)[-1] for c in post_calls]
        self.assertEqual(tag_names, ["urgent", "in review"])

    def test_tag_remove_issues_delete_per_tag(self):
        client = FlexClient(responses={"/task/t1": {"id": "t1"}})
        cmd_tasks_update(client, self._args(remove_tags=["draft"]))
        delete_calls = [c for c in client.calls if c["method"] == "DELETE"]
        self.assertEqual(len(delete_calls), 1)
        self.assertTrue(delete_calls[0]["path"].endswith("/tag/draft"))

    def test_custom_field_posts_one_per_field(self):
        client = FlexClient(responses={"/task/t1": {"id": "t1"}})
        cmd_tasks_update(client, self._args(
            custom_fields=["abc-uuid=high", "xyz-uuid=42"]))
        post_calls = [c for c in client.calls if c["method"] == "POST"]
        # Last one should target /task/t1/field/xyz-uuid with value 42
        self.assertEqual(post_calls[-1]["path"], "/task/t1/field/xyz-uuid")
        self.assertEqual(post_calls[-1]["data"], {"value": "42"})

    def test_custom_field_bad_format_errors(self):
        client = FlexClient()
        with self.assertRaises(SystemExit):
            cmd_tasks_update(client, self._args(custom_fields=["nomarkerhere"]))

    def test_side_effect_only_update_fetches_final_state(self):
        """When no PUT body is needed, fetch the task to return final state."""
        client = FlexClient(responses={"/task/t1": {"id": "t1", "name": "fetched"}})
        result = cmd_tasks_update(client, self._args(add_tags=["urgent"]))
        methods = [c["method"] for c in client.calls]
        self.assertIn("GET", methods)
        self.assertEqual(result.get("name"), "fetched")

    def test_dry_run_returns_plan_without_calls(self):
        client = FlexClient(dry_run=True)
        result = cmd_tasks_update(client, self._args(
            name="renamed", add_tags=["urgent"], remove_tags=["draft"],
            add_assignees=["42"],
            custom_fields=["f1=hello"]))
        self.assertTrue(result["dry_run"])
        self.assertEqual(result["put_body"]["name"], "renamed")
        self.assertEqual(result["tag_adds"], ["urgent"])
        self.assertEqual(result["tag_removes"], ["draft"])
        self.assertEqual(result["custom_fields"], [{"field_id": "f1", "value": "hello"}])
        # Dry-run must not issue any API call
        self.assertEqual(client.calls, [])

    def test_update_empty_description_clear_inline(self):
        client = FlexClient(dry_run=True)
        result = cmd_tasks_update(client, self._args(desc=""))
        self.assertTrue(result["dry_run"])
        self.assertEqual(result["put_body"]["markdown_description"], "")
        self.assertEqual(client.calls, [])

    def test_update_empty_description_clear_from_file(self):
        client = FlexClient(dry_run=True)
        with tempfile.NamedTemporaryFile("w", encoding="utf-8") as handle:
            result = cmd_tasks_update(client, self._args(desc_file=handle.name))

        self.assertTrue(result["dry_run"])
        self.assertEqual(result["put_body"]["markdown_description"], "")
        self.assertEqual(client.calls, [])


class TasksCreateBehaviorTests(unittest.TestCase):

    def _make_args(self, **overrides):
        defaults = dict(space="testspace", list_id=None, name="Task",
                          desc=None, desc_file=None,
                          priority=None, status=None, assign_user=None,
                          start_date=None, due_date=None,
                          time_estimate=None, points=None,
                          custom_fields=None, task_type=None, tags=None)
        defaults.update(overrides)
        return Namespace(**defaults)

    def test_create_parser_accepts_richer_phase_ten_flags(self):
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="group")
        register_tasks_parser(subparsers, argparse.RawDescriptionHelpFormatter)
        tasks_parser = subparsers.choices["tasks"]

        args = tasks_parser.parse_args(
            [
                "create",
                "--space",
                "testspace",
                "--name",
                "Task",
                "--start-date",
                "2026-04-21",
                "--due-date",
                "2026-04-24",
                "--time-estimate",
                "90m",
                "--points",
                "3",
                "--custom-field",
                "field-1=high",
                "--custom-field",
                "field-2=42",
                "--task-type",
                "type-1",
            ]
        )

        self.assertEqual(args.start_date, "2026-04-21")
        self.assertEqual(args.due_date, "2026-04-24")
        self.assertEqual(args.time_estimate, "90m")
        self.assertEqual(args.points, "3")
        self.assertEqual(args.custom_fields, ["field-1=high", "field-2=42"])
        self.assertEqual(args.task_type, "type-1")

    def test_no_priority_when_unset(self):
        client = FlexClient(dry_run=True)
        args = self._make_args()
        result = cmd_tasks_create(client, args)
        self.assertNotIn("priority", result["body"])

    def test_priority_from_arg(self):
        client = FlexClient(dry_run=True)
        args = self._make_args(priority="high")
        result = cmd_tasks_create(client, args)
        self.assertEqual(result["body"]["priority"], 2)

    def test_assign_user(self):
        client = FlexClient(dry_run=True)
        args = self._make_args(assign_user="99999")
        result = cmd_tasks_create(client, args)
        self.assertEqual(result["body"]["assignees"], [99999])

    def test_no_assignee_by_default(self):
        client = FlexClient(dry_run=True)
        args = self._make_args()
        result = cmd_tasks_create(client, args)
        self.assertNotIn("assignees", result["body"])

    def test_status_set_in_body(self):
        client = FlexClient(dry_run=True)
        args = self._make_args(status="in progress")
        result = cmd_tasks_create(client, args)
        self.assertEqual(result["body"]["status"], "in progress")

    def test_richer_core_fields_appear_in_dry_run_body(self):
        client = FlexClient(dry_run=True)
        args = self._make_args(
            start_date="2026-04-21",
            due_date="2026-04-24",
            time_estimate="90m",
            points="3",
        )
        result = cmd_tasks_create(client, args)

        self.assertEqual(result["body"]["start_date"], "1776729600000")
        self.assertEqual(result["body"]["due_date"], "1776988800000")
        self.assertTrue(result["body"]["start_date_time"])
        self.assertTrue(result["body"]["due_date_time"])
        self.assertEqual(result["body"]["time_estimate"], 5400000)
        self.assertEqual(result["body"]["points"], 3)

    def test_create_custom_fields_dry_run_shows_post_create_plan(self):
        client = FlexClient(dry_run=True)
        result = cmd_tasks_create(
            client,
            self._make_args(custom_fields=["field-1=high", "field-2=42"]),
        )

        self.assertEqual(result["action"], "create_task")
        self.assertEqual(result["create_body"]["name"], "Task")
        self.assertEqual(
            result["post_create_custom_fields"],
            [
                {"field_id": "field-1", "value": "high"},
                {"field_id": "field-2", "value": "42"},
            ],
        )
        self.assertEqual(client.calls, [])

    def test_create_custom_fields_live_posts_follow_up_and_fetches_final_task(self):
        client = FlexClient(
            responses={
                "/list/222/task": {"id": "task-1", "name": "Task"},
                "/task/task-1": {"id": "task-1", "name": "Task", "custom_fields": []},
            }
        )

        result = cmd_tasks_create(
            client,
            self._make_args(custom_fields=["field-1=high", "field-2=42"]),
        )

        self.assertEqual(result["id"], "task-1")
        self.assertEqual(
            [call["path"] for call in client.calls],
            [
                "/list/222/task",
                "/task/task-1/field/field-1",
                "/task/task-1/field/field-2",
                "/task/task-1",
            ],
        )

    def test_create_tags_dry_run_shows_post_create_plan(self):
        client = FlexClient(dry_run=True)

        result = cmd_tasks_create(client, self._make_args(tags=["Urgent", "In Review"]))

        self.assertEqual(result["action"], "create_task")
        self.assertEqual(result["create_body"], {"name": "Task"})
        self.assertEqual(result["post_create_tags"], ["urgent", "in review"])
        self.assertEqual(client.calls, [])

    def test_create_tags_live_posts_after_create_and_fetches_final_task(self):
        client = FlexClient(
            responses={
                "/list/222/task": {"id": "task-1", "name": "Task"},
                "/task/task-1": {"id": "task-1", "name": "Task", "tags": []},
            }
        )

        result = cmd_tasks_create(client, self._make_args(tags=["Urgent", "In Review"]))

        self.assertEqual(result["id"], "task-1")
        self.assertEqual(
            [call["path"] for call in client.calls],
            [
                "/list/222/task",
                "/task/task-1/tag/urgent",
                "/task/task-1/tag/in review",
                "/task/task-1",
            ],
        )

    def test_create_task_type_sets_supported_create_body_field(self):
        client = FlexClient(
            dry_run=True,
            responses={
                "/team/test_workspace/custom_item": {
                    "custom_items": [{"id": "type-1", "name": "Bug"}]
                }
            },
        )

        result = cmd_tasks_create(client, self._make_args(task_type="type-1"))

        self.assertEqual(result["task_type"], {"id": "type-1", "source": "workspace_custom_item_types"})
        self.assertEqual(result["create_body"]["custom_item_id"], "type-1")

    def test_create_task_type_errors_when_workspace_type_is_unknown(self):
        client = FlexClient(
            responses={"/team/test_workspace/custom_item": {"custom_items": []}}
        )

        with self.assertRaises(SystemExit):
            cmd_tasks_create(client, self._make_args(task_type="missing-type"))

    def test_create_rejects_bad_custom_field_format_before_api_calls(self):
        client = FlexClient(dry_run=True)

        with self.assertRaises(SystemExit):
            cmd_tasks_create(client, self._make_args(custom_fields=["missing-separator"]))

        self.assertEqual(client.calls, [])

    def test_create_rejects_bad_start_date_before_api_calls(self):
        client = FlexClient(dry_run=True)

        with self.assertRaises(SystemExit):
            cmd_tasks_create(client, self._make_args(start_date="04/21/2026"))

        self.assertEqual(client.calls, [])

    def test_create_rejects_bad_due_date_before_api_calls(self):
        client = FlexClient(dry_run=True)

        with self.assertRaises(SystemExit):
            cmd_tasks_create(client, self._make_args(due_date="not-a-date"))

        self.assertEqual(client.calls, [])

    def test_create_rejects_bad_time_estimate_before_api_calls(self):
        client = FlexClient(dry_run=True)

        with self.assertRaises(SystemExit):
            cmd_tasks_create(client, self._make_args(time_estimate="soon"))

        self.assertEqual(client.calls, [])

    def test_create_rejects_bad_points_before_api_calls(self):
        client = FlexClient(dry_run=True)

        with self.assertRaises(SystemExit):
            cmd_tasks_create(client, self._make_args(points="three"))

        self.assertEqual(client.calls, [])

    def test_no_tags_by_default(self):
        """tasks create must not inject any tags unless --tag is passed."""
        client = FlexClient(dry_run=True)
        args = self._make_args()
        result = cmd_tasks_create(client, args)
        self.assertNotIn("tags", result["body"])

    def test_no_tags_even_if_config_has_default_tags(self):
        """Stale `default_tags` entries in config files must be ignored."""
        import clickup_cli.config as cfg
        client = FlexClient(dry_run=True)
        args = self._make_args()
        # Temporarily seed a stale default_tags field on the cached config —
        # proves the CLI no longer reads it.
        original = cfg._config_cache
        cfg._config_cache = dict(original or {})
        cfg._config_cache["default_tags"] = ["created by claude"]
        try:
            result = cmd_tasks_create(client, args)
        finally:
            cfg._config_cache = original
        self.assertNotIn("tags", result["body"])

    def test_empty_inline_description_is_omitted(self):
        client = FlexClient(dry_run=True)
        args = self._make_args(desc="")
        result = cmd_tasks_create(client, args)
        self.assertNotIn("markdown_description", result["body"])

    def test_empty_file_description_is_omitted(self):
        client = FlexClient(dry_run=True)
        with tempfile.NamedTemporaryFile("w", encoding="utf-8") as handle:
            args = self._make_args(desc_file=handle.name)
            result = cmd_tasks_create(client, args)
        self.assertNotIn("markdown_description", result["body"])

    def test_space_inference_produces_empty_stderr(self):
        client = FlexClient(
            dry_run=True,
            responses={"/list/444": {"space": {"id": "333"}}},
        )
        args = self._make_args(space=None, list_id="444")
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            cmd_tasks_create(client, args)
        self.assertEqual(buf.getvalue(), "")


class TasksSearchBehaviorTests(unittest.TestCase):

    def _make_search_args(self, **overrides):
        defaults = dict(
            query="bug",
            include_closed=False,
            include_archived=False,
            space=None,
            list_id=None,
            folder_id=None,
            name_prefix=None,
            tags=None,
            custom_fields=None,
            fields=None,
            full=False,
        )
        defaults.update(overrides)
        return Namespace(**defaults)

    def _search_client_for_full_space_scope(self):
        return FlexClient(
            responses={
                "/space/111/list": {"lists": [{"id": "folderless-1"}, {"id": "shared"}]},
                "/space/111/folder": {"folders": [{"id": "f1"}, {"id": "f2"}]},
                "/folder/f1/list": {"lists": [{"id": "folder-list-1"}, {"id": "shared"}]},
                "/folder/f2/list": {"lists": [{"id": "folder-list-2"}]},
                "/task": {"tasks": [], "last_page": True},
            }
        )

    def test_auto_name_prefix_for_task_id_pattern(self):
        """Query matching ABC-123 pattern auto-applies --name-prefix."""
        client = FlexClient(responses={
            "/task": {
                "tasks": [
                    {"name": "PROJ-39: Real task", "status": {"status": "open"}, "priority": None, "id": "t1", "url": "u"},
                    {"name": "Something else PROJ-39", "status": {"status": "open"}, "priority": None, "id": "t2", "url": "u"},
                ],
                "last_page": True,
            }
        })
        args = self._make_search_args(query="PROJ-39")
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            result = cmd_tasks_search(client, args)
        # Only the task starting with PROJ-39 should remain
        self.assertEqual(result["count"], 1)
        self.assertTrue(result["tasks"][0]["name"].startswith("PROJ-39"))
        # Auto-prefix must be silent (no informational hint on stderr)
        self.assertEqual(buf.getvalue(), "")

    def test_space_scoping_expands_alias_to_all_lists_in_space(self):
        client = self._search_client_for_full_space_scope()
        args = self._make_search_args(space="testspace")
        cmd_tasks_search(client, args)
        search_call = next(call for call in client.calls if call["path"].endswith("/task"))
        self.assertEqual(
            search_call["params"]["list_ids[]"],
            ["folderless-1", "shared", "folder-list-1", "folder-list-2"],
        )

    def test_space_scoping_uses_runtime_space_alias_and_workspace_id(self):
        client = FlexClient(
            responses={
                "/space/runtime_space/list": {"lists": [{"id": "runtime-folderless"}]},
                "/space/runtime_space/folder": {"folders": []},
                "/task": {"tasks": [], "last_page": True},
            },
            runtime=SimpleNamespace(
                workspace_id="runtime_ws",
                user_id="",
                spaces={"runtime": {"space_id": "runtime_space"}},
            ),
        )

        cmd_tasks_search(client, self._make_search_args(space="runtime"))

        self.assertIn("/space/runtime_space/list", client.calls[0]["path"])
        search_call = next(call for call in client.calls if call["path"].endswith("/task"))
        self.assertEqual(search_call["path"], "/team/runtime_ws/task")
        self.assertEqual(search_call["params"]["list_ids[]"], ["runtime-folderless"])

    def test_space_scoping_expands_raw_space_id_to_all_lists_in_space(self):
        client = self._search_client_for_full_space_scope()
        args = self._make_search_args(space="111")
        cmd_tasks_search(client, args)
        search_call = next(call for call in client.calls if call["path"].endswith("/task"))
        self.assertEqual(
            search_call["params"]["list_ids[]"],
            ["folderless-1", "shared", "folder-list-1", "folder-list-2"],
        )

    def test_space_scoping_errors_when_space_has_no_lists(self):
        client = FlexClient(
            responses={
                "/space/111/list": {"lists": []},
                "/space/111/folder": {"folders": []},
            }
        )
        args = self._make_search_args(space="111")
        with self.assertRaises(SystemExit):
            cmd_tasks_search(client, args)
        self.assertFalse(any(call["path"].endswith("/task") for call in client.calls))

    def test_space_scoping_errors_for_unknown_space_alias(self):
        client = FlexClient(responses={"/task": {"tasks": [], "last_page": True}})
        args = self._make_search_args(space="nope")
        with self.assertRaises(SystemExit):
            cmd_tasks_search(client, args)
        self.assertFalse(any(call["path"].endswith("/task") for call in client.calls))

    def test_bad_space_alias_does_not_override_explicit_list_scope(self):
        client = FlexClient(responses={"/task": {"tasks": [], "last_page": True}})
        args = self._make_search_args(space="badname", list_id="custom_list")

        cmd_tasks_search(client, args)

        self.assertEqual(len(client.calls), 1)
        self.assertEqual(client.calls[0]["params"]["list_ids[]"], "custom_list")

    def test_bad_space_alias_does_not_override_explicit_folder_scope(self):
        client = FlexClient(responses={"/task": {"tasks": [], "last_page": True}})
        args = self._make_search_args(space="badname", folder_id="f123")

        cmd_tasks_search(client, args)

        self.assertEqual(len(client.calls), 1)
        self.assertEqual(client.calls[0]["params"]["project_ids[]"], "f123")

    def test_dry_run_with_active_bad_space_alias_still_fails_validation(self):
        client = FlexClient(dry_run=True)
        args = self._make_search_args(space="badname")

        with self.assertRaises(SystemExit):
            cmd_tasks_search(client, args)

        self.assertEqual(client.calls, [])

    def test_dry_run_preserves_original_envelope_with_active_space(self):
        client = FlexClient(
            dry_run=True,
            responses={
                "/space/111/list": {"lists": [{"id": "folderless-1"}]},
                "/space/111/folder": {"folders": []},
            },
        )
        args = self._make_search_args(space="111")

        result = cmd_tasks_search(client, args)

        self.assertEqual(
            result,
            {"dry_run": True, "action": "search_tasks", "query": "bug"},
        )

    def test_search_accepts_repeatable_custom_field_filters(self):
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="group")
        register_tasks_parser(subparsers, argparse.RawDescriptionHelpFormatter)
        tasks_parser = subparsers.choices["tasks"]

        args = tasks_parser.parse_args(
            [
                "search",
                "bug",
                "--custom-field",
                "field-1=high",
                "--custom-field",
                "field-2=42",
            ]
        )

        self.assertEqual(args.custom_fields, ["field-1=high", "field-2=42"])

    def test_search_serializes_custom_field_filters_for_active_and_archived_passes(self):
        client = FlexClient(
            responses={
                "/task": [
                    {"tasks": [], "last_page": True},
                    {"tasks": [], "last_page": True},
                ]
            }
        )

        cmd_tasks_search(
            client,
            self._make_search_args(
                include_archived=True,
                custom_fields=["field-1=high", "field-2=42"],
            ),
        )

        task_calls = [call for call in client.calls if call["path"].endswith("/task")]
        self.assertEqual(
            task_calls[0]["params"]["custom_fields"],
            [
                {"field_id": "field-1", "operator": "=", "value": "high"},
                {"field_id": "field-2", "operator": "=", "value": "42"},
            ],
        )
        self.assertEqual(task_calls[1]["params"]["custom_fields"], task_calls[0]["params"]["custom_fields"])
        self.assertEqual(task_calls[1]["params"]["archived"], "true")

    def test_search_invalid_custom_field_filter_errors(self):
        client = FlexClient(responses={"/task": {"tasks": [], "last_page": True}})

        with self.assertRaises(SystemExit):
            cmd_tasks_search(client, self._make_search_args(custom_fields=["missing-separator"]))

    def test_search_help_describes_space_scope_as_whole_space(self):
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="group")
        register_tasks_parser(subparsers, argparse.RawDescriptionHelpFormatter)
        tasks_parser = subparsers.choices["tasks"]
        search_parser = tasks_parser._subparsers._group_actions[0].choices["search"]
        help_text = search_parser.format_help()
        self.assertIn("search the whole space", help_text)
        self.assertIn("--custom-field", help_text)

    def test_root_help_lists_recent_task_subcommands(self):
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="group")
        register_tasks_parser(subparsers, argparse.RawDescriptionHelpFormatter)

        help_text = parser.format_help()

        self.assertIn("add-to-list", help_text)
        self.assertIn("remove-from-list", help_text)
        self.assertIn("link", help_text)
        self.assertIn("depend", help_text)

    def test_list_scoping(self):
        client = FlexClient(responses={
            "/task": {"tasks": [], "last_page": True}
        })
        args = self._make_search_args(list_id="custom_list")
        cmd_tasks_search(client, args)
        params = client.calls[0]["params"]
        self.assertEqual(params["list_ids[]"], "custom_list")

    def test_folder_scoping(self):
        client = FlexClient(responses={
            "/task": {"tasks": [], "last_page": True}
        })
        args = self._make_search_args(folder_id="f123")
        cmd_tasks_search(client, args)
        params = client.calls[0]["params"]
        self.assertEqual(params["project_ids[]"], "f123")


# ─── Tag Filtering ───────────────────────────────────────────────────────


class TagFilterTests(unittest.TestCase):

    def test_search_filters_by_tag(self):
        client = FlexClient(responses={
            "/task": {
                "tasks": [
                    {"name": "Has tag", "id": "t1", "status": {"status": "open"},
                     "priority": None, "url": "u",
                     "tags": [{"name": "important"}]},
                    {"name": "No tag", "id": "t2", "status": {"status": "open"},
                     "priority": None, "url": "u",
                     "tags": []},
                ],
                "last_page": True,
            }
        })
        args = Namespace(query="tag", include_closed=False, space=None,
                         list_id=None, folder_id=None, name_prefix=None,
                         tags=["important"], fields=None, full=False)
        result = cmd_tasks_search(client, args)
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["tasks"][0]["name"], "Has tag")

    def test_search_tag_filter_is_case_insensitive(self):
        client = FlexClient(responses={
            "/task": {
                "tasks": [
                    {"name": "Tagged", "id": "t1", "status": {"status": "open"},
                     "priority": None, "url": "u",
                     "tags": [{"name": "Created By Claude"}]},
                ],
                "last_page": True,
            }
        })
        args = Namespace(query="tag", include_closed=False, space=None,
                         list_id=None, folder_id=None, name_prefix=None,
                         tags=["created by claude"], fields=None, full=False)
        result = cmd_tasks_search(client, args)
        self.assertEqual(result["count"], 1)

    def test_list_passes_tags_as_api_param(self):
        client = FlexClient(dry_run=True)
        args = Namespace(space="testspace", list_id=None, include_closed=False,
                         status=None, subtasks=False, tags=["urgent"],
                         fields=None, full=False)
        result = cmd_tasks_list(client, args)
        self.assertTrue(result["dry_run"])


class TasksDependTests(unittest.TestCase):
    """Coverage for `tasks depend add/remove/list`."""

    def _args(self, subcommand, **overrides):
        defaults = dict(
            subcommand=subcommand, task_id="abc123",
            depends_on=None, dependency_of=None,
        )
        defaults.update(overrides)
        return Namespace(**defaults)

    def test_add_depends_on_posts_with_depends_on_body(self):
        client = FlexClient(responses={"/task/abc123/dependency": {}})
        cmd_tasks_depend(client, self._args("add", depends_on="def456"))
        post_call = next(c for c in client.calls if c["method"] == "POST")
        self.assertEqual(post_call["path"], "/task/abc123/dependency")
        self.assertEqual(post_call["data"], {"depends_on": "def456"})

    def test_add_depended_on_by_posts_with_dependency_of_body(self):
        client = FlexClient(responses={"/task/abc123/dependency": {}})
        cmd_tasks_depend(client, self._args("add", dependency_of="def456"))
        post_call = next(c for c in client.calls if c["method"] == "POST")
        self.assertEqual(post_call["data"], {"dependency_of": "def456"})

    def test_remove_delete_carries_query_params(self):
        client = FlexClient(responses={"/task/abc123/dependency": {}})
        cmd_tasks_depend(client, self._args("remove", depends_on="def456"))
        del_call = next(c for c in client.calls if c["method"] == "DELETE")
        self.assertEqual(del_call["params"], {"depends_on": "def456"})

    def test_dry_run_makes_no_api_calls(self):
        client = FlexClient(dry_run=True)
        result = cmd_tasks_depend(client, self._args("add", depends_on="def456"))
        self.assertTrue(result["dry_run"])
        self.assertEqual(result["action"], "depend_add")
        self.assertEqual(client.calls, [])

    def test_add_without_direction_errors(self):
        client = FlexClient()
        with self.assertRaises(SystemExit):
            cmd_tasks_depend(client, self._args("add"))

    def test_list_partitions_dependencies_by_direction(self):
        client = FlexClient(responses={
            "/task/abc123": {
                "id": "abc123",
                "dependencies": [
                    # abc123 waits on blocker1
                    {"task_id": "abc123", "depends_on": "blocker1"},
                    # blocked1 waits on abc123
                    {"task_id": "blocked1", "depends_on": "abc123"},
                ],
            },
        })
        result = cmd_tasks_depend(client, self._args("list"))
        # depends_on = what this task is waiting on
        self.assertEqual(len(result["depends_on"]), 1)
        self.assertEqual(result["depends_on"][0]["depends_on"], "blocker1")
        # depended_on_by = who is waiting on this task
        self.assertEqual(len(result["depended_on_by"]), 1)
        self.assertEqual(result["depended_on_by"][0]["task_id"], "blocked1")


class TasksLinkTests(unittest.TestCase):
    """Coverage for `tasks link add/remove/list`."""

    def _args(self, subcommand, **overrides):
        defaults = dict(
            subcommand=subcommand,
            task_id="abc123",
            linked_task_id=None,
        )
        defaults.update(overrides)
        return Namespace(**defaults)

    def test_add_posts_to_link_endpoint(self):
        client = FlexClient(responses={"/task/abc123/link/def456": {}})
        cmd_tasks_link(client, self._args("add", linked_task_id="def456"))
        post_call = next(c for c in client.calls if c["method"] == "POST")
        self.assertEqual(post_call["path"], "/task/abc123/link/def456")
        self.assertEqual(post_call["data"], {})

    def test_remove_deletes_link_endpoint(self):
        client = FlexClient(responses={"/task/abc123/link/def456": {}})
        cmd_tasks_link(client, self._args("remove", linked_task_id="def456"))
        delete_call = next(c for c in client.calls if c["method"] == "DELETE")
        self.assertEqual(delete_call["path"], "/task/abc123/link/def456")
        self.assertIsNone(delete_call["params"])

    def test_dry_run_add_uses_link_specific_fields(self):
        client = FlexClient(dry_run=True)
        result = cmd_tasks_link(client, self._args("add", linked_task_id="def456"))
        self.assertTrue(result["dry_run"])
        self.assertEqual(result["action"], "link_add")
        self.assertEqual(result["task_id"], "abc123")
        self.assertEqual(result["linked_task_id"], "def456")
        self.assertEqual(client.calls, [])

    def test_add_requires_linked_task_id(self):
        client = FlexClient()
        with self.assertRaises(SystemExit):
            cmd_tasks_link(client, self._args("add"))

    def test_list_returns_only_link_data(self):
        client = FlexClient(
            responses={
                "/task/abc123": {
                    "id": "abc123",
                    "linked_tasks": [
                        {"task_id": "abc123", "link_id": "def456"},
                        {"task_id": "abc123", "link_id": "ghi789"},
                    ],
                    "dependencies": [
                        {"task_id": "abc123", "depends_on": "blocker1"},
                    ],
                }
            }
        )

        result = cmd_tasks_link(client, self._args("list"))

        self.assertEqual(result, {
            "task_id": "abc123",
            "linked_tasks": [
                {"task_id": "abc123", "link_id": "def456"},
                {"task_id": "abc123", "link_id": "ghi789"},
            ],
        })
        self.assertNotIn("dependencies", result)


class TasksMultiListTests(unittest.TestCase):
    """Coverage for task-scoped multi-list commands."""

    def _membership_args(self, **overrides):
        defaults = dict(task_id="abc123", list_id="901816700000")
        defaults.update(overrides)
        return Namespace(**defaults)

    def test_lists_returns_home_and_additional_lists(self):
        client = FlexClient(
            responses={
                "/task/abc123": {
                    "id": "abc123",
                    "list": {"id": "home-1", "name": "Home"},
                    "additional_lists": [
                        {"id": "extra-1", "name": "Extra 1"},
                        {"id": "extra-2", "name": "Extra 2"},
                    ],
                }
            }
        )

        result = cmd_tasks_lists(client, Namespace(task_id="abc123"))

        self.assertEqual(
            result,
            {
                "task_id": "abc123",
                "home_list": {"id": "home-1", "name": "Home"},
                "lists": [
                    {"id": "home-1", "name": "Home"},
                    {"id": "extra-1", "name": "Extra 1"},
                    {"id": "extra-2", "name": "Extra 2"},
                ],
            },
        )

    def test_add_to_list_posts_to_list_task_endpoint(self):
        client = FlexClient(responses={"/list/901816700000/task/abc123": {}})

        cmd_tasks_add_to_list(client, self._membership_args())

        post_call = next(c for c in client.calls if c["method"] == "POST")
        self.assertEqual(post_call["path"], "/list/901816700000/task/abc123")
        self.assertEqual(post_call["data"], {})

    def test_remove_from_list_deletes_list_task_endpoint(self):
        client = FlexClient(responses={"/list/901816700000/task/abc123": {}})

        cmd_tasks_remove_from_list(client, self._membership_args())

        delete_call = next(c for c in client.calls if c["method"] == "DELETE")
        self.assertEqual(delete_call["path"], "/list/901816700000/task/abc123")

    def test_add_to_list_dry_run_uses_membership_action(self):
        client = FlexClient(dry_run=True)

        result = cmd_tasks_add_to_list(client, self._membership_args())

        self.assertTrue(result["dry_run"])
        self.assertEqual(result["action"], "add_to_list")
        self.assertEqual(result["task_id"], "abc123")
        self.assertEqual(result["list_id"], "901816700000")
        self.assertEqual(client.calls, [])

    def test_remove_from_list_surfaces_delete_failures_without_move_fallback(self):
        client = MagicMock()
        client.dry_run = False
        client.delete_v2.side_effect = RuntimeError("cannot remove home list")
        client.put_v3 = MagicMock()

        with self.assertRaises(RuntimeError):
            cmd_tasks_remove_from_list(client, self._membership_args())

        client.put_v3.assert_not_called()


class TasksBulkTests(unittest.TestCase):

    def test_bulk_move_dry_run_combines_ids_and_file(self):
        client = FlexClient(dry_run=True)
        with tempfile.NamedTemporaryFile("w", encoding="utf-8") as handle:
            handle.write("file-1\n\nfile-2\n")
            handle.flush()
            args = Namespace(
                subcommand="move",
                task_ids=["arg-1"],
                task_file=handle.name,
                to_list="dev",
                continue_on_error=False,
            )

            result = tasks_commands.cmd_tasks_bulk(client, args)

        self.assertEqual(result["action"], "bulk_move")
        self.assertEqual(result["task_ids"], ["arg-1", "file-1", "file-2"])
        self.assertEqual(result["destination_list_id"], "444")
        self.assertEqual(client.calls, [])

    def test_bulk_move_stops_on_first_failure_with_resume_details(self):
        client = MagicMock()
        client.dry_run = False
        client.runtime = SimpleNamespace(workspace_id="ws", spaces={})
        client.put_v3.side_effect = [{"id": "a"}, RuntimeError("boom")]
        args = Namespace(
            subcommand="move",
            task_ids=["a", "b", "c"],
            task_file=None,
            to_list="dest",
            continue_on_error=False,
        )

        result = tasks_commands.cmd_tasks_bulk(client, args)

        self.assertEqual(result["completed"], ["a"])
        self.assertEqual(result["failed_task_id"], "b")
        self.assertEqual(result["remaining"], ["b", "c"])
        self.assertEqual(result["resume_from"], "b")
        self.assertEqual(client.put_v3.call_count, 2)

    def test_bulk_move_continue_on_error_records_failures(self):
        client = MagicMock()
        client.dry_run = False
        client.runtime = SimpleNamespace(workspace_id="ws", spaces={})
        client.put_v3.side_effect = [{"id": "a"}, RuntimeError("boom"), {"id": "c"}]
        args = Namespace(
            subcommand="move",
            task_ids=["a", "b", "c"],
            task_file=None,
            to_list="dest",
            continue_on_error=True,
        )

        result = tasks_commands.cmd_tasks_bulk(client, args)

        self.assertEqual(result["completed"], ["a", "c"])
        self.assertEqual(result["failed"], [{"task_id": "b", "error": "boom"}])
        self.assertIsNone(result["resume_from"])
        self.assertEqual(client.put_v3.call_count, 3)

    def test_bulk_tags_dry_run_reads_plan(self):
        client = FlexClient(dry_run=True)
        plan = {"tasks": [{"task_id": "a", "operations": [{"action": "add", "tag": "Urgent"}]}]}
        with tempfile.NamedTemporaryFile("w", encoding="utf-8") as handle:
            json.dump(plan, handle)
            handle.flush()
            result = tasks_commands.cmd_tasks_bulk(
                client,
                Namespace(subcommand="tags", plan_file=handle.name, continue_on_error=False),
            )

        self.assertEqual(result["action"], "bulk_tags")
        self.assertEqual(result["plan"]["tasks"][0]["operations"][0]["tag"], "urgent")
        self.assertEqual(client.calls, [])

    def test_bulk_tags_rejects_invalid_plan_before_dry_run(self):
        client = FlexClient(dry_run=True)
        invalid_plans = [
            {},
            {"tasks": []},
            {"tasks": "a"},
            {"tasks": ["a"]},
            {"tasks": [{"operations": [{"action": "add", "tag": "urgent"}]}]},
            {"tasks": [{"task_id": "a"}]},
            {"tasks": [{"task_id": "a", "operations": []}]},
            {"tasks": [{"task_id": "a", "operations": "add"}]},
            {"tasks": [{"task_id": "a", "operations": ["add"]}]},
            {"tasks": [{"task_id": "a", "operations": [{"action": "add"}]}]},
            {"tasks": [{"task_id": "a", "operations": [{"action": "rename", "tag": "urgent"}]}]},
        ]

        for plan in invalid_plans:
            with self.subTest(plan=plan):
                with tempfile.NamedTemporaryFile("w", encoding="utf-8") as handle:
                    json.dump(plan, handle)
                    handle.flush()

                    with self.assertRaises(SystemExit):
                        tasks_commands.cmd_tasks_bulk(
                            client,
                            Namespace(subcommand="tags", plan_file=handle.name, continue_on_error=False),
                        )

        self.assertEqual(client.calls, [])

    def test_bulk_tags_preserves_operation_order(self):
        client = FlexClient()
        plan = {
            "tasks": [
                {
                    "task_id": "a",
                    "operations": [
                        {"action": "add", "tag": "Urgent"},
                        {"action": "remove", "tag": "Draft"},
                    ],
                }
            ]
        }
        with tempfile.NamedTemporaryFile("w", encoding="utf-8") as handle:
            json.dump(plan, handle)
            handle.flush()
            result = tasks_commands.cmd_tasks_bulk(
                client,
                Namespace(subcommand="tags", plan_file=handle.name, continue_on_error=False),
            )

        self.assertEqual(result["completed"], ["a"])
        self.assertEqual(
            [(call["method"], call["path"]) for call in client.calls],
            [("POST", "/task/a/tag/urgent"), ("DELETE", "/task/a/tag/draft")],
        )

    def test_bulk_tags_stops_on_first_failed_task(self):
        client = MagicMock()
        client.dry_run = False
        client.post_v2.side_effect = [None, RuntimeError("boom")]
        plan = {
            "tasks": [
                {"task_id": "a", "operations": [{"action": "add", "tag": "ok"}]},
                {"task_id": "b", "operations": [{"action": "add", "tag": "bad"}]},
                {"task_id": "c", "operations": [{"action": "add", "tag": "later"}]},
            ]
        }
        with tempfile.NamedTemporaryFile("w", encoding="utf-8") as handle:
            json.dump(plan, handle)
            handle.flush()
            result = tasks_commands.cmd_tasks_bulk(
                client,
                Namespace(subcommand="tags", plan_file=handle.name, continue_on_error=False),
            )

        self.assertEqual(result["completed"], ["a"])
        self.assertEqual(result["failed_task_id"], "b")
        self.assertEqual(result["remaining"], ["b", "c"])


class RawIdFlagAcceptanceTests(unittest.TestCase):
    """--space / --folder name-lookup flags must accept raw numeric IDs."""

    def test_folders_create_with_raw_space_id(self):
        client = FlexClient(dry_run=True)
        args = Namespace(space="901810236409", name="sprint-1")
        from clickup_cli.commands.folders import cmd_folders_create
        result = cmd_folders_create(client, args)
        self.assertEqual(result["space_id"], "901810236409")

    def test_folders_list_with_raw_space_id(self):
        client = FlexClient(responses={
            "/space/": {"folders": [], "last_page": True}
        })
        args = Namespace(space="901810236409")
        from clickup_cli.commands.folders import cmd_folders_list
        cmd_folders_list(client, args)
        self.assertIn("901810236409", client.calls[-1]["path"])

    def test_spaces_get_with_raw_id(self):
        client = FlexClient(responses={"/space/": {"id": "111", "name": "x"}})
        args = Namespace(space="901810236409")
        from clickup_cli.commands.spaces import cmd_spaces_get
        cmd_spaces_get(client, args)
        self.assertIn("901810236409", client.calls[-1]["path"])

    def test_folders_create_unknown_alias_still_errors(self):
        """Unknown non-numeric aliases should still error loudly."""
        client = FlexClient(dry_run=True)
        args = Namespace(space="Personal", name="sprint-1")  # case mismatch
        from clickup_cli.commands.folders import cmd_folders_create
        with self.assertRaises(SystemExit):
            cmd_folders_create(client, args)

    def test_tasks_list_with_raw_space_id_does_api_lookup(self):
        client = FlexClient(responses={
            "/space/901810236409/list": {
                "lists": [{"id": "inferred_list"}],
            },
            "/list/inferred_list/task": {"tasks": [], "last_page": True},
        })
        args = Namespace(space="901810236409", list_id=None,
                         include_closed=False, include_archived=False,
                         status=None, subtasks=False, tags=None,
                         fields=None, full=False)
        cmd_tasks_list(client, args)
        paths = [c["path"] for c in client.calls]
        self.assertTrue(any("/space/901810236409/list" in p for p in paths))
        self.assertTrue(any("/list/inferred_list/task" in p for p in paths))

    def test_tasks_list_raw_space_empty_lists_errors(self):
        client = FlexClient(responses={
            "/space/901810236409/list": {"lists": []},
        })
        args = Namespace(space="901810236409", list_id=None,
                         include_closed=False, include_archived=False,
                         status=None, subtasks=False, tags=None,
                         fields=None, full=False)
        with self.assertRaises(SystemExit):
            cmd_tasks_list(client, args)


class TasksIncludeArchivedTests(unittest.TestCase):
    """--include-archived flag: second API call with archived=true, merged results."""

    def _list_args(self, **overrides):
        defaults = dict(
            space="testspace", list_id=None, include_closed=False,
            include_archived=False, status=None, subtasks=False,
            tags=None, fields=None, full=False, all_pages=False,
        )
        defaults.update(overrides)
        return Namespace(**defaults)

    def test_list_single_call_when_flag_unset(self):
        client = FlexClient(responses={
            "/list/": {"tasks": [], "last_page": True},
        })
        result = cmd_tasks_list(client, self._list_args())
        get_calls = [c for c in client.calls if c["method"] == "GET"]
        self.assertEqual(len(get_calls), 1)
        self.assertEqual(get_calls[0]["params"]["archived"], "false")
        self.assertTrue(result["results_complete"])
        self.assertFalse(result["results_truncated"])

    def test_list_two_calls_when_flag_set(self):
        client = FlexClient(responses={
            "/list/": {"tasks": [], "last_page": True},
        })
        result = cmd_tasks_list(client, self._list_args(include_archived=True))
        get_calls = [c for c in client.calls if c["method"] == "GET"]
        self.assertEqual(len(get_calls), 2)
        seen_archived_values = {c["params"]["archived"] for c in get_calls}
        self.assertEqual(seen_archived_values, {"false", "true"})
        self.assertTrue(result["results_complete"])
        self.assertFalse(result["results_truncated"])

    def test_list_default_budget_truncates_before_third_page(self):
        client = FlexClient(responses={
            "/list/": [
                {"tasks": [{"id": "t1", "name": "A", "status": {"status": "open"}, "priority": None, "url": "u1"}], "last_page": False},
                {"tasks": [{"id": "t2", "name": "B", "status": {"status": "open"}, "priority": None, "url": "u2"}], "last_page": False},
                {"tasks": [{"id": "t3", "name": "C", "status": {"status": "open"}, "priority": None, "url": "u3"}], "last_page": True},
            ]
        })

        result = cmd_tasks_list(client, self._list_args())

        self.assertEqual([task["id"] for task in result["tasks"]], ["t1", "t2"])
        self.assertEqual(result["pages_fetched"], 2)
        self.assertFalse(result["results_complete"])
        self.assertTrue(result["results_truncated"])

    def test_list_all_pages_fetches_full_result(self):
        client = FlexClient(responses={
            "/list/": [
                {"tasks": [{"id": "t1", "name": "A", "status": {"status": "open"}, "priority": None, "url": "u1"}], "last_page": False},
                {"tasks": [{"id": "t2", "name": "B", "status": {"status": "open"}, "priority": None, "url": "u2"}], "last_page": False},
                {"tasks": [{"id": "t3", "name": "C", "status": {"status": "open"}, "priority": None, "url": "u3"}], "last_page": True},
            ]
        })

        result = cmd_tasks_list(client, self._list_args(all_pages=True))

        self.assertEqual([task["id"] for task in result["tasks"]], ["t1", "t2", "t3"])
        self.assertEqual(result["pages_fetched"], 3)
        self.assertTrue(result["results_complete"])
        self.assertFalse(result["results_truncated"])

    def test_list_merges_both_result_sets(self):
        def _resp(path, kwargs):
            archived_flag = kwargs.get("params", {}).get("archived")
            if archived_flag == "true":
                return {"tasks": [{"id": "a1", "name": "archived task",
                                   "status": {"status": "open"},
                                   "priority": None, "url": "u"}],
                        "last_page": True}
            return {"tasks": [{"id": "n1", "name": "live task",
                               "status": {"status": "open"},
                               "priority": None, "url": "u"}],
                    "last_page": True}
        client = FlexClient(responses={"/list/": _resp})
        result = cmd_tasks_list(client, self._list_args(include_archived=True))
        task_ids = {t["id"] for t in result["tasks"]}
        self.assertEqual(task_ids, {"n1", "a1"})
        self.assertEqual(result["count"], 2)

    def test_search_include_archived_makes_two_calls(self):
        client = FlexClient(responses={
            "/task": {"tasks": [], "last_page": True},
        })
        args = Namespace(query="bug", include_closed=False,
                         include_archived=True, space=None, list_id=None,
                          folder_id=None, name_prefix=None, tags=None,
                         fields=None, full=False, all_pages=False)
        result = cmd_tasks_search(client, args)
        get_calls = [c for c in client.calls if c["method"] == "GET"]
        self.assertEqual(len(get_calls), 2)
        archived_flags = [c["params"].get("archived") for c in get_calls]
        self.assertIn("true", archived_flags)
        self.assertTrue(result["results_complete"])
        self.assertFalse(result["results_truncated"])

    def test_search_shared_budget_limits_archived_pass(self):
        client = FlexClient(responses={
            "/task": [
                {"tasks": [{"id": "a1", "name": "Active 1", "status": {"status": "open"}, "priority": None, "url": "u1"}], "last_page": False},
                {"tasks": [{"id": "a2", "name": "Active 2", "status": {"status": "open"}, "priority": None, "url": "u2"}], "last_page": False},
                {"tasks": [{"id": "z1", "name": "Archived 1", "status": {"status": "open"}, "priority": None, "url": "u3"}], "last_page": False},
            ]
        })
        args = Namespace(query="bug", include_closed=False,
                         include_archived=True, space=None, list_id=None,
                         folder_id=None, name_prefix=None, tags=None,
                         fields=None, full=False, all_pages=False)

        result = cmd_tasks_search(client, args)

        self.assertEqual([task["id"] for task in result["tasks"]], ["a1", "a2"])
        self.assertEqual(result["pages_fetched"], 2)
        self.assertFalse(result["results_complete"])
        self.assertTrue(result["results_truncated"])

    def test_search_space_scope_include_archived_uses_archived_lists_and_folders(self):
        def _space_lists(path, kwargs):
            params = kwargs.get("params") or {}
            archived = params.get("archived")
            if archived == "true":
                return {"lists": [{"id": "archived-folderless"}]}
            return {"lists": [{"id": "active-folderless"}]}

        def _space_folders(path, kwargs):
            params = kwargs.get("params") or {}
            archived = params.get("archived")
            if archived == "true":
                return {"folders": [{"id": "archived-folder"}]}
            return {"folders": [{"id": "active-folder"}]}

        def _folder_lists(path, kwargs):
            if "/folder/active-folder/list" in path:
                return {"lists": [{"id": "active-folder-list"}]}
            if "/folder/archived-folder/list" in path:
                return {"lists": [{"id": "archived-folder-list"}]}
            return {"lists": []}

        def _tasks(path, kwargs):
            list_ids = kwargs.get("params", {}).get("list_ids[]", [])
            archived = kwargs.get("params", {}).get("archived")
            if archived == "true":
                return {
                    "tasks": [
                        {
                            "id": "+".join(list_ids),
                            "name": "archived task",
                            "status": {"status": "open"},
                            "priority": None,
                            "url": "u",
                        }
                    ],
                    "last_page": True,
                }
            return {
                "tasks": [
                    {
                        "id": "+".join(list_ids),
                        "name": "live task",
                        "status": {"status": "open"},
                        "priority": None,
                        "url": "u",
                    }
                ],
                "last_page": True,
            }

        client = FlexClient(
            responses={
                "/space/111/list": _space_lists,
                "/space/111/folder": _space_folders,
                "/folder/": _folder_lists,
                "/task": _tasks,
            }
        )
        args = Namespace(
            query="bug",
            include_closed=False,
            include_archived=True,
            space="111",
            list_id=None,
            folder_id=None,
            name_prefix=None,
            tags=None,
            fields=None,
            full=False,
        )

        result = cmd_tasks_search(client, args)

        task_ids = {task["id"] for task in result["tasks"]}
        self.assertEqual(
            task_ids,
            {
                "active-folderless+active-folder-list",
                "active-folderless+active-folder-list+archived-folderless+archived-folder-list",
            },
        )

    def test_search_space_scope_include_archived_handles_archived_only_space(self):
        def _space_lists(path, kwargs):
            params = kwargs.get("params") or {}
            if params.get("archived") == "true":
                return {"lists": [{"id": "archived-folderless"}]}
            return {"lists": []}

        def _space_folders(path, kwargs):
            params = kwargs.get("params") or {}
            if params.get("archived") == "true":
                return {"folders": [{"id": "archived-folder"}]}
            return {"folders": []}

        def _folder_lists(path, kwargs):
            if "/folder/archived-folder/list" in path:
                return {"lists": [{"id": "archived-folder-list"}]}
            return {"lists": []}

        def _tasks(path, kwargs):
            params = kwargs.get("params") or {}
            list_ids = params.get("list_ids[]", [])
            archived = params.get("archived")
            task_id = "+".join(list_ids) or "unscoped"
            return {
                "tasks": [
                    {
                        "id": f"{archived or 'active'}:{task_id}",
                        "name": "task",
                        "status": {"status": "open"},
                        "priority": None,
                        "url": "u",
                    }
                ],
                "last_page": True,
            }

        client = FlexClient(
            responses={
                "/space/111/list": _space_lists,
                "/space/111/folder": _space_folders,
                "/folder/": _folder_lists,
                "/task": _tasks,
            }
        )
        args = Namespace(
            query="bug",
            include_closed=False,
            include_archived=True,
            space="111",
            list_id=None,
            folder_id=None,
            name_prefix=None,
            tags=None,
            fields=None,
            full=False,
        )

        result = cmd_tasks_search(client, args)

        task_ids = {task["id"] for task in result["tasks"]}
        self.assertEqual(task_ids, {"true:archived-folderless+archived-folder-list"})
        task_calls = [
            call
            for call in client.calls
            if call["method"] == "GET" and call["path"].endswith("/task")
        ]
        self.assertEqual(len(task_calls), 1)
        self.assertEqual(task_calls[0]["params"].get("archived"), "true")

    def test_search_space_scope_include_archived_skips_completely_empty_space(self):
        client = FlexClient(
            responses={
                "/space/111/list": {"lists": []},
                "/space/111/folder": {"folders": []},
                "/task": {
                    "tasks": [
                        {
                            "id": "should-not-run",
                            "name": "task",
                            "status": {"status": "open"},
                            "priority": None,
                            "url": "u",
                        }
                    ],
                    "last_page": True,
                },
            }
        )
        args = Namespace(
            query="bug",
            include_closed=False,
            include_archived=True,
            space="111",
            list_id=None,
            folder_id=None,
            name_prefix=None,
            tags=None,
            fields=None,
            full=False,
        )

        result = cmd_tasks_search(client, args)

        self.assertEqual(result["tasks"], [])
        task_calls = [
            call for call in client.calls if call["method"] == "GET" and call["path"].endswith("/task")
        ]
        self.assertEqual(task_calls, [])
