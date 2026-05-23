"""Handler tests for metadata discovery commands."""

import argparse
import unittest
from argparse import Namespace

from command_fakes import FlexClient


class FieldsCommandTests(unittest.TestCase):
    def test_fields_list_uses_explicit_list_scope(self):
        from clickup_cli.commands.fields import cmd_fields_list

        client = FlexClient(
            responses={
                "/list/list-9/field": {
                    "fields": [{"id": "field-1", "name": "Priority"}]
                }
            }
        )

        result = cmd_fields_list(
            client,
            Namespace(space="testspace", list_id="list-9"),
        )

        self.assertEqual(result["count"], 1)
        self.assertEqual(result["fields"][0]["id"], "field-1")
        self.assertEqual(
            result["scope"],
            {
                "space": "testspace",
                "requested_list_id": "list-9",
                "resolved_list_id": "list-9",
            },
        )

    def test_fields_list_resolves_space_default_list_when_list_missing(self):
        from clickup_cli.commands.fields import cmd_fields_list

        client = FlexClient(
            responses={
                "/list/222/field": {
                    "fields": [{"id": "field-1", "name": "Priority"}]
                }
            }
        )

        result = cmd_fields_list(client, Namespace(space="testspace", list_id=None))

        self.assertEqual(result["scope"]["resolved_list_id"], "222")
        self.assertEqual(client.calls[0]["path"], "/list/222/field")


class TaskTypesCommandTests(unittest.TestCase):
    def test_task_types_list_reports_workspace_only_scope(self):
        from clickup_cli.commands.task_types import cmd_task_types_list

        client = FlexClient(
            responses={
                "/team/test_workspace/custom_item": {
                    "custom_items": [{"id": "type-1", "name": "Bug"}]
                }
            }
        )

        result = cmd_task_types_list(
            client,
            Namespace(space="testspace", list_id="list-9"),
        )

        self.assertEqual(result["count"], 1)
        self.assertTrue(result["available"])
        self.assertFalse(result["scope_applied"])
        self.assertEqual(result["source"], "workspace_custom_item_types")
        self.assertEqual(
            result["scope"],
            {
                "space": "testspace",
                "requested_list_id": "list-9",
                "resolved_list_id": "list-9",
            },
        )

    def test_task_types_list_reports_unavailable_when_workspace_has_none(self):
        from clickup_cli.commands.task_types import cmd_task_types_list

        client = FlexClient(
            responses={"/team/test_workspace/custom_item": {"custom_items": []}}
        )

        result = cmd_task_types_list(client, Namespace(space=None, list_id=None))

        self.assertEqual(result["task_types"], [])
        self.assertEqual(result["count"], 0)
        self.assertFalse(result["available"])
        self.assertFalse(result["scope_applied"])
        self.assertEqual(result["reason"], "workspace_has_no_custom_item_types")


class MetadataParserTests(unittest.TestCase):
    def test_metadata_groups_register_public_parsers(self):
        from clickup_cli.commands.fields import register_parser as register_fields_parser
        from clickup_cli.commands.task_types import (
            register_parser as register_task_types_parser,
        )

        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="group")

        register_fields_parser(subparsers, argparse.RawDescriptionHelpFormatter)
        register_task_types_parser(subparsers, argparse.RawDescriptionHelpFormatter)

        fields_args = parser.parse_args(["fields", "list", "--space", "testspace"])
        task_types_args = parser.parse_args(
            ["task-types", "list", "--list", "12345"]
        )

        self.assertEqual(fields_args.group, "fields")
        self.assertEqual(fields_args.command, "list")
        self.assertEqual(fields_args.space, "testspace")
        self.assertEqual(task_types_args.group, "task-types")
        self.assertEqual(task_types_args.command, "list")
        self.assertEqual(task_types_args.list_id, "12345")

    def test_fields_list_help_documents_scope_resolution(self):
        from clickup_cli.commands.fields import register_parser as register_fields_parser

        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="group")
        register_fields_parser(subparsers, argparse.RawDescriptionHelpFormatter)
        fields_parser = subparsers.choices["fields"]
        list_parser = fields_parser._subparsers._group_actions[0].choices["list"]

        help_text = " ".join(list_parser.format_help().split())

        self.assertIn("configured default list", help_text)
        self.assertIn("first folderless list", help_text)
        self.assertIn("scope", help_text)

    def test_task_types_list_help_documents_workspace_scope(self):
        from clickup_cli.commands.task_types import (
            register_parser as register_task_types_parser,
        )

        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="group")
        register_task_types_parser(subparsers, argparse.RawDescriptionHelpFormatter)
        task_types_parser = subparsers.choices["task-types"]
        list_parser = task_types_parser._subparsers._group_actions[0].choices["list"]

        help_text = " ".join(list_parser.format_help().split())

        self.assertIn("workspace-scoped", help_text)
        self.assertIn("scope_applied", help_text)
        self.assertIn("false", help_text)


if __name__ == "__main__":
    unittest.main()
