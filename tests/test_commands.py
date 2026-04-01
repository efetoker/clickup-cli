"""Tests for all command handlers — behavioral coverage for every command module."""

import unittest
from argparse import Namespace
from unittest.mock import MagicMock, patch

import requests

from clickup_cli.commands.comments import (
    cmd_comments_add,
    cmd_comments_delete,
    cmd_comments_list,
    cmd_comments_reply,
    cmd_comments_thread,
    cmd_comments_update,
)
from clickup_cli.commands.docs import (
    cmd_docs_create,
    cmd_docs_create_page,
    cmd_docs_get,
    cmd_docs_get_page,
    cmd_docs_list,
    cmd_docs_pages,
    cmd_docs_edit_page,
)
from clickup_cli.commands.folders import (
    cmd_folders_create,
    cmd_folders_delete,
    cmd_folders_get,
    cmd_folders_list,
    cmd_folders_update,
)
from clickup_cli.commands.lists import (
    cmd_lists_create,
    cmd_lists_delete,
    cmd_lists_get,
    cmd_lists_list,
    cmd_lists_update,
)
from clickup_cli.commands.spaces import (
    cmd_spaces_get,
    cmd_spaces_list,
    cmd_spaces_statuses,
)
from clickup_cli.commands.tags import (
    cmd_tags_add,
    cmd_tags_list,
    cmd_tags_remove,
)
from clickup_cli.commands.team import (
    cmd_team_members,
    cmd_team_whoami,
)
from clickup_cli.commands.tasks import (
    cmd_tasks_get,
    cmd_tasks_list,
    cmd_tasks_merge,
    cmd_tasks_move,
    cmd_tasks_create,
    cmd_tasks_update,
    cmd_tasks_search,
)
from clickup_cli.commands.init import cmd_init


class FlexClient:
    """Flexible fake client for testing command handlers."""

    def __init__(self, dry_run=False, responses=None):
        self.dry_run = dry_run
        self._responses = responses or {}
        self._default_response = {"ok": True}
        self.calls = []

    def _handle(self, method, path, **kwargs):
        self.calls.append({"method": method, "path": path, **kwargs})
        if self.dry_run and not kwargs.get("allow_dry_run"):
            return {"dry_run": True, "method": method, "url": path, "kwargs": kwargs}
        # Match by path substring
        for key, resp in self._responses.items():
            if key in path:
                if callable(resp):
                    return resp(path, kwargs)
                return resp
        return dict(self._default_response)

    def get_v2(self, path, params=None, allow_dry_run=False):
        return self._handle("GET", path, params=params, allow_dry_run=allow_dry_run)

    def post_v2(self, path, data=None):
        return self._handle("POST", path, data=data)

    def put_v2(self, path, data=None):
        return self._handle("PUT", path, data=data)

    def delete_v2(self, path):
        return self._handle("DELETE", path)

    def get_v3(self, path, params=None, allow_dry_run=False):
        return self._handle("GET_V3", path, params=params, allow_dry_run=allow_dry_run)

    def post_v3(self, path, data=None):
        return self._handle("POST_V3", path, data=data)

    def put_v3(self, path, data=None):
        return self._handle("PUT_V3", path, data=data)


# ─── Comments ─────────────────────────────────────────────────────────────


class CommentsListTests(unittest.TestCase):

    def test_dry_run(self):
        client = FlexClient(dry_run=True)
        args = Namespace(task_id="t1", fetch_all=False)
        result = cmd_comments_list(client, args)
        self.assertTrue(result["dry_run"])
        self.assertEqual(result["task_id"], "t1")

    def test_first_page_only(self):
        client = FlexClient(responses={
            "/comment": {"comments": [{"id": "c1"}, {"id": "c2"}]}
        })
        args = Namespace(task_id="t1", fetch_all=False)
        result = cmd_comments_list(client, args)
        self.assertEqual(result["count"], 2)

    def test_fetch_all_with_few_comments_returns_first_page(self):
        client = FlexClient(responses={
            "/comment": {"comments": [{"id": "c1"}]}
        })
        args = Namespace(task_id="t1", fetch_all=True)
        result = cmd_comments_list(client, args)
        self.assertEqual(result["count"], 1)

    def test_fetch_all_with_many_comments_paginates(self):
        """When first page has >=25 comments, fetch_all triggers pagination."""
        comments_25 = [{"id": f"c{i}", "date": str(i)} for i in range(25)]
        page2 = [{"id": "c25", "date": "25"}]

        call_count = [0]
        def mock_get(path, kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return {"comments": comments_25}
            elif call_count[0] == 2:
                return {"comments": comments_25}  # fetch_all_comments first call
            elif call_count[0] == 3:
                return {"comments": page2}
            return {"comments": []}

        client = FlexClient(responses={"/comment": mock_get})
        args = Namespace(task_id="t1", fetch_all=True)
        result = cmd_comments_list(client, args)
        self.assertGreaterEqual(result["count"], 25)


class CommentsAddTests(unittest.TestCase):

    def test_add_with_text(self):
        client = FlexClient(responses={"/comment": {"id": "c1"}})
        args = Namespace(task_id="t1", text="Hello", file=None)
        result = cmd_comments_add(client, args)
        self.assertEqual(result["id"], "c1")
        body = client.calls[-1]["data"]
        self.assertEqual(body["comment_text"], "Hello")

    def test_add_no_text_no_file_errors(self):
        client = FlexClient()
        args = Namespace(task_id="t1", text=None, file=None)
        with self.assertRaises(SystemExit):
            cmd_comments_add(client, args)

    def test_add_dry_run(self):
        client = FlexClient(dry_run=True)
        args = Namespace(task_id="t1", text="Hello", file=None)
        result = cmd_comments_add(client, args)
        self.assertTrue(result["dry_run"])


class CommentsUpdateTests(unittest.TestCase):

    def test_update_text(self):
        client = FlexClient()
        args = Namespace(comment_id="c1", text="Updated", file=None, resolved=None)
        result = cmd_comments_update(client, args)
        self.assertEqual(result["status"], "ok")

    def test_update_resolve(self):
        client = FlexClient()
        args = Namespace(comment_id="c1", text=None, file=None, resolved=True)
        result = cmd_comments_update(client, args)
        self.assertEqual(result["action"], "updated")

    def test_update_empty_body_errors(self):
        client = FlexClient()
        args = Namespace(comment_id="c1", text=None, file=None, resolved=None)
        with self.assertRaises(SystemExit):
            cmd_comments_update(client, args)

    def test_update_dry_run(self):
        client = FlexClient(dry_run=True)
        args = Namespace(comment_id="c1", text="New", file=None, resolved=None)
        result = cmd_comments_update(client, args)
        self.assertTrue(result["dry_run"])
        self.assertEqual(result["body"]["comment_text"], "New")


class CommentsDeleteTests(unittest.TestCase):

    def test_delete_dry_run(self):
        client = FlexClient(dry_run=True)
        args = Namespace(comment_id="c1")
        result = cmd_comments_delete(client, args)
        self.assertTrue(result["dry_run"])

    def test_delete_actual(self):
        client = FlexClient()
        args = Namespace(comment_id="c1")
        result = cmd_comments_delete(client, args)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["action"], "deleted")


class CommentsThreadTests(unittest.TestCase):

    def test_thread_dict_response(self):
        client = FlexClient(responses={
            "/reply": {"comments": [{"id": "r1"}, {"id": "r2"}]}
        })
        args = Namespace(comment_id="c1")
        result = cmd_comments_thread(client, args)
        self.assertEqual(result["count"], 2)

    def test_thread_empty_response(self):
        client = FlexClient(responses={
            "/reply": {"comments": []}
        })
        args = Namespace(comment_id="c1")
        result = cmd_comments_thread(client, args)
        self.assertEqual(result["count"], 0)


class CommentsReplyTests(unittest.TestCase):

    def test_reply_with_text(self):
        client = FlexClient(responses={"/reply": {"id": "r1"}})
        args = Namespace(comment_id="c1", text="OK", file=None)
        result = cmd_comments_reply(client, args)
        self.assertEqual(result["id"], "r1")

    def test_reply_no_text_errors(self):
        client = FlexClient()
        args = Namespace(comment_id="c1", text=None, file=None)
        with self.assertRaises(SystemExit):
            cmd_comments_reply(client, args)

    def test_reply_dry_run(self):
        client = FlexClient(dry_run=True)
        args = Namespace(comment_id="c1", text="OK", file=None)
        result = cmd_comments_reply(client, args)
        self.assertTrue(result["dry_run"])
        self.assertEqual(result["action"], "reply")


# ─── Docs ─────────────────────────────────────────────────────────────────


class DocsListTests(unittest.TestCase):

    def test_dry_run(self):
        client = FlexClient(dry_run=True)
        args = Namespace(space=None)
        result = cmd_docs_list(client, args)
        self.assertTrue(result["dry_run"])

    def test_list_without_space_filter(self):
        client = FlexClient(responses={"/docs": {"docs": [{"id": "d1"}]}})
        args = Namespace(space=None)
        result = cmd_docs_list(client, args)
        self.assertEqual(result["count"], 1)

    def test_list_with_space_filter(self):
        client = FlexClient(responses={"/docs": {"docs": [{"id": "d1"}]}})
        args = Namespace(space="testspace")
        cmd_docs_list(client, args)
        # Should have included parent_id param
        params = client.calls[0]["params"]
        self.assertIn("parent_id", params)

    def test_list_pagination(self):
        call_count = [0]
        def mock_docs(path, kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return {"docs": [{"id": "d1"}], "next_cursor": "abc"}
            return {"docs": [{"id": "d2"}]}

        client = FlexClient(responses={"/docs": mock_docs})
        args = Namespace(space=None)
        result = cmd_docs_list(client, args)
        self.assertEqual(result["count"], 2)


class DocsGetTests(unittest.TestCase):

    def test_get_doc(self):
        client = FlexClient(responses={"/docs/": {"id": "d1", "name": "My Doc"}})
        args = Namespace(doc_id="d1")
        result = cmd_docs_get(client, args)
        self.assertEqual(result["id"], "d1")


class DocsCreateTests(unittest.TestCase):

    def test_unknown_space_errors(self):
        client = FlexClient()
        args = Namespace(space="nonexistent", name="Doc", content=None,
                         content_file=None, visibility=None)
        with self.assertRaises(SystemExit):
            cmd_docs_create(client, args)

    def test_dry_run(self):
        client = FlexClient(dry_run=True)
        args = Namespace(space="testspace", name="Doc", content=None,
                         content_file=None, visibility=None)
        result = cmd_docs_create(client, args)
        self.assertTrue(result["dry_run"])
        self.assertEqual(result["body"]["name"], "Doc")

    def test_create_without_content(self):
        client = FlexClient(responses={"/docs": {"id": "d1"}})
        args = Namespace(space="testspace", name="Doc", content=None,
                         content_file=None, visibility=None)
        result = cmd_docs_create(client, args)
        self.assertEqual(result["id"], "d1")

    def test_create_with_visibility(self):
        client = FlexClient(dry_run=True)
        args = Namespace(space="testspace", name="Doc", content=None,
                         content_file=None, visibility="PRIVATE")
        result = cmd_docs_create(client, args)
        self.assertEqual(result["body"]["visibility"], "PRIVATE")


class DocsPagesTests(unittest.TestCase):

    def test_pages(self):
        client = FlexClient(responses={"/pages": [{"id": "p1", "name": "Page"}]})
        args = Namespace(doc_id="d1")
        result = cmd_docs_pages(client, args)
        # Returns whatever API gives back
        self.assertIsNotNone(result)


class DocsGetPageTests(unittest.TestCase):

    def test_get_page_md(self):
        client = FlexClient(responses={
            "/pages/": {"id": "p1", "content": "# Hello"}
        })
        args = Namespace(doc_id="d1", page_id="p1", format="md")
        cmd_docs_get_page(client, args)
        params = client.calls[0]["params"]
        self.assertEqual(params["content_format"], "text/md")

    def test_get_page_plain(self):
        client = FlexClient(responses={
            "/pages/": {"id": "p1", "content": "Hello"}
        })
        args = Namespace(doc_id="d1", page_id="p1", format="plain")
        cmd_docs_get_page(client, args)
        params = client.calls[0]["params"]
        self.assertEqual(params["content_format"], "text/plain")


class DocsEditPageTests(unittest.TestCase):

    def test_replace_content(self):
        client = FlexClient(responses={"/pages/": {"id": "p1", "content": "New"}})
        args = Namespace(doc_id="d1", page_id="p1", content="New",
                         content_file=None, name=None, append=False)
        cmd_docs_edit_page(client, args)
        body = client.calls[-1]["data"]
        self.assertEqual(body["content"], "New")
        self.assertEqual(body["content_format"], "text/md")

    def test_name_only_update(self):
        client = FlexClient(responses={"/pages/": {"id": "p1", "name": "New Name"}})
        args = Namespace(doc_id="d1", page_id="p1", content=None,
                         content_file=None, name="New Name", append=False)
        cmd_docs_edit_page(client, args)
        body = client.calls[-1]["data"]
        self.assertEqual(body["name"], "New Name")
        self.assertNotIn("content", body)

    def test_empty_body_errors(self):
        client = FlexClient()
        args = Namespace(doc_id="d1", page_id="p1", content=None,
                         content_file=None, name=None, append=False)
        with self.assertRaises(SystemExit):
            cmd_docs_edit_page(client, args)

    def test_replace_dry_run(self):
        client = FlexClient(dry_run=True)
        args = Namespace(doc_id="d1", page_id="p1", content="Hi",
                         content_file=None, name=None, append=False)
        result = cmd_docs_edit_page(client, args)
        self.assertTrue(result["dry_run"])
        self.assertEqual(result["body"]["content"], "Hi")


class DocsCreatePageTests(unittest.TestCase):

    def test_create_with_content(self):
        client = FlexClient(responses={"/pages": {"id": "p2"}})
        args = Namespace(doc_id="d1", name="Notes", content="# Notes",
                         content_file=None)
        cmd_docs_create_page(client, args)
        body = client.calls[-1]["data"]
        self.assertEqual(body["name"], "Notes")
        self.assertEqual(body["content"], "# Notes")

    def test_create_name_only(self):
        client = FlexClient(responses={"/pages": {"id": "p2"}})
        args = Namespace(doc_id="d1", name="Empty", content=None,
                         content_file=None)
        cmd_docs_create_page(client, args)
        body = client.calls[-1]["data"]
        self.assertEqual(body["name"], "Empty")
        self.assertNotIn("content", body)


# ─── Folders ──────────────────────────────────────────────────────────────


class FoldersListTests(unittest.TestCase):

    def test_list_folders(self):
        client = FlexClient(responses={
            "/folder": {"folders": [{"id": "f1"}, {"id": "f2"}]}
        })
        args = Namespace(space="testspace")
        result = cmd_folders_list(client, args)
        self.assertEqual(result["count"], 2)


class FoldersGetTests(unittest.TestCase):

    def test_get_folder(self):
        client = FlexClient(responses={"/folder/": {"id": "f1", "name": "Sprint"}})
        args = Namespace(folder_id="f1")
        result = cmd_folders_get(client, args)
        self.assertEqual(result["id"], "f1")


class FoldersCreateTests(unittest.TestCase):

    def test_create_actual(self):
        client = FlexClient(responses={"/folder": {"id": "f1", "name": "New"}})
        args = Namespace(space="testspace", name="New")
        result = cmd_folders_create(client, args)
        self.assertEqual(result["id"], "f1")

    def test_create_dry_run(self):
        client = FlexClient(dry_run=True)
        args = Namespace(space="testspace", name="New")
        result = cmd_folders_create(client, args)
        self.assertTrue(result["dry_run"])
        self.assertEqual(result["body"]["name"], "New")


class FoldersUpdateTests(unittest.TestCase):

    def test_update_name(self):
        client = FlexClient(responses={"/folder/": {"id": "f1", "name": "Renamed"}})
        args = Namespace(folder_id="f1", name="Renamed")
        result = cmd_folders_update(client, args)
        self.assertEqual(result["name"], "Renamed")

    def test_update_empty_body_errors(self):
        client = FlexClient()
        args = Namespace(folder_id="f1", name=None)
        with self.assertRaises(SystemExit):
            cmd_folders_update(client, args)

    def test_update_dry_run(self):
        client = FlexClient(dry_run=True)
        args = Namespace(folder_id="f1", name="New")
        result = cmd_folders_update(client, args)
        self.assertTrue(result["dry_run"])


class FoldersDeleteTests(unittest.TestCase):

    def test_delete_dry_run(self):
        client = FlexClient(dry_run=True)
        args = Namespace(folder_id="f1")
        result = cmd_folders_delete(client, args)
        self.assertTrue(result["dry_run"])

    def test_delete_actual(self):
        client = FlexClient()
        args = Namespace(folder_id="f1")
        result = cmd_folders_delete(client, args)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["action"], "deleted")


# ─── Lists ────────────────────────────────────────────────────────────────


class ListsListTests(unittest.TestCase):

    def test_list_by_folder(self):
        client = FlexClient(responses={
            "/list": {"lists": [{"id": "l1"}]}
        })
        args = Namespace(folder="f1", space=None)
        result = cmd_lists_list(client, args)
        self.assertEqual(result["count"], 1)
        self.assertIn("/folder/f1/list", client.calls[0]["path"])

    def test_list_by_space(self):
        client = FlexClient(responses={
            "/list": {"lists": [{"id": "l1"}, {"id": "l2"}]}
        })
        args = Namespace(folder=None, space="testspace")
        result = cmd_lists_list(client, args)
        self.assertEqual(result["count"], 2)
        self.assertIn("/space/", client.calls[0]["path"])

    def test_list_neither_errors(self):
        client = FlexClient()
        args = Namespace(folder=None, space=None)
        with self.assertRaises(SystemExit):
            cmd_lists_list(client, args)


class ListsGetTests(unittest.TestCase):

    def test_get_list(self):
        client = FlexClient(responses={"/list/": {"id": "l1", "name": "Tasks"}})
        args = Namespace(list_id="l1")
        result = cmd_lists_get(client, args)
        self.assertEqual(result["id"], "l1")


class ListsCreateTests(unittest.TestCase):

    def test_create_in_folder(self):
        client = FlexClient(responses={"/list": {"id": "l1"}})
        args = Namespace(folder="f1", space=None, name="Tasks",
                         content=None, status=None)
        result = cmd_lists_create(client, args)
        self.assertEqual(result["id"], "l1")

    def test_create_in_space(self):
        client = FlexClient(responses={"/list": {"id": "l2"}})
        args = Namespace(folder=None, space="testspace", name="Backlog",
                         content=None, status=None)
        result = cmd_lists_create(client, args)
        self.assertEqual(result["id"], "l2")

    def test_create_neither_errors(self):
        client = FlexClient()
        args = Namespace(folder=None, space=None, name="X",
                         content=None, status=None)
        with self.assertRaises(SystemExit):
            cmd_lists_create(client, args)

    def test_create_dry_run_folder(self):
        client = FlexClient(dry_run=True)
        args = Namespace(folder="f1", space=None, name="Tasks",
                         content=None, status=None)
        result = cmd_lists_create(client, args)
        self.assertTrue(result["dry_run"])
        self.assertIn("folder_id", result)

    def test_create_dry_run_space(self):
        client = FlexClient(dry_run=True)
        args = Namespace(folder=None, space="testspace", name="Tasks",
                         content=None, status=None)
        result = cmd_lists_create(client, args)
        self.assertTrue(result["dry_run"])
        self.assertIn("space_id", result)

    def test_create_with_optional_fields(self):
        client = FlexClient(responses={"/list": {"id": "l1"}})
        args = Namespace(folder="f1", space=None, name="Tasks",
                         content="Description", status="active")
        cmd_lists_create(client, args)
        body = client.calls[-1]["data"]
        self.assertEqual(body["content"], "Description")
        self.assertEqual(body["status"], "active")


class ListsUpdateTests(unittest.TestCase):

    def test_update_name(self):
        client = FlexClient(responses={"/list/": {"id": "l1", "name": "New"}})
        args = Namespace(list_id="l1", name="New", content=None,
                         content_file=None, status=None)
        result = cmd_lists_update(client, args)
        self.assertEqual(result["name"], "New")

    def test_update_empty_body_errors(self):
        client = FlexClient()
        args = Namespace(list_id="l1", name=None, content=None,
                         content_file=None, status=None)
        with self.assertRaises(SystemExit):
            cmd_lists_update(client, args)

    def test_update_dry_run(self):
        client = FlexClient(dry_run=True)
        args = Namespace(list_id="l1", name="New", content=None,
                         content_file=None, status=None)
        result = cmd_lists_update(client, args)
        self.assertTrue(result["dry_run"])

    def test_update_content_and_status(self):
        client = FlexClient(responses={"/list/": {"id": "l1"}})
        args = Namespace(list_id="l1", name=None, content="Desc",
                         content_file=None, status="active")
        cmd_lists_update(client, args)
        body = client.calls[-1]["data"]
        self.assertEqual(body["content"], "Desc")
        self.assertEqual(body["status"], "active")


class ListsDeleteTests(unittest.TestCase):

    def test_delete_dry_run(self):
        client = FlexClient(dry_run=True)
        args = Namespace(list_id="l1")
        result = cmd_lists_delete(client, args)
        self.assertTrue(result["dry_run"])

    def test_delete_actual(self):
        client = FlexClient()
        args = Namespace(list_id="l1")
        result = cmd_lists_delete(client, args)
        self.assertEqual(result["status"], "ok")


# ─── Spaces ───────────────────────────────────────────────────────────────


class SpacesListTests(unittest.TestCase):

    def test_list_spaces(self):
        client = FlexClient(responses={
            "/space": {"spaces": [{"id": "s1"}, {"id": "s2"}]}
        })
        args = Namespace()
        result = cmd_spaces_list(client, args)
        self.assertEqual(result["count"], 2)


class SpacesGetTests(unittest.TestCase):

    def test_get_by_config_name(self):
        client = FlexClient(responses={
            "/space/": {"id": "111", "name": "testspace"}
        })
        args = Namespace(space="testspace")
        result = cmd_spaces_get(client, args)
        self.assertEqual(result["id"], "111")
        # Verify it resolved config name to space_id
        self.assertIn("/space/111", client.calls[0]["path"])

    def test_get_by_raw_id(self):
        client = FlexClient(responses={
            "/space/": {"id": "99999", "name": "Raw"}
        })
        args = Namespace(space="99999")
        cmd_spaces_get(client, args)
        self.assertIn("/space/99999", client.calls[0]["path"])


class SpacesStatusesTests(unittest.TestCase):

    def test_statuses_with_data(self):
        client = FlexClient(responses={
            "/space/": {
                "statuses": [
                    {"status": "open", "type": "open", "color": "#fff", "orderindex": 0},
                    {"status": "done", "type": "closed", "color": "#0f0", "orderindex": 1},
                ]
            }
        })
        args = Namespace(space="testspace")
        result = cmd_spaces_statuses(client, args)
        self.assertEqual(result["count"], 2)
        self.assertEqual(result["statuses"][0]["status"], "open")
        self.assertEqual(result["space"], "testspace")

    def test_statuses_empty(self):
        client = FlexClient(responses={"/space/": {"statuses": []}})
        args = Namespace(space="testspace")
        result = cmd_spaces_statuses(client, args)
        self.assertEqual(result["count"], 0)
        self.assertEqual(result["statuses"], [])


# ─── Tags ─────────────────────────────────────────────────────────────────


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


class TasksGetTests(unittest.TestCase):

    def test_get_with_comments(self):
        client = MagicMock()
        client.dry_run = False
        # First call: get task, second call: get comments (first page), third: empty page
        client.get_v2.side_effect = [
            {"id": "t1", "name": "Task"},  # GET /task/t1
            {"comments": [
                {"id": "c1", "comment_text": "Hello", "user": {"username": "testuser"}, "date": "1000"}
            ]},  # GET /task/t1/comment (first call)
            {"comments": []},  # GET /task/t1/comment (pagination check)
        ]
        args = Namespace(task_id="t1", no_comments=False)
        result = cmd_tasks_get(client, args)
        self.assertEqual(result["id"], "t1")
        self.assertEqual(result["comment_count"], 1)
        self.assertEqual(result["comments"][0]["user"], "testuser")

    def test_get_no_comments_flag(self):
        client = MagicMock()
        client.dry_run = False
        client.get_v2.return_value = {"id": "t1", "name": "Task"}
        args = Namespace(task_id="t1", no_comments=True)
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
        args = Namespace(task_id="t1", no_comments=False)
        result = cmd_tasks_get(client, args)
        self.assertEqual(result["comment_count"], 0)
        self.assertEqual(result["comments"], [])


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


class TasksCreateBehaviorTests(unittest.TestCase):

    def _make_args(self, **overrides):
        defaults = dict(space="testspace", list_id=None, name="Task",
                        desc=None, desc_file=None,
                        priority=None, status=None, assign_user=None)
        defaults.update(overrides)
        return Namespace(**defaults)

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

    def test_no_tags_when_default_tags_empty(self):
        client = FlexClient(dry_run=True)
        args = self._make_args()
        result = cmd_tasks_create(client, args)
        self.assertNotIn("tags", result["body"])


class TasksSearchBehaviorTests(unittest.TestCase):

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
        args = Namespace(query="PROJ-39", include_closed=False, space=None,
                         list_id=None, folder_id=None, name_prefix=None,
                         fields=None, full=False)
        result = cmd_tasks_search(client, args)
        # Only the task starting with PROJ-39 should remain
        self.assertEqual(result["count"], 1)
        self.assertTrue(result["tasks"][0]["name"].startswith("PROJ-39"))

    def test_space_scoping(self):
        client = FlexClient(responses={
            "/task": {"tasks": [], "last_page": True}
        })
        args = Namespace(query="bug", include_closed=False, space="testspace",
                         list_id=None, folder_id=None, name_prefix=None,
                         fields=None, full=False)
        cmd_tasks_search(client, args)
        params = client.calls[0]["params"]
        self.assertEqual(params["list_ids[]"], "222")  # testspace list_id

    def test_list_scoping(self):
        client = FlexClient(responses={
            "/task": {"tasks": [], "last_page": True}
        })
        args = Namespace(query="bug", include_closed=False, space=None,
                         list_id="custom_list", folder_id=None, name_prefix=None,
                         fields=None, full=False)
        cmd_tasks_search(client, args)
        params = client.calls[0]["params"]
        self.assertEqual(params["list_ids[]"], "custom_list")

    def test_folder_scoping(self):
        client = FlexClient(responses={
            "/task": {"tasks": [], "last_page": True}
        })
        args = Namespace(query="bug", include_closed=False, space=None,
                         list_id=None, folder_id="f123", name_prefix=None,
                         fields=None, full=False)
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


# ─── CLI dispatch ─────────────────────────────────────────────────────────


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
                cmd_init(args)

        # Should NOT have called input() — token was provided via flag
        self.assertEqual(mock_get.call_count, 2)


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

    def _make_lists_response(self, lists=None):
        resp = MagicMock()
        resp.status_code = 200
        resp.ok = True
        resp.json.return_value = {"lists": lists or []}
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
                    cmd_init(args)

        written = mock_file().write.call_args_list
        written_text = "".join(call[0][0] for call in written)
        self.assertIn('"user_id": ""', written_text)

    @patch("clickup_cli.commands.init.requests.get")
    def test_spaces_fetched_and_config_written(self, mock_get):
        """Spaces are fetched and included in the config file."""
        team = {"id": "ws1", "name": "MyWS",
                "members": [{"user": {"id": "u1", "username": "testuser"}}]}

        spaces_resp = self._make_spaces_response([
            {"id": "s1", "name": "Personal"},
        ])
        lists_resp = self._make_lists_response([{"id": "L1"}])

        mock_get.side_effect = [
            self._make_team_response([team]),
            spaces_resp,
            lists_resp,  # lists fetch for space "Personal"
        ]
        args = Namespace(token="pk_test")
        with patch("builtins.open", unittest.mock.mock_open()) as mock_file:
            with patch("os.makedirs"):
                cmd_init(args)

        written = mock_file().write.call_args_list
        written_text = "".join(call[0][0] for call in written)
        self.assertIn("personal", written_text)
        self.assertIn("s1", written_text)
        self.assertIn("L1", written_text)

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


if __name__ == "__main__":
    unittest.main()
