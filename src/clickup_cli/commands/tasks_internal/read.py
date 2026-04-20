"""Read-oriented task handlers behind the facade."""

import sys

import requests

from ...helpers import fetch_all_comments
from .shared import (
    DEFAULT_TASK_PAGE_BUDGET,
    _TASK_ID_PATTERN,
    _budget_metadata,
    _filter_by_tags,
    _format_and_wrap,
    _paginate_tasks,
    _parse_search_custom_fields,
    _resolve_list_id,
    _resolve_scope_list_ids,
)


def cmd_tasks_list(client, args):
    list_id = _resolve_list_id(args, client=client)
    if client.dry_run:
        return {"dry_run": True, "action": "list_tasks", "list_id": list_id}

    params = {"archived": "false"}
    if args.include_closed:
        params["include_closed"] = "true"
    if args.status:
        params["statuses[]"] = args.status
    if args.subtasks:
        params["subtasks"] = "true"
    tag_filter = getattr(args, "tags", None)
    if tag_filter:
        params["tags[]"] = [tag.lower() for tag in tag_filter]

    budget = None if getattr(args, "all_pages", False) else {"remaining": DEFAULT_TASK_PAGE_BUDGET}
    active_result = _paginate_tasks(client, f"/list/{list_id}/task", params, budget=budget)
    all_tasks = list(active_result["tasks"])
    total_pages = active_result["pages_fetched"]
    complete = active_result["complete"]

    if getattr(args, "include_archived", False):
        archived_params = dict(params)
        archived_params["archived"] = "true"
        archived_result = _paginate_tasks(
            client,
            f"/list/{list_id}/task",
            archived_params,
            budget=budget,
        )
        all_tasks.extend(archived_result["tasks"])
        total_pages += archived_result["pages_fetched"]
        complete = complete and archived_result["complete"]

    result = _format_and_wrap(all_tasks, args)
    result.update(_budget_metadata(total_pages, complete))
    return result


def cmd_tasks_get(client, args):
    task = client.get_v2(f"/task/{args.task_id}")

    if getattr(args, "no_comments", False):
        return task

    try:
        comment_result = fetch_all_comments(
            client,
            args.task_id,
            all_pages=getattr(args, "all_comments", False),
        )
        all_comments = comment_result["comments"]
        task["comments"] = [
            {
                "id": comment.get("id"),
                "comment_text": comment.get("comment_text", ""),
                "user": comment.get("user", {}).get("username", "unknown"),
                "date": comment.get("date"),
            }
            for comment in all_comments
        ]
        task["comment_count"] = len(all_comments)
        task["comment_count_returned"] = len(all_comments)
        task["comments_complete"] = comment_result["complete"]
        task["comments_truncated"] = comment_result["truncated"]
    except (requests.RequestException, KeyError, ValueError) as exc:
        print(f"warning: could not fetch comments: {exc}", file=sys.stderr)
        task["comments"] = []
        task["comment_count"] = 0
        task["comment_count_returned"] = 0
        task["comments_complete"] = False
        task["comments_truncated"] = False

    return task


def cmd_tasks_search(client, args):
    """Search tasks across workspace or scoped containers, then normalize output.

    By default this shares the bounded pagination contract used by `tasks list`:
    active and archived passes consume one shared page budget unless
    `--all-pages` opts into an exhaustive scan, and the response advertises
    completeness via `pages_fetched` / `results_complete` / `results_truncated`.

    `--space` is expanded to every list in that space unless `--list` or
    `--folder` already narrows the search. If the free-text query looks like a
    task ID pattern (for example `PROJ-123`) and `--name-prefix` is omitted, the
    same value is reused as a client-side `name_prefix` filter so broad ClickUp
    search results collapse back to exact title prefixes.

    Archived tasks require a second search pass because ClickUp treats
    `archived=true` as archived-only. For space-scoped searches that means a
    fallback archived list-ID expansion before the archived pass runs, while
    empty active scopes can still stay valid when `--include-archived` is the
    only source of matches. Tag filters are also applied client-side here, after
    the API search results are merged.
    """
    resolved_space_list_ids = None
    if args.space and not getattr(args, "list_id", None) and not getattr(args, "folder_id", None):
        resolved_space_list_ids = _resolve_scope_list_ids(
            client,
            args.space,
            allow_empty=getattr(args, "include_archived", False),
        )

    if client.dry_run:
        return {"dry_run": True, "action": "search_tasks", "query": args.query}

    name_prefix = getattr(args, "name_prefix", None)
    if not name_prefix and _TASK_ID_PATTERN.match(args.query):
        name_prefix = args.query

    params = {"search": args.query}
    if args.include_closed:
        params["include_closed"] = "true"
    custom_fields = _parse_search_custom_fields(getattr(args, "custom_fields", None))
    if custom_fields:
        params["custom_fields"] = custom_fields
    run_active_search = True
    if hasattr(args, "list_id") and args.list_id:
        params["list_ids[]"] = args.list_id
    elif hasattr(args, "folder_id") and args.folder_id:
        params["project_ids[]"] = args.folder_id
    elif resolved_space_list_ids is not None:
        if resolved_space_list_ids:
            params["list_ids[]"] = resolved_space_list_ids
        else:
            run_active_search = False

    all_tasks = []
    budget = None if getattr(args, "all_pages", False) else {"remaining": DEFAULT_TASK_PAGE_BUDGET}
    total_pages = 0
    complete = True
    if run_active_search:
        active_result = _paginate_tasks(
            client,
            f"/team/{client.runtime.workspace_id}/task",
            params,
            budget=budget,
        )
        all_tasks = list(active_result["tasks"])
        total_pages += active_result["pages_fetched"]
        complete = active_result["complete"]

    if getattr(args, "include_archived", False):
        archived_params = dict(params)
        archived_params["archived"] = "true"
        run_archived_search = True
        if resolved_space_list_ids is not None:
            archived_list_ids = _resolve_scope_list_ids(
                client,
                args.space,
                include_archived=True,
                allow_empty=True,
            )
            scoped_archived_list_ids = list(dict.fromkeys(resolved_space_list_ids + archived_list_ids))
            if scoped_archived_list_ids:
                archived_params["list_ids[]"] = scoped_archived_list_ids
            else:
                run_archived_search = False
        if run_archived_search:
            archived_result = _paginate_tasks(
                client,
                f"/team/{client.runtime.workspace_id}/task",
                archived_params,
                budget=budget,
            )
            all_tasks.extend(archived_result["tasks"])
            total_pages += archived_result["pages_fetched"]
            complete = complete and archived_result["complete"]
        elif budget is not None and budget["remaining"] <= 0:
            complete = False

    if name_prefix:
        all_tasks = [
            task
            for task in all_tasks
            if task.get("name", "").startswith(name_prefix)
        ]

    tag_filter = getattr(args, "tags", None)
    if tag_filter:
        all_tasks = _filter_by_tags(all_tasks, tag_filter)

    result = _format_and_wrap(all_tasks, args)
    result.update(_budget_metadata(total_pages, complete))
    return result
