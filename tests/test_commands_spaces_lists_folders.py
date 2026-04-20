"""Handler tests for spaces, lists, and folders commands."""

import unittest
from argparse import Namespace
from types import SimpleNamespace

from clickup_cli.commands.folders import (
    cmd_folders_create,
    cmd_folders_delete,
    cmd_folders_get,
    cmd_folders_list,
    cmd_folders_privacy,
    cmd_folders_update,
)
from clickup_cli.commands.lists import (
    cmd_lists_create,
    cmd_lists_delete,
    cmd_lists_get,
    cmd_lists_list,
    cmd_lists_privacy,
    cmd_lists_update,
)
from clickup_cli.commands.spaces import (
    cmd_spaces_create,
    cmd_spaces_delete,
    cmd_spaces_get,
    cmd_spaces_list,
    cmd_spaces_privacy,
    cmd_spaces_statuses,
    cmd_spaces_update,
)

from command_fakes import FlexClient

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


class FoldersPrivacyTests(unittest.TestCase):

    def test_privacy_cases(self):
        cases = [
            (
                "folder",
                cmd_folders_privacy,
                Namespace(folder_id="f1", private=True, public=False),
                "/workspaces/test_workspace/folder/f1/acls",
                "f1",
                True,
            ),
            (
                "list",
                cmd_lists_privacy,
                Namespace(list_id="l1", private=True, public=False),
                "/workspaces/test_workspace/list/l1/acls",
                "l1",
                True,
            ),
            (
                "space",
                cmd_spaces_privacy,
                Namespace(space="testspace", private=True, public=False),
                "/workspaces/test_workspace/space/111/acls",
                "111",
                True,
            ),
            (
                "folder-public",
                cmd_folders_privacy,
                Namespace(folder_id="f1", private=False, public=True),
                "/workspaces/test_workspace/folder/f1/acls",
                "f1",
                False,
            ),
            (
                "list-public",
                cmd_lists_privacy,
                Namespace(list_id="l1", private=False, public=True),
                "/workspaces/test_workspace/list/l1/acls",
                "l1",
                False,
            ),
            (
                "space-public",
                cmd_spaces_privacy,
                Namespace(space="testspace", private=False, public=True),
                "/workspaces/test_workspace/space/111/acls",
                "111",
                False,
            ),
        ]

        for label, handler, args, path, object_id, private in cases:
            with self.subTest(case=label):
                client = FlexClient()
                result = handler(client, args)
                self.assertEqual(result["status"], "ok")
                self.assertEqual(result["action"], "set_privacy")
                self.assertEqual(result["object_id"], object_id)
                self.assertEqual(result["private"], private)
                call = client.calls[0]
                self.assertEqual(call["method"], "PATCH_V3")
                self.assertIn(path, call["path"])
                self.assertEqual(call["data"], {"private": private})

    def test_dry_run_cases(self):
        cases = [
            ("folder", cmd_folders_privacy, Namespace(folder_id="f1", private=True, public=False), "folder", "f1"),
            ("list", cmd_lists_privacy, Namespace(list_id="l1", private=True, public=False), "list", "l1"),
            ("space", cmd_spaces_privacy, Namespace(space="testspace", private=True, public=False), "space", "111"),
        ]

        for label, handler, args, object_type, object_id in cases:
            with self.subTest(case=label):
                client = FlexClient(dry_run=True)
                result = handler(client, args)
                self.assertTrue(result["dry_run"])
                self.assertEqual(result["action"], "set_privacy")
                self.assertEqual(result["object_type"], object_type)
                self.assertEqual(result["object_id"], object_id)
                self.assertEqual(result["body"], {"private": True})
                self.assertEqual(client.calls, [])

    def test_uses_runtime_workspace_id(self):
        cases = [
            (cmd_folders_privacy, Namespace(folder_id="f1", private=True, public=False), "/workspaces/runtime_ws/folder/f1/acls"),
            (cmd_lists_privacy, Namespace(list_id="l1", private=True, public=False), "/workspaces/runtime_ws/list/l1/acls"),
            (cmd_spaces_privacy, Namespace(space="999999", private=True, public=False), "/workspaces/runtime_ws/space/999999/acls"),
        ]

        for handler, args, path in cases:
            with self.subTest(path=path):
                client = FlexClient(
                    runtime=SimpleNamespace(workspace_id="runtime_ws", user_id="", spaces={})
                )
                handler(client, args)
                self.assertIn(path, client.calls[0]["path"])


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

    def test_list_uses_runtime_workspace_id(self):
        client = FlexClient(
            responses={"/space": {"spaces": [{"id": "s1"}]}},
            runtime=SimpleNamespace(workspace_id="runtime_ws", user_id="", spaces={}),
        )

        cmd_spaces_list(client, Namespace())

        self.assertIn("/team/runtime_ws/space", client.calls[0]["path"])


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


class SpacesCreateTests(unittest.TestCase):

    def test_create_dry_run(self):
        client = FlexClient(dry_run=True)
        args = Namespace(name="Platform", multiple_assignees=True)

        result = cmd_spaces_create(client, args)

        self.assertTrue(result["dry_run"])
        self.assertEqual(result["action"], "create_space")
        self.assertEqual(result["workspace_id"], "test_workspace")
        self.assertEqual(result["body"]["name"], "Platform")
        self.assertTrue(result["body"]["multiple_assignees"])
        self.assertIn("features", result["body"])
        self.assertEqual(client.calls, [])

    def test_create_live_request(self):
        client = FlexClient(responses={"/space": {"id": "s1", "name": "Platform"}})
        args = Namespace(name="Platform", multiple_assignees=False)

        result = cmd_spaces_create(client, args)

        self.assertEqual(result["id"], "s1")
        call = client.calls[0]
        self.assertEqual(call["method"], "POST")
        self.assertIn("/team/test_workspace/space", call["path"])
        self.assertEqual(call["data"]["name"], "Platform")
        self.assertFalse(call["data"]["multiple_assignees"])
        self.assertIn("features", call["data"])


class SpacesUpdateTests(unittest.TestCase):

    def test_update_dry_run_merges_required_fields(self):
        client = FlexClient(
            dry_run=True,
            responses={
                "/space/": {
                    "id": "111",
                    "name": "Platform",
                    "color": "#123456",
                    "private": True,
                    "admin_can_manage": False,
                    "multiple_assignees": False,
                    "features": {"due_dates": {"enabled": True}},
                }
            },
        )
        args = Namespace(space="testspace", name="Platform API", multiple_assignees=True)

        result = cmd_spaces_update(client, args)

        self.assertTrue(result["dry_run"])
        self.assertEqual(result["action"], "update_space")
        self.assertEqual(result["space_id"], "111")
        self.assertEqual(
            result["body"],
            {
                "name": "Platform API",
                "color": "#123456",
                "private": True,
                "admin_can_manage": False,
                "multiple_assignees": True,
                "features": {"due_dates": {"enabled": True}},
            },
        )
        self.assertEqual(len(client.calls), 1)
        self.assertEqual(client.calls[0]["method"], "GET")
        self.assertIn("/space/111", client.calls[0]["path"])

    def test_update_live_request_uses_resolved_space_id(self):
        client = FlexClient(
            responses={
                "/space/": [
                    {
                        "id": "333",
                        "name": "Dev",
                        "color": "#abcdef",
                        "private": False,
                        "admin_can_manage": True,
                        "multiple_assignees": True,
                        "features": {"sprints": {"enabled": False}},
                    },
                    {"id": "333", "name": "Platform API"},
                ]
            }
        )
        args = Namespace(space="dev", name="Platform API", multiple_assignees=None)

        result = cmd_spaces_update(client, args)

        self.assertEqual(result["id"], "333")
        self.assertEqual(client.calls[0]["method"], "GET")
        self.assertIn("/space/333", client.calls[0]["path"])
        self.assertEqual(client.calls[1]["method"], "PUT")
        self.assertIn("/space/333", client.calls[1]["path"])
        self.assertEqual(
            client.calls[1]["data"],
            {
                "name": "Platform API",
                "color": "#abcdef",
                "private": False,
                "admin_can_manage": True,
                "multiple_assignees": True,
                "features": {"sprints": {"enabled": False}},
            },
        )

    def test_update_noop_errors(self):
        client = FlexClient()
        args = Namespace(space="testspace", name=None, multiple_assignees=None)

        with self.assertRaises(SystemExit):
            cmd_spaces_update(client, args)


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


class SpacesPrivacyTests(unittest.TestCase):

    def test_raw_space_id(self):
        client = FlexClient()
        args = Namespace(space="999999", private=True, public=False)
        cmd_spaces_privacy(client, args)
        self.assertIn("/space/999999/acls", client.calls[0]["path"])


class SpacesDeleteTests(unittest.TestCase):

    def test_delete_dry_run(self):
        client = FlexClient(dry_run=True)
        args = Namespace(space="dev")

        result = cmd_spaces_delete(client, args)

        self.assertTrue(result["dry_run"])
        self.assertEqual(result["action"], "delete_space")
        self.assertEqual(result["space_id"], "333")
        self.assertEqual(client.calls, [])

    def test_delete_live_request_uses_resolved_space_id(self):
        client = FlexClient()
        args = Namespace(space="dev")

        result = cmd_spaces_delete(client, args)

        self.assertEqual(result, {"status": "ok", "action": "deleted", "space_id": "333"})
        self.assertEqual(client.calls[0]["method"], "DELETE")
        self.assertIn("/space/333", client.calls[0]["path"])
