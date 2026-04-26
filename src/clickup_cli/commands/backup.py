"""Shared backup and destructive-safety helpers for list/folder commands."""

import json
from pathlib import Path

from ..helpers import fetch_all_comments


def backup_options(args):
    """Return safety-first backup options from argparse flags."""
    return {
        "include_closed": not getattr(args, "no_closed", False),
        "include_archived": not getattr(args, "no_archived", False),
        "subtasks": not getattr(args, "no_subtasks", False),
        "all_pages": not getattr(args, "first_page", False),
        "comments": not getattr(args, "no_comments", False),
    }


def scan_list_tasks(client, list_id, options):
    """Scan task summaries for a list using explicit completeness metadata."""
    tasks = []
    pages_fetched = 0
    complete = True
    passes = [{"archived": "false"}]
    if options["include_archived"]:
        passes.append({"archived": "true"})

    for pass_params in passes:
        page = 0
        while True:
            params = dict(pass_params)
            params["page"] = str(page)
            if options["include_closed"]:
                params["include_closed"] = "true"
            if options["subtasks"]:
                params["subtasks"] = "true"

            response = client.get_v2(
                f"/list/{list_id}/task", params=params, allow_dry_run=True
            )
            pages_fetched += 1
            tasks.extend(response.get("tasks", []))

            if response.get("last_page", False):
                break
            if not options["all_pages"]:
                complete = False
                break
            page += 1

    deduped = list({task.get("id"): task for task in tasks if task.get("id")}.values())
    return {
        "tasks": deduped,
        "task_ids": [task["id"] for task in deduped],
        "count": len(deduped),
        "pages_fetched": pages_fetched,
        "complete": complete,
    }


def count_list_tasks(client, list_id):
    """Count all active, closed, archived, and subtask items for safety checks."""
    options = {
        "include_closed": True,
        "include_archived": True,
        "subtasks": True,
        "all_pages": True,
        "comments": False,
    }
    scan = scan_list_tasks(client, list_id, options)
    return {
        "total": scan["count"],
        "task_ids": scan["task_ids"],
        "pages_fetched": scan["pages_fetched"],
        "complete": scan["complete"],
    }


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def backup_list(client, list_id, output_dir, options, *, prefix=""):
    """Write a deterministic backup for one list and return manifest details."""
    root = Path(output_dir)
    list_meta = client.get_v2(f"/list/{list_id}", allow_dry_run=True)
    scan = scan_list_tasks(client, list_id, options)

    files = []
    list_file = root / "list.json"
    tasks_file = root / "tasks.json"
    write_json(list_file, list_meta)
    write_json(tasks_file, scan["tasks"])
    files.extend([f"{prefix}list.json", f"{prefix}tasks.json"])

    comments_complete = True
    for task_id in scan["task_ids"]:
        task = client.get_v2(f"/task/{task_id}", allow_dry_run=True)
        if options["comments"]:
            comment_result = fetch_all_comments(client, task_id, all_pages=True)
            task["comments"] = comment_result["comments"]
            task["comments_complete"] = comment_result["complete"]
            comments_complete = comments_complete and comment_result["complete"]
        task_file = root / "tasks" / f"{task_id}.json"
        write_json(task_file, task)
        files.append(f"{prefix}tasks/{task_id}.json")

    manifest = {
        "type": "list_backup",
        "list_id": list_id,
        "task_ids": scan["task_ids"],
        "task_count": scan["count"],
        "options": options,
        "complete": scan["complete"] and comments_complete,
        "tasks_complete": scan["complete"],
        "comments_complete": comments_complete,
        "pages_fetched": scan["pages_fetched"],
        "files": files,
    }
    write_json(root / "manifest.json", manifest)
    return manifest


def count_folder_tasks(client, folder):
    """Count all tasks in every child list included by folder metadata."""
    list_counts = []
    total = 0
    task_ids = []
    complete = True
    pages_fetched = 0
    for child_list in folder_child_lists(client, folder, include_archived=True):
        count = count_list_tasks(client, child_list["id"])
        list_counts.append({"list_id": child_list["id"], **count})
        total += count["total"]
        task_ids.extend(count["task_ids"])
        complete = complete and count["complete"]
        pages_fetched += count["pages_fetched"]
    return {
        "total": total,
        "task_ids": task_ids,
        "lists": list_counts,
        "pages_fetched": pages_fetched,
        "complete": complete,
    }


def folder_child_lists(client, folder, include_archived=False):
    """Return folder child lists, optionally adding archived lists not in metadata."""
    child_lists = list(folder.get("lists", []))
    if include_archived and folder.get("id"):
        archived_response = client.get_v2(
            f"/folder/{folder['id']}/list",
            params={"archived": "true"},
            allow_dry_run=True,
        )
        child_lists.extend(archived_response.get("lists", []))
    deduped = {}
    for child_list in child_lists:
        deduped.setdefault(child_list["id"], child_list)
    return list(deduped.values())
