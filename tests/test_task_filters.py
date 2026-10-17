"""Text matching, negative tag filters, and due-date boundaries."""

import time
from argparse import Namespace
from datetime import datetime

import pytest
from command_fakes import FlexClient

from clickup_cli.cli import build_parser
from clickup_cli.commands.tasks_internal.read import cmd_tasks_list, cmd_tasks_search
from clickup_cli.commands.tasks_internal.shared import _task_filter_params


def args(**overrides):
    values = {
        "query": "", "space": None, "list_id": "list-example", "folder_id": None,
        "include_closed": False, "include_archived": False, "subtasks": False, "status": None,
        "tags": None, "exclude_tags": None, "untagged": False, "due_before": None,
        "due_after": None, "overdue": False, "name_prefix": None, "custom_fields": None,
        "fields": None, "full": False, "all_pages": False, "limit": None,
    }
    values.update(overrides)
    return Namespace(**values)


def task(task_id, name="Example", tags=(), **extra):
    return {"id": task_id, "name": name, "tags": [{"name": t} for t in tags],
            "status": {"type": "open", "status": "open"}, **extra}


def client(tasks, **kwargs):
    return FlexClient(responses={"/task": {"tasks": tasks, "last_page": True}}, **kwargs)


def test_search_rejects_unrelated_api_results():
    result = cmd_tasks_search(client([task("a", "Unrelated title")]), args(query="needle phrase"))
    assert result["count"] == 0


def test_search_all_words_casefold_across_name_and_description():
    tasks = [task("a", "Ship RELEASE", description="Publish next package"),
             task("b", "Release notes", description=None),
             task("c", "Other", text_content="PUBLISH the release")]
    result = cmd_tasks_search(client(tasks), args(query="publish release", limit=1))
    assert [t["id"] for t in result["tasks"]] == ["a"]
    assert result["results_complete"] is True


def test_search_empty_query_and_explicit_prefix():
    result = cmd_tasks_search(client([task("a", "PROJ-7: Example"), task("b")]),
                              args(query="  ", name_prefix="PROJ-7"))
    assert [t["id"] for t in result["tasks"]] == ["a"]


@pytest.mark.parametrize("handler", [cmd_tasks_list, cmd_tasks_search])
def test_negative_filters_precede_limit(handler):
    tasks = [task("a", tags=["Hidden"]), task("b", tags=["keep"]), task("c")]
    result = handler(client(tasks), args(exclude_tags=["hidden"], limit=1))
    assert [t["id"] for t in result["tasks"]] == ["b"]
    result = handler(client(tasks), args(untagged=True, limit=1))
    assert [t["id"] for t in result["tasks"]] == ["c"]


@pytest.mark.parametrize("handler", [cmd_tasks_list, cmd_tasks_search])
def test_untagged_and_positive_tag_fail_before_requests(handler):
    fake = FlexClient()
    with pytest.raises(SystemExit):
        handler(fake, args(untagged=True, tags=["known"]))
    assert fake.calls == []


@pytest.mark.parametrize("handler", [cmd_tasks_list, cmd_tasks_search])
@pytest.mark.parametrize("all_pages,expected,complete", [(False, [], False), (True, ["c"], True)])
def test_negative_filters_preserve_scan_budget(handler, all_pages, expected, complete):
    fake = FlexClient(responses={"/task": [
        {"tasks": [task("a", tags=["skip"])], "last_page": False},
        {"tasks": [task("b", tags=["skip"])], "last_page": False},
        {"tasks": [task("c")], "last_page": True},
    ]})
    result = handler(fake, args(exclude_tags=["skip"], all_pages=all_pages, limit=1))
    assert [t["id"] for t in result["tasks"]] == expected
    assert result["results_complete"] is complete
    assert result["results_truncated"] is not complete
    assert result["pages_fetched"] == (3 if all_pages else 2)


@pytest.mark.parametrize("handler", [cmd_tasks_list, cmd_tasks_search])
def test_positive_and_negative_tags_combine(handler):
    fake = client([task("a", tags=["keep", "skip"]), task("b", tags=["keep"]), task("c")])
    result = handler(fake, args(tags=["keep"], exclude_tags=["skip"]))
    assert [t["id"] for t in result["tasks"]] == ["b"]


@pytest.mark.parametrize("command", ["list", "search"])
def test_parser_exposes_new_filters(command):
    argv = ["tasks", command] + (["query"] if command == "search" else [])
    parsed = build_parser().parse_args(argv + ["--untagged", "--exclude-tag", "skip",
                                               "--due-before", "2026-10-20", "--overdue"])
    assert parsed.untagged and parsed.overdue
    assert parsed.exclude_tags == ["skip"]


@pytest.mark.parametrize("handler", [cmd_tasks_list, cmd_tasks_search])
def test_due_day_boundaries_are_exclusive_and_forwarded(handler):
    start = int(datetime(2026, 10, 20).timestamp() * 1000)
    following = int(datetime(2026, 10, 21).timestamp() * 1000)
    tasks = [task("none"), task("before", due_date=str(start - 1)),
             task("midnight", due_date=str(start)), task("during", due_date=str(start + 1000)),
             task("after", due_date=str(following))]

    def api(path, kwargs):
        params = kwargs["params"]
        selected = [t for t in tasks if t.get("due_date")
                    and int(t["due_date"]) < params.get("due_date_lt", following + 1)
                    and int(t["due_date"]) > params.get("due_date_gt", 0)]
        return {"tasks": selected, "last_page": True}

    fake = FlexClient(responses={"/task": api})
    result = handler(fake, args(due_before="2026-10-20"))
    assert [t["id"] for t in result["tasks"]] == ["before"]
    assert fake.calls[-1]["params"]["due_date_lt"] == start
    result = handler(fake, args(due_after="2026-10-20"))
    assert [t["id"] for t in result["tasks"]] == ["after"]
    assert fake.calls[-1]["params"]["due_date_gt"] == following - 1


@pytest.mark.parametrize("handler", [cmd_tasks_list, cmd_tasks_search])
def test_overdue_rejects_closed_done_and_missing_dates(handler):
    fake = client([task("open", due_date="1"), task("none"),
                   task("closed", due_date="1", status={"type": "closed"}),
                   task("done", due_date="1", status={"type": "done"})])
    result = handler(fake, args(overdue=True, include_closed=True))
    assert [t["id"] for t in result["tasks"]] == ["open"]
    assert fake.calls[-1]["params"]["due_date_lt"] > 1


@pytest.mark.parametrize("options", [{"due_before": "2026-02-30"}, {"due_after": "2026-1-2"},
                                    {"due_after": "2026-10-20", "due_before": "2026-10-21"}])
def test_invalid_dates_and_empty_ranges_fail_before_requests(options):
    fake = FlexClient()
    with pytest.raises(SystemExit):
        cmd_tasks_list(fake, args(**options))
    assert fake.calls == []


def test_due_filters_intersect_and_overdue_captures_one_now():
    bounds = _task_filter_params(args(due_before="2000-01-01", overdue=True))
    assert bounds["due_date_lt"] == int(datetime(2000, 1, 1).timestamp() * 1000)


def test_local_date_bounds_follow_daylight_saving_time(monkeypatch):
    try:
        with monkeypatch.context() as patch:
            patch.setenv("TZ", "Europe/Berlin")
            time.tzset()
            before = _task_filter_params(args(due_before="2026-03-29"))["due_date_lt"]
            after = _task_filter_params(args(due_after="2026-03-29"))["due_date_gt"] + 1
            assert after - before == 23 * 60 * 60 * 1000
    finally:
        time.tzset()
