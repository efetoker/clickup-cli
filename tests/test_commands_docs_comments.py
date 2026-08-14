"""Handler tests for docs and comments commands."""

import argparse
import tempfile
import unittest
from argparse import Namespace
from types import SimpleNamespace

from command_fakes import FlexClient

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
    cmd_docs_edit_page,
    cmd_docs_get,
    cmd_docs_get_page,
    cmd_docs_list,
    cmd_docs_pages,
)
from clickup_cli.commands.docs import (
    register_parser as register_docs_parser,
)


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
        self.assertEqual(body["notify_all"], False)

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

    def test_update_empty_text_clear_inline(self):
        client = FlexClient(dry_run=True)
        args = Namespace(comment_id="c1", text="", file=None, resolved=None)
        result = cmd_comments_update(client, args)
        self.assertTrue(result["dry_run"])
        self.assertIn("comment_text", result["body"])
        self.assertEqual(result["body"]["comment_text"], "")

    def test_update_empty_text_clear_from_file(self):
        client = FlexClient(dry_run=True)
        with tempfile.NamedTemporaryFile("w", encoding="utf-8") as handle:
            args = Namespace(
                comment_id="c1",
                text=None,
                file=handle.name,
                resolved=None,
            )
            result = cmd_comments_update(client, args)

        self.assertTrue(result["dry_run"])
        self.assertIn("comment_text", result["body"])
        self.assertEqual(result["body"]["comment_text"], "")


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
        self.assertEqual(client.calls[-1]["data"], {"comment_text": "OK", "notify_all": False})

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
        self.assertEqual(result["body"], {"comment_text": "OK", "notify_all": False})


# ─── Docs ─────────────────────────────────────────────────────────────────


class DocsListTests(unittest.TestCase):

    def test_dry_run(self):
        client = FlexClient(dry_run=True)
        args = Namespace(space=None)
        result = cmd_docs_list(client, args)
        self.assertTrue(result["dry_run"])

    def test_dry_run_preserves_original_envelope_with_space(self):
        client = FlexClient(dry_run=True)
        args = Namespace(space="111")

        result = cmd_docs_list(client, args)

        self.assertEqual(
            result,
            {"dry_run": True, "action": "list_docs", "space": "111"},
        )

    def test_dry_run_with_invalid_space_name_fails_before_preview(self):
        client = FlexClient(dry_run=True)
        args = Namespace(space="badname")

        with self.assertRaises(SystemExit):
            cmd_docs_list(client, args)

        self.assertEqual(client.calls, [])

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

    def test_list_with_raw_space_id_filter(self):
        client = FlexClient(responses={"/docs": {"docs": [{"id": "d1"}]}})
        args = Namespace(space="111")
        result = cmd_docs_list(client, args)

        self.assertEqual(result["count"], 1)
        params = client.calls[0]["params"]
        self.assertEqual(params["parent_id"], "111")
        self.assertEqual(params["parent_type"], "SPACE")

    def test_list_uses_runtime_workspace_id(self):
        client = FlexClient(
            responses={"/docs": {"docs": [{"id": "d1"}]}},
            runtime=SimpleNamespace(workspace_id="runtime_ws", user_id="", spaces={}),
        )

        cmd_docs_list(client, Namespace(space=None))

        self.assertIn("/workspaces/runtime_ws/docs", client.calls[0]["path"])

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

    def test_invalid_space_name_fails_before_request(self):
        client = FlexClient(responses={"/docs": {"docs": [{"id": "d1"}]}})
        args = Namespace(space="badname")

        with self.assertRaises(SystemExit):
            cmd_docs_list(client, args)

        self.assertEqual(client.calls, [])

    def test_list_help_mentions_space_name_or_id(self):
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="group")
        register_docs_parser(subparsers, argparse.RawDescriptionHelpFormatter)
        docs_parser = subparsers.choices["docs"]
        list_parser = docs_parser._subparsers._group_actions[0].choices["list"]
        help_text = list_parser.format_help()

        self.assertIn("SPACE_NAME_OR_ID", help_text)


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

    def test_dry_run_with_content_shows_page_write_plan(self):
        client = FlexClient(dry_run=True)
        args = Namespace(space="testspace", name="Doc", content="# Hello",
                         content_file=None, visibility=None)

        result = cmd_docs_create(client, args)

        self.assertEqual(
            result["post_create_page_write"],
            {
                "target": "auto-created default page",
                "body": {"content": "# Hello", "content_format": "text/md"},
            },
        )

    def test_dry_run_accepts_raw_space_id(self):
        client = FlexClient(dry_run=True)
        args = Namespace(space="111", name="Doc", content=None,
                         content_file=None, visibility=None)
        result = cmd_docs_create(client, args)

        self.assertTrue(result["dry_run"])
        self.assertEqual(result["body"]["parent"], {"id": "111", "type": 4})

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

    def test_create_help_mentions_space_name_or_id(self):
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="group")
        register_docs_parser(subparsers, argparse.RawDescriptionHelpFormatter)
        docs_parser = subparsers.choices["docs"]
        create_parser = docs_parser._subparsers._group_actions[0].choices["create"]
        help_text = create_parser.format_help()

        self.assertIn("SPACE_NAME_OR_ID", help_text)
        self.assertIn('clickup --dry-run docs create --space 12345 --name "My doc"', help_text)


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

    def test_replace_empty_content_clear_inline(self):
        client = FlexClient(dry_run=True)
        args = Namespace(doc_id="d1", page_id="p1", content="",
                         content_file=None, name=None, append=False)
        result = cmd_docs_edit_page(client, args)
        self.assertTrue(result["dry_run"])
        self.assertEqual(result["body"]["content"], "")
        self.assertEqual(result["body"]["content_format"], "text/md")

    def test_replace_empty_content_clear_from_file(self):
        client = FlexClient(dry_run=True)
        with tempfile.NamedTemporaryFile("w", encoding="utf-8") as handle:
            args = Namespace(doc_id="d1", page_id="p1", content=None,
                             content_file=handle.name, name=None, append=False)
            result = cmd_docs_edit_page(client, args)

        self.assertTrue(result["dry_run"])
        self.assertEqual(result["body"]["content"], "")
        self.assertEqual(result["body"]["content_format"], "text/md")


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
