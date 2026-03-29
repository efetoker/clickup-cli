"""Tests for helpers.py — output, error, read_content, resolve_space_id, fetch_all_comments."""

import io
import json
import os
import sys
import tempfile
import unittest
from argparse import Namespace
from unittest.mock import MagicMock

from clickup_cli.helpers import (
    error,
    fetch_all_comments,
    output,
    read_content,
    resolve_space_id,
)


class OutputTests(unittest.TestCase):
    """Tests for the output() JSON printer."""

    def test_output_compact_json(self):
        captured = io.StringIO()
        sys.stdout = captured
        try:
            output({"key": "value", "num": 42})
        finally:
            sys.stdout = sys.__stdout__
        result = json.loads(captured.getvalue())
        self.assertEqual(result, {"key": "value", "num": 42})
        # Compact = single line, no indentation
        self.assertNotIn("\n  ", captured.getvalue())

    def test_output_pretty_json(self):
        captured = io.StringIO()
        sys.stdout = captured
        try:
            output({"key": "value"}, pretty=True)
        finally:
            sys.stdout = sys.__stdout__
        result = json.loads(captured.getvalue())
        self.assertEqual(result, {"key": "value"})
        # Pretty = indented
        self.assertIn("\n  ", captured.getvalue())

    def test_output_unicode_not_escaped(self):
        captured = io.StringIO()
        sys.stdout = captured
        try:
            output({"name": "Türkçe"})
        finally:
            sys.stdout = sys.__stdout__
        self.assertIn("Türkçe", captured.getvalue())
        self.assertNotIn("\\u", captured.getvalue())

    def test_output_empty_dict(self):
        captured = io.StringIO()
        sys.stdout = captured
        try:
            output({})
        finally:
            sys.stdout = sys.__stdout__
        self.assertEqual(json.loads(captured.getvalue()), {})

    def test_output_list(self):
        captured = io.StringIO()
        sys.stdout = captured
        try:
            output([1, 2, 3])
        finally:
            sys.stdout = sys.__stdout__
        self.assertEqual(json.loads(captured.getvalue()), [1, 2, 3])


class ErrorTests(unittest.TestCase):
    """Tests for the error() function."""

    def test_error_exits_with_code_1(self):
        with self.assertRaises(SystemExit) as ctx:
            error("something broke")
        self.assertEqual(ctx.exception.code, 1)

    def test_error_prints_to_stderr(self):
        captured = io.StringIO()
        old_stderr = sys.stderr
        sys.stderr = captured
        try:
            with self.assertRaises(SystemExit):
                error("test message")
        finally:
            sys.stderr = old_stderr
        self.assertIn("Error: test message", captured.getvalue())


class ReadContentTests(unittest.TestCase):
    """Tests for read_content()."""

    def test_inline_string_returned(self):
        self.assertEqual(read_content("hello", None), "hello")

    def test_both_inline_and_file_errors(self):
        with self.assertRaises(SystemExit):
            read_content("inline", "/some/file")

    def test_both_none_returns_none(self):
        self.assertIsNone(read_content(None, None))

    def test_file_path_reads_content(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("# File content\nLine 2")
            tmp = f.name
        try:
            result = read_content(None, tmp)
            self.assertEqual(result, "# File content\nLine 2")
        finally:
            os.unlink(tmp)

    def test_file_not_found_errors(self):
        with self.assertRaises(SystemExit):
            read_content(None, "/nonexistent/file.md")

    def test_custom_flag_name_in_error(self):
        captured = io.StringIO()
        old_stderr = sys.stderr
        sys.stderr = captured
        try:
            with self.assertRaises(SystemExit):
                read_content("a", "b", flag_name="--desc")
        finally:
            sys.stderr = old_stderr
        self.assertIn("--desc", captured.getvalue())


class ResolveSpaceIdTests(unittest.TestCase):
    """Tests for resolve_space_id()."""

    def test_raw_numeric_id_passed_through(self):
        self.assertEqual(resolve_space_id("99999"), "99999")

    def test_config_name_resolved(self):
        # conftest sets up testspace -> space_id 111
        self.assertEqual(resolve_space_id("testspace"), "111")

    def test_config_name_personal(self):
        self.assertEqual(resolve_space_id("personal"), "333")

    def test_unknown_non_numeric_errors(self):
        with self.assertRaises(SystemExit):
            resolve_space_id("nonexistent_space")

    def test_unknown_non_numeric_shows_available(self):
        captured = io.StringIO()
        old_stderr = sys.stderr
        sys.stderr = captured
        try:
            with self.assertRaises(SystemExit):
                resolve_space_id("badname")
        finally:
            sys.stderr = old_stderr
        output_text = captured.getvalue()
        self.assertIn("Unknown space: badname", output_text)
        self.assertIn("Available:", output_text)


class FetchAllCommentsTests(unittest.TestCase):
    """Tests for fetch_all_comments() pagination."""

    def test_single_page_of_comments(self):
        client = MagicMock()
        # First call returns 2 comments, second call (pagination check) returns empty
        client.get_v2.side_effect = [
            {"comments": [
                {"id": "c1", "date": "1000"},
                {"id": "c2", "date": "2000"},
            ]},
            {"comments": []},
        ]
        result = fetch_all_comments(client, "task1")
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["id"], "c1")

    def test_empty_comments(self):
        client = MagicMock()
        client.get_v2.return_value = {"comments": []}
        result = fetch_all_comments(client, "task1")
        self.assertEqual(result, [])

    def test_multi_page_comments(self):
        page1 = {
            "comments": [
                {"id": "c1", "date": "1000"},
                {"id": "c2", "date": "2000"},
            ]
        }
        page2 = {
            "comments": [
                {"id": "c3", "date": "3000"},
            ]
        }
        page3 = {"comments": []}

        client = MagicMock()
        client.get_v2.side_effect = [page1, page2, page3]

        result = fetch_all_comments(client, "task1")
        self.assertEqual(len(result), 3)
        self.assertEqual([c["id"] for c in result], ["c1", "c2", "c3"])

    def test_pagination_uses_last_comment_params(self):
        page1 = {"comments": [{"id": "c1", "date": "1000"}]}
        page2 = {"comments": []}

        client = MagicMock()
        client.get_v2.side_effect = [page1, page2]

        fetch_all_comments(client, "task1")

        # Second call should use start/start_id params
        second_call = client.get_v2.call_args_list[1]
        self.assertEqual(second_call[0][0], "/task/task1/comment")
        self.assertEqual(second_call[1]["params"]["start"], "1000")
        self.assertEqual(second_call[1]["params"]["start_id"], "c1")


if __name__ == "__main__":
    unittest.main()
