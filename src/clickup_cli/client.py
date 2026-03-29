"""ClickUp API client with rate limiting, dry-run, and debug support."""

import json as _json
import sys
import time

import requests

from .helpers import error


class ClickUpClient:
    BASE_V2 = "https://api.clickup.com/api/v2"
    BASE_V3 = "https://api.clickup.com/api/v3"

    def __init__(self, token, dry_run=False, debug=False):
        self.token = token
        self.dry_run = dry_run
        self.debug = debug
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": token,
                "Content-Type": "application/json",
            }
        )

    def _log(self, msg):
        """Print debug message to stderr."""
        if self.debug:
            print(f"[debug] {msg}", file=sys.stderr)

    def _check_rate_limit(self, response):
        """Sleep proactively if rate limit is running low."""
        remaining = response.headers.get("X-RateLimit-Remaining")
        reset = response.headers.get("X-RateLimit-Reset")
        if remaining is not None and int(remaining) < 10 and reset:
            wait = max(0, int(reset) - int(time.time())) + 1
            print(
                f"Rate limit low ({remaining} remaining), waiting {wait}s...",
                file=sys.stderr,
            )
            time.sleep(wait)

    def _request(self, method, url, allow_dry_run=False, **kwargs):
        """Make an HTTP request with rate limit handling and error reporting."""
        if self.dry_run and not allow_dry_run:
            return {"dry_run": True, "method": method, "url": url, "kwargs": kwargs}

        self._log(f"{method} {url}")
        if kwargs.get("params"):
            self._log(f"  params: {kwargs['params']}")
        if kwargs.get("json"):
            self._log(f"  body: {_json.dumps(kwargs['json'], ensure_ascii=False)}")

        def _do_request():
            try:
                return self.session.request(method, url, **kwargs)
            except requests.ConnectionError:
                error("Couldn't reach ClickUp API — check your network connection")

        response = _do_request()
        self._log(f"  → {response.status_code} ({len(response.text)} bytes)")

        if response.status_code == 429:
            reset = response.headers.get("X-RateLimit-Reset")
            if reset:
                wait = max(0, int(reset) - int(time.time())) + 1
                print(f"Rate limited (429), waiting {wait}s...", file=sys.stderr)
                time.sleep(wait)
                response = _do_request()

        if response.status_code == 401:
            error(
                "Authentication failed — check your API token"
            )

        if not response.ok:
            body = response.text
            try:
                body = response.json()
            except ValueError:
                pass
            error(f"API error {response.status_code} on {method} {url}: {body}")

        self._check_rate_limit(response)

        if response.status_code == 204 or not response.text:
            return {}
        return response.json()

    def get_v2(self, path, params=None, allow_dry_run=False):
        return self._request(
            "GET", f"{self.BASE_V2}{path}", params=params, allow_dry_run=allow_dry_run
        )

    def post_v2(self, path, data=None):
        return self._request("POST", f"{self.BASE_V2}{path}", json=data)

    def put_v2(self, path, data=None):
        return self._request("PUT", f"{self.BASE_V2}{path}", json=data)

    def delete_v2(self, path):
        return self._request("DELETE", f"{self.BASE_V2}{path}")

    def get_v3(self, path, params=None, allow_dry_run=False):
        return self._request(
            "GET", f"{self.BASE_V3}{path}", params=params, allow_dry_run=allow_dry_run
        )

    def post_v3(self, path, data=None):
        return self._request("POST", f"{self.BASE_V3}{path}", json=data)

    def put_v3(self, path, data=None):
        return self._request("PUT", f"{self.BASE_V3}{path}", json=data)
