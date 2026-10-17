"""Tag mutation validation and bulk failure regression coverage."""

import json
from argparse import Namespace

import pytest
from command_fakes import FlexClient

from clickup_cli.cli import build_parser, dispatch
from clickup_cli.commands.tags import cmd_tags_edit, cmd_tags_migrate
from clickup_cli.commands.tasks_internal.write import _tasks_bulk_tags
from clickup_cli.helpers import resolve_id_args


def parsed(argv):
    result = build_parser().parse_args(argv)
    resolve_id_args(result)
    return result


@pytest.mark.parametrize("continue_on_error", [False, True])
def test_bulk_tags_catches_api_system_exit(tmp_path, capsys, continue_on_error):
    plan = tmp_path / "plan.json"
    plan.write_text(json.dumps({"tasks": [
        {"task_id": "first", "operations": [{"action": "add", "tag": "known"}]},
        {"task_id": "second", "operations": [{"action": "add", "tag": "known"}]},
    ]}))

    def fail_first(path, kwargs):
        from clickup_cli.helpers import error
        if "/first/" in path:
            error("API error 400: synthetic failure")
        return {}

    fake = FlexClient(responses={"/tag/": fail_first})
    result = _tasks_bulk_tags(fake, Namespace(plan_file=str(plan), continue_on_error=continue_on_error))
    assert result["status"] == "partial_failure"
    assert result["failed"][0]["task_id"] == "first"
    assert "synthetic failure" in result["failed"][0]["error"]
    assert result["remaining"] == ([] if continue_on_error else ["first", "second"])
    assert result["resume_from"] == (None if continue_on_error else "first")
    assert result["completed"] == (["second"] if continue_on_error else [])
    assert "API error 400" in capsys.readouterr().err


@pytest.mark.parametrize("entry", ["create", "update", "add", "bulk"])
@pytest.mark.parametrize("dry_run", [False, True])
@pytest.mark.parametrize("known", [False, True])
def test_strict_tags_every_addition_entrypoint(tmp_path, entry, dry_run, known):
    plan = tmp_path / "plan.json"
    plan.write_text(json.dumps({"tasks": [{"task_id": "task-example", "operations": [
        {"action": "add", "tag": "known" if known else "unknown"}]}]}))
    tag = "known" if known else "unknown"
    commands = {
        "create": ["tasks", "create", "--space", "testspace", "--name", "Example", "--tag", tag],
        "update": ["tasks", "update", "task-example", "--name", "Changed", "--add-tag", tag],
        "add": ["tags", "add", "task-example", "--tag", tag],
        "bulk": ["tasks", "bulk", "tags", "--plan", str(plan)],
    }
    fake = FlexClient(dry_run=dry_run, responses={
        "/space/111/tag": {"tags": [{"name": "known"}]},
        "/list/222/task": {"id": "task-created"},
        "/list/222": {"space": {"id": "111"}},
        "/task/task-example": {"id": "task-example", "space": {"id": "111"}},
    })
    command = parsed(commands[entry] + ["--strict-tags"])
    if known:
        dispatch(fake, command)
    else:
        with pytest.raises(SystemExit):
            dispatch(fake, command)
    if dry_run or not known:
        assert all(call["method"] == "GET" for call in fake.calls)
    else:
        assert any(call["method"] == "POST" for call in fake.calls)


def test_config_default_and_explicit_override():
    from clickup_cli.runtime import RuntimeContext

    fake = FlexClient(dry_run=True, runtime=RuntimeContext(workspace_id="workspace-example", strict_tags=True),
                      responses={"/task/task-example": {"space": {"id": "111"}},
                                 "/space/111/tag": {"tags": []}})
    argv = ["tags", "add", "task-example", "--tag", "unknown"]
    with pytest.raises(SystemExit):
        dispatch(fake, parsed(argv))
    fake.calls.clear()
    assert dispatch(fake, parsed(argv + ["--no-strict-tags"]))["dry_run"]
    assert fake.calls == []


def test_strict_create_checks_actual_list_space_not_alias():
    fake = FlexClient(responses={"/list/list-other": {"space": {"id": "other-space"}},
                                 "/space/other-space/tag": {"tags": []}})
    with pytest.raises(SystemExit):
        dispatch(fake, parsed(["tasks", "create", "--space", "testspace", "--list", "list-other",
                               "--name", "Example", "--tag", "unknown", "--strict-tags"]))
    assert all(call["method"] == "GET" for call in fake.calls)
    assert fake.calls[-1]["path"] == "/space/other-space/tag"


def test_strict_bulk_validates_all_tasks_before_any_mutation(tmp_path):
    plan = tmp_path / "plan.json"
    plan.write_text(json.dumps({"tasks": [
        {"task_id": "first", "operations": [{"action": "add", "tag": "known"}]},
        {"task_id": "second", "operations": [{"action": "add", "tag": "unknown"}]},
    ]}))
    fake = FlexClient(responses={"/task/first": {"space": {"id": "111"}},
                                 "/task/second": {"list": {"id": "list-other"}},
                                 "/list/list-other": {"space": {"id": "333"}},
                                 "/space/111/tag": {"tags": [{"name": "known"}]},
                                 "/space/333/tag": {"tags": []}})
    with pytest.raises(SystemExit):
        dispatch(fake, parsed(["tasks", "bulk", "tags", "--plan", str(plan), "--strict-tags"]))
    assert all(call["method"] == "GET" for call in fake.calls)


def edit_args(**extra):
    values = {"space": "testspace", "tag": "source", "name": None, "fg_color": None, "bg_color": None}
    values.update(extra)
    return Namespace(**values)


def test_edit_fills_missing_values_and_encodes_source():
    fake = FlexClient(dry_run=True, responses={"/space/111/tag": {"tags": [
        {"name": "source / path", "tag_fg": "#ffffff", "tag_bg": "#000000"}]}})
    result = cmd_tags_edit(fake, edit_args(tag="SOURCE / PATH", name="Target", fg_color="#123"))
    assert result["body"] == {"tag": {"name": "target", "tag_fg": "#112233", "tag_bg": "#000000"}}
    assert all(call["method"] == "GET" for call in fake.calls)


@pytest.mark.parametrize("options", [{}, {"fg_color": "red"}, {"name": ""}])
def test_edit_invalid_changes_make_no_requests(options):
    fake = FlexClient()
    with pytest.raises(SystemExit):
        cmd_tags_edit(fake, edit_args(**options))
    assert fake.calls == []


@pytest.mark.parametrize("tags", [[], [{"name": "source"}, {"name": "target"}]])
def test_edit_missing_source_and_collision_do_not_mutate(tags):
    fake = FlexClient(responses={"/space/111/tag": {"tags": tags}})
    with pytest.raises(SystemExit):
        cmd_tags_edit(fake, edit_args(name="target"))
    assert all(call["method"] == "GET" for call in fake.calls)


def test_edit_live_verifies_result():
    fake = FlexClient(responses={"/space/111/tag": [
        {"tags": [{"name": "source / path", "tag_fg": "#ffffff", "tag_bg": "#000000"}]},
        {},
        {"tags": [{"name": "target", "tag_fg": "#ffffff", "tag_bg": "#000000"}]},
    ]})
    result = cmd_tags_edit(fake, edit_args(tag="source / path", name="target"))
    assert result["tag"]["name"] == "target"
    assert fake.calls[1]["method"] == "PUT"
    assert fake.calls[1]["path"] == "/space/111/tag/source%20%2F%20path"


def migration_args(tmp_path, mapping, **extra):
    path = tmp_path / "mapping.json"
    path.write_text(json.dumps(mapping))
    return Namespace(space="testspace", map_file=str(path), delete_old=extra.get("delete_old", False),
                     continue_on_error=extra.get("continue_on_error", False))


def migration_client(dry_run=False, tasks=None):
    inventory = [{"name": name} for name in ["source-a", "source-b", "drop", "target"]]
    tasks = tasks if tasks is not None else [
        {"id": "a", "name": "Merge", "tags": [{"name": "source-a"}, {"name": "source-b"}]},
        {"id": "b", "name": "Already target", "tags": [{"name": "source-a"}, {"name": "target"}]},
        {"id": "c", "name": "Drop", "archived": True, "tags": [{"name": "drop"}]},
    ]

    def task_page(path, kwargs):
        archived = kwargs["params"]["archived"] == "true"
        return {"tasks": [t for t in tasks if bool(t.get("archived")) == archived], "last_page": True}

    def change_tag(path, kwargs):
        _, _, task_id, _, tag = path.split("/")
        task = next(t for t in tasks if t["id"] == task_id)
        if "data" in kwargs:
            task["tags"].append({"name": tag})
        else:
            task["tags"] = [t for t in task["tags"] if t["name"] != tag]
        return {}

    return FlexClient(dry_run=dry_run, responses={
        "/space/111/tag": {"tags": inventory},
        "/space/111/list": {"lists": [{"id": "222"}]},
        "/space/111/folder": {"folders": []},
        "/space/111": {"id": "111", "archived": False},
        "/list/222/task": task_page,
        "/task/": change_tag,
    })


def test_migration_merge_drop_and_deletions_dry_run(tmp_path):
    fake = migration_client(dry_run=True)
    result = cmd_tags_migrate(fake, migration_args(tmp_path, {"source-a": ["target"], "source-b": ["target"], "drop": []}, delete_old=True))
    assert result["totals"] == {"tasks": 3, "add": 1, "remove": 4, "space_tag_deletions": 3}
    assert result["plan"]["tasks"][0]["operations"] == [
        {"action": "add", "tag": "target"}, {"action": "remove", "tag": "source-a"},
        {"action": "remove", "tag": "source-b"}]
    assert result["results_complete"]
    assert all(call["method"] == "GET" for call in fake.calls)
    pages = [call for call in fake.calls if call["path"].endswith("/task")]
    assert all(call["params"]["include_closed"] == "true" and call["params"]["subtasks"] == "true" for call in pages)
    assert {call["params"]["archived"] for call in pages} == {"true", "false"}


def test_migration_live_and_rerun_noop(tmp_path):
    fake = migration_client()
    args = migration_args(tmp_path, {"source-a": ["target"], "source-b": ["target"], "drop": []})
    result = cmd_tags_migrate(fake, args)
    assert result["completed"] == ["a", "b", "c"]
    assert cmd_tags_migrate(fake, args)["totals"]["tasks"] == 0


def test_migration_deletes_sources_only_after_fresh_scans(tmp_path):
    fake = migration_client()
    result = cmd_tags_migrate(fake, migration_args(tmp_path, {"source-a": ["target"], "source-b": ["target"], "drop": []}, delete_old=True))
    assert result["deleted_space_tags"] == ["source-a", "source-b", "drop"]
    assert result["pending_space_tag_deletions"] == []
    assert result["status"] == "ok"
    assert len([c for c in fake.calls if c["path"] == "/list/222/task"]) == 8


@pytest.mark.parametrize("mapping", [{}, [], {"source-a": "target"}, {"source-a": [3]},
                                    {"source-a": ["source-a"]}, {"source-a": ["source-b"], "source-b": []}])
def test_malformed_maps_make_no_requests(tmp_path, mapping):
    fake = migration_client()
    with pytest.raises(SystemExit):
        cmd_tags_migrate(fake, migration_args(tmp_path, mapping))
    assert fake.calls == []


def test_missing_migration_tags_block_mutations(tmp_path):
    fake = migration_client()
    with pytest.raises(SystemExit):
        cmd_tags_migrate(fake, migration_args(tmp_path, {"source-a": ["unknown"]}))
    assert all(c["method"] == "GET" for c in fake.calls)


def test_incomplete_migration_scan_blocks_mutations(tmp_path):
    fake = migration_client()
    fake._responses["/list/222/task"] = {"tasks": []}
    with pytest.raises(SystemExit):
        cmd_tags_migrate(fake, migration_args(tmp_path, {"source-a": []}))
    assert all(c["method"] == "GET" for c in fake.calls)


def test_migration_task_failure_prevents_space_deletions(tmp_path):
    fake = migration_client()

    def fail(path, kwargs):
        raise SystemExit(1)

    fake._responses["/task/"] = fail
    result = cmd_tags_migrate(fake, migration_args(tmp_path, {"source-a": ["target"]}, delete_old=True))
    assert result["status"] == "partial_failure"
    assert result["pending_space_tag_deletions"] == ["source-a"]
    assert not any(c["method"] == "DELETE" and "/space/" in c["path"] for c in fake.calls)


@pytest.mark.parametrize("path,response", [
    ("/space/111/folder", {}),
    ("/space/111", {"id": "111", "archived": True}),
    ("/list/222/task", {"tasks": [{"id": "a"}], "last_page": True}),
    ("/list/222/task", {"tasks": [{"id": "a", "tags": []}], "last_page": False}),
])
def test_migration_rejects_incomplete_hierarchy_and_repeated_pages(tmp_path, path, response):
    fake = migration_client()
    fake._responses[path] = response
    with pytest.raises(SystemExit):
        cmd_tags_migrate(fake, migration_args(tmp_path, {"source-a": []}))
    assert all(c["method"] == "GET" for c in fake.calls)


def test_migration_fresh_usage_prevents_deletion(tmp_path):
    fake = migration_client()
    fake._responses["/task/"] = {}
    result = cmd_tags_migrate(fake, migration_args(tmp_path, {"source-a": []}, delete_old=True))
    assert result["status"] == "partial_failure"
    assert result["pending_space_tag_deletions"] == ["source-a"]
    assert result["deleted_space_tags"] == []


def test_migration_continue_on_error_preserves_other_tasks(tmp_path):
    fake = migration_client()
    original = fake._responses["/task/"]

    def fail_one(path, kwargs):
        if "/task/a/" in path:
            raise RuntimeError("synthetic failure")
        return original(path, kwargs)

    fake._responses["/task/"] = fail_one
    result = cmd_tags_migrate(fake, migration_args(tmp_path, {"source-a": []}, delete_old=True,
                                                  continue_on_error=True))
    assert result["completed"] == ["b"]
    assert result["failed"][0]["task_id"] == "a"
    assert result["deleted_space_tags"] == []


def test_duplicate_normalized_map_sources_fail_without_requests(tmp_path):
    path = tmp_path / "mapping.json"
    path.write_text('{"Source": [], "source": []}')
    fake = migration_client()
    with pytest.raises(SystemExit):
        cmd_tags_migrate(fake, Namespace(space="testspace", map_file=str(path)))
    assert fake.calls == []


def test_migration_fresh_scan_failure_retains_completed_result(tmp_path, monkeypatch):
    from clickup_cli.commands import tags

    fake = migration_client()
    real_scan = tags._scan_space_tasks
    calls = []

    def fail_fresh(*args, **kwargs):
        calls.append(True)
        if len(calls) > 1:
            from clickup_cli.helpers import error
            error("synthetic verification failure")
        return real_scan(*args, **kwargs)

    monkeypatch.setattr(tags, "_scan_space_tasks", fail_fresh)
    result = cmd_tags_migrate(fake, migration_args(tmp_path, {"source-a": ["target"]}, delete_old=True))
    assert result["status"] == "partial_failure"
    assert result["completed"] == ["a", "b"]
    assert "synthetic verification failure" in result["failed"][0]["error"]
    assert result["pending_space_tag_deletions"] == ["source-a"]
    assert result["deleted_space_tags"] == []


def test_migration_scans_active_lists_inside_archived_folders(tmp_path):
    fake = migration_client(dry_run=True, tasks=[])
    fake._responses["/space/111/folder"] = lambda path, kw: {
        "folders": [{"id": "archived-folder"}] if (kw.get("params") or {}).get("archived") == "true" else []}
    fake._responses["/folder/archived-folder/list"] = lambda path, kw: {
        "lists": [{"id": "active-child"}] if kw["params"]["archived"] == "false" else []}
    fake._responses["/list/active-child/task"] = {
        "tasks": [{"id": "nested", "name": "Example", "tags": [{"name": "source-a"}]}],
        "last_page": True}
    result = cmd_tags_migrate(fake, migration_args(tmp_path, {"source-a": []}))
    assert [task["task_id"] for task in result["plan"]["tasks"]] == ["nested"]
    assert result["lists_scanned"] == 2
