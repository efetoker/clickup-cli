"""Regression coverage for command manifests."""

import os
import subprocess
import unittest


class CommandManifestTests(unittest.TestCase):
    def test_non_init_modules_expose_manifests(self):
        from clickup_cli.commands import COMMAND_MANIFESTS

        groups = {manifest["group"] for manifest in COMMAND_MANIFESTS}
        self.assertEqual(
            groups,
            {
                "tasks",
                "comments",
                "docs",
                "fields",
                "folders",
                "lists",
                "spaces",
                "tags",
                "task-types",
                "team",
            },
        )

        for manifest in COMMAND_MANIFESTS:
            with self.subTest(group=manifest["group"]):
                self.assertIn("register_parser", manifest)
                self.assertTrue(callable(manifest["register_parser"]))
                self.assertIn("handlers", manifest)
                self.assertTrue(manifest["handlers"])

    def test_handlers_are_derived_from_manifests(self):
        from clickup_cli.commands import COMMAND_MANIFESTS, HANDLERS

        derived = {}
        for manifest in COMMAND_MANIFESTS:
            for command, handler in manifest["handlers"].items():
                derived[f"{manifest['group']}_{command}"] = handler

        self.assertEqual(HANDLERS, derived)
        self.assertIn("docs_get-page", HANDLERS)
        self.assertIn("docs_edit-page", HANDLERS)
        self.assertIn("docs_create-page", HANDLERS)
        self.assertIn("fields_list", HANDLERS)
        self.assertIn("task-types_list", HANDLERS)

    def test_validate_cli_output_checks_manifest_groups(self):
        script_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "scripts",
            "validate-cli-output.sh",
        )

        result = subprocess.run(
            ["bash", script_path],
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Checking: clickup fields --help", result.stdout)
        self.assertIn("Checking: clickup task-types --help", result.stdout)


if __name__ == "__main__":
    unittest.main()
