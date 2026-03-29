"""Tests for client.py — ClickUpClient request handling, rate limits, debug, v3 methods."""

import io
import sys
import time
import unittest
from unittest.mock import MagicMock, patch

from clickup_cli.client import ClickUpClient


class ClientSetupMixin:
    """Shared helpers for client tests."""

    def _make_client(self, **kwargs):
        return ClickUpClient("fake-token", **kwargs)

    def _mock_response(self, status_code=200, ok=True, text='{"ok": true}',
                       json_data=None, headers=None):
        resp = MagicMock()
        resp.status_code = status_code
        resp.ok = ok
        resp.text = text
        resp.headers = headers or {}
        resp.json.return_value = json_data or {"ok": True}
        return resp


class DebugLoggingTests(ClientSetupMixin, unittest.TestCase):
    """Tests for debug logging behavior."""

    def test_debug_false_no_output(self):
        client = self._make_client(debug=False)
        captured = io.StringIO()
        old_stderr = sys.stderr
        sys.stderr = captured
        try:
            client._log("test message")
        finally:
            sys.stderr = old_stderr
        self.assertEqual(captured.getvalue(), "")

    def test_debug_true_logs_to_stderr(self):
        client = self._make_client(debug=True)
        captured = io.StringIO()
        old_stderr = sys.stderr
        sys.stderr = captured
        try:
            client._log("test message")
        finally:
            sys.stderr = old_stderr
        self.assertIn("[debug] test message", captured.getvalue())

    def test_debug_logs_request_details(self):
        client = self._make_client(debug=True)
        resp = self._mock_response()
        client.session.request = MagicMock(return_value=resp)

        captured = io.StringIO()
        old_stderr = sys.stderr
        sys.stderr = captured
        try:
            client.get_v2("/test")
        finally:
            sys.stderr = old_stderr

        output = captured.getvalue()
        self.assertIn("GET", output)
        self.assertIn("/test", output)

    def test_debug_logs_params(self):
        client = self._make_client(debug=True)
        resp = self._mock_response()
        client.session.request = MagicMock(return_value=resp)

        captured = io.StringIO()
        old_stderr = sys.stderr
        sys.stderr = captured
        try:
            client.get_v2("/test", params={"page": "0"})
        finally:
            sys.stderr = old_stderr

        self.assertIn("params:", captured.getvalue())

    def test_debug_logs_body(self):
        client = self._make_client(debug=True)
        resp = self._mock_response()
        client.session.request = MagicMock(return_value=resp)

        captured = io.StringIO()
        old_stderr = sys.stderr
        sys.stderr = captured
        try:
            client.post_v2("/test", data={"name": "task"})
        finally:
            sys.stderr = old_stderr

        self.assertIn("body:", captured.getvalue())


class RateLimitTests(ClientSetupMixin, unittest.TestCase):
    """Tests for _check_rate_limit behavior."""

    @patch("time.sleep")
    def test_low_remaining_sleeps(self, mock_sleep):
        client = self._make_client()
        resp = MagicMock()
        resp.headers = {
            "X-RateLimit-Remaining": "5",
            "X-RateLimit-Reset": str(int(time.time()) + 2),
        }
        client._check_rate_limit(resp)
        mock_sleep.assert_called_once()

    @patch("time.sleep")
    def test_high_remaining_no_sleep(self, mock_sleep):
        client = self._make_client()
        resp = MagicMock()
        resp.headers = {
            "X-RateLimit-Remaining": "50",
            "X-RateLimit-Reset": str(int(time.time()) + 60),
        }
        client._check_rate_limit(resp)
        mock_sleep.assert_not_called()

    @patch("time.sleep")
    def test_no_remaining_header_no_sleep(self, mock_sleep):
        client = self._make_client()
        resp = MagicMock()
        resp.headers = {}
        client._check_rate_limit(resp)
        mock_sleep.assert_not_called()

    @patch("time.sleep")
    def test_low_remaining_but_no_reset_no_sleep(self, mock_sleep):
        client = self._make_client()
        resp = MagicMock()
        resp.headers = {"X-RateLimit-Remaining": "3"}
        client._check_rate_limit(resp)
        mock_sleep.assert_not_called()


class ErrorHandlingTests(ClientSetupMixin, unittest.TestCase):
    """Tests for various HTTP error handling paths."""

    def test_429_without_reset_header_falls_through_to_error(self):
        client = self._make_client()
        mock_429 = self._mock_response(429, ok=False, text="Rate limited")
        mock_429.headers = {}  # No X-RateLimit-Reset
        mock_429.json.side_effect = ValueError  # Not JSON
        client.session.request = MagicMock(return_value=mock_429)

        with self.assertRaises(SystemExit):
            client.get_v2("/test")

    def test_generic_non_ok_response_exits(self):
        client = self._make_client()
        resp = self._mock_response(
            500, ok=False, text="Server Error",
            json_data={"err": "internal"},
        )
        client.session.request = MagicMock(return_value=resp)

        with self.assertRaises(SystemExit):
            client.get_v2("/test")

    def test_non_ok_with_unparseable_body(self):
        client = self._make_client()
        resp = self._mock_response(502, ok=False, text="Bad Gateway")
        resp.json.side_effect = ValueError
        client.session.request = MagicMock(return_value=resp)

        with self.assertRaises(SystemExit):
            client.get_v2("/test")


class DryRunTests(ClientSetupMixin, unittest.TestCase):
    """Tests for dry-run behavior."""

    def test_dry_run_skips_mutating_request(self):
        client = self._make_client(dry_run=True)
        client.session.request = MagicMock()
        result = client.post_v2("/test", data={"name": "x"})
        client.session.request.assert_not_called()
        self.assertTrue(result["dry_run"])

    def test_dry_run_get_v2_with_allow_dry_run_makes_request(self):
        client = self._make_client(dry_run=True)
        resp = self._mock_response(json_data={"id": "123"})
        client.session.request = MagicMock(return_value=resp)

        result = client.get_v2("/test", allow_dry_run=True)
        client.session.request.assert_called_once()
        self.assertEqual(result["id"], "123")

    def test_dry_run_get_v2_without_allow_returns_preview(self):
        client = self._make_client(dry_run=True)
        client.session.request = MagicMock()

        result = client.get_v2("/test")
        client.session.request.assert_not_called()
        self.assertTrue(result["dry_run"])


class V3MethodTests(ClientSetupMixin, unittest.TestCase):
    """Tests for v3 API methods."""

    def test_get_v3_calls_correct_base(self):
        client = self._make_client()
        resp = self._mock_response(json_data={"docs": []})
        client.session.request = MagicMock(return_value=resp)

        result = client.get_v3("/workspaces/123/docs")
        call_args = client.session.request.call_args
        self.assertIn("v3", call_args[0][1])
        self.assertEqual(result, {"docs": []})

    def test_post_v3(self):
        client = self._make_client()
        resp = self._mock_response(json_data={"id": "doc1"})
        client.session.request = MagicMock(return_value=resp)

        result = client.post_v3("/workspaces/123/docs", data={"name": "Doc"})
        self.assertEqual(result["id"], "doc1")
        call_args = client.session.request.call_args
        self.assertEqual(call_args[0][0], "POST")
        self.assertIn("v3", call_args[0][1])

    def test_put_v3(self):
        client = self._make_client()
        resp = self._mock_response(json_data={"updated": True})
        client.session.request = MagicMock(return_value=resp)

        result = client.put_v3("/workspaces/123/docs/1/pages/2", data={"content": "hi"})
        self.assertEqual(result["updated"], True)
        call_args = client.session.request.call_args
        self.assertEqual(call_args[0][0], "PUT")

    def test_get_v3_with_allow_dry_run(self):
        client = self._make_client(dry_run=True)
        resp = self._mock_response(json_data={"content": "page"})
        client.session.request = MagicMock(return_value=resp)

        result = client.get_v3("/test", allow_dry_run=True)
        client.session.request.assert_called_once()
        self.assertEqual(result["content"], "page")

    def test_v3_dry_run_post_returns_preview(self):
        client = self._make_client(dry_run=True)
        client.session.request = MagicMock()

        result = client.post_v3("/test", data={"name": "Doc"})
        client.session.request.assert_not_called()
        self.assertTrue(result["dry_run"])
        self.assertEqual(result["method"], "POST")

    def test_v3_dry_run_put_returns_preview(self):
        client = self._make_client(dry_run=True)
        client.session.request = MagicMock()

        result = client.put_v3("/test", data={"content": "hi"})
        client.session.request.assert_not_called()
        self.assertTrue(result["dry_run"])
        self.assertEqual(result["method"], "PUT")


class ResponseParsingTests(ClientSetupMixin, unittest.TestCase):
    """Tests for response body parsing edge cases."""

    def test_204_returns_empty_dict(self):
        client = self._make_client()
        resp = self._mock_response(204, ok=True, text="")
        client.session.request = MagicMock(return_value=resp)

        result = client.delete_v2("/test")
        self.assertEqual(result, {})

    def test_200_empty_body_returns_empty_dict(self):
        client = self._make_client()
        resp = self._mock_response(200, ok=True, text="")
        client.session.request = MagicMock(return_value=resp)

        result = client.get_v2("/test")
        self.assertEqual(result, {})


if __name__ == "__main__":
    unittest.main()
