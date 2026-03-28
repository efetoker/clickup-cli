"""ClickUp API client with rate limiting and dry-run support."""

import sys
import time

import requests

from .helpers import error


class ClickUpClient:
    BASE_V2 = "https://api.clickup.com/api/v2"
    BASE_V3 = "https://api.clickup.com/api/v3"

    def __init__(self, token, dry_run=False):
        self.token = token
        self.dry_run = dry_run
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": token,
                "Content-Type": "application/json",
            }
        )

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

        resp = None
        try:
            resp = self.session.request(method, url, **kwargs)
        except requests.ConnectionError:
            error("Couldn't reach ClickUp API — check your network connection")

        if resp is None:
            error("No response received from ClickUp API")

        response = resp

        if response.status_code == 429:
            reset = response.headers.get("X-RateLimit-Reset")
            if reset:
                wait = max(0, int(reset) - int(time.time())) + 1
                print(f"Rate limited (429), waiting {wait}s...", file=sys.stderr)
                time.sleep(wait)
                try:
                    response = self.session.request(method, url, **kwargs)
                except requests.ConnectionError:
                    error("Couldn't reach ClickUp API — check your network connection")
                if response is None:
                    error("No response received from ClickUp API")

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
