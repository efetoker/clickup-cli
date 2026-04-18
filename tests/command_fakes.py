"""Shared fake clients for command handler tests."""

from types import SimpleNamespace


class FlexClient:
    """Flexible fake client for testing command handlers."""

    def __init__(self, dry_run=False, responses=None, runtime=None):
        self.dry_run = dry_run
        self.runtime = runtime or SimpleNamespace(
            workspace_id="test_workspace",
            user_id="",
            spaces={
                "testspace": {"space_id": "111", "list_id": "222"},
                "dev": {"space_id": "333", "list_id": "444"},
                "staging": {"space_id": "555", "list_id": "666"},
            },
        )
        self._responses = responses or {}
        self._default_response = {"ok": True}
        self.calls = []

    def _handle(self, method, path, **kwargs):
        self.calls.append({"method": method, "path": path, **kwargs})
        if self.dry_run and not kwargs.get("allow_dry_run"):
            return {"dry_run": True, "method": method, "url": path, "kwargs": kwargs}
        for key, resp in self._responses.items():
            if key in path:
                if isinstance(resp, list):
                    return resp.pop(0)
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

    def delete_v2(self, path, params=None):
        return self._handle("DELETE", path, params=params)

    def get_v3(self, path, params=None, allow_dry_run=False):
        return self._handle("GET_V3", path, params=params, allow_dry_run=allow_dry_run)

    def post_v3(self, path, data=None):
        return self._handle("POST_V3", path, data=data)

    def put_v3(self, path, data=None):
        return self._handle("PUT_V3", path, data=data)

    def patch_v3(self, path, data=None):
        return self._handle("PATCH_V3", path, data=data)
