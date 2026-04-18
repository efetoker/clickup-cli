"""Regression coverage for the tasks facade split."""

import unittest

from clickup_cli import cli


class TasksFacadeTests(unittest.TestCase):
    def test_facade_re_exports_read_entrypoints_from_internal_modules(self):
        from clickup_cli.commands import tasks
        from clickup_cli.commands.tasks_internal import parser, read

        self.assertIs(tasks.register_parser, parser.register_parser)
        self.assertIs(tasks.cmd_tasks_list, read.cmd_tasks_list)
        self.assertIs(tasks.cmd_tasks_get, read.cmd_tasks_get)
        self.assertIs(tasks.cmd_tasks_search, read.cmd_tasks_search)

    def test_facade_re_exports_write_entrypoints_from_internal_modules(self):
        from clickup_cli.commands import tasks
        from clickup_cli.commands.tasks_internal import write

        self.assertIs(tasks.cmd_tasks_create, write.cmd_tasks_create)
        self.assertIs(tasks.cmd_tasks_update, write.cmd_tasks_update)
        self.assertIs(tasks.cmd_tasks_delete, write.cmd_tasks_delete)
        self.assertIs(tasks.cmd_tasks_move, write.cmd_tasks_move)
        self.assertIs(tasks.cmd_tasks_merge, write.cmd_tasks_merge)
        self.assertIs(tasks.cmd_tasks_depend, write.cmd_tasks_depend)

    def test_root_parser_still_registers_tasks_group(self):
        parser = cli.build_parser()

        self.assertIn("tasks", parser._subparsers._group_actions[0].choices)


if __name__ == "__main__":
    unittest.main()
