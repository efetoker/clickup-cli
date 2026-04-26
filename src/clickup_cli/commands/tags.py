"""Tag command handlers — list, lifecycle, usage, add, remove."""

from urllib.parse import quote

from ..helpers import add_id_argument, compact_task, resolve_space_id
from .tasks_internal.shared import (
    DEFAULT_TASK_PAGE_BUDGET,
    _filter_by_tags,
    _paginate_tasks,
    _resolve_scope_list_ids,
)


def register_parser(subparsers, F):
    """Register all tags subcommands on the given subparsers object."""
    tags_parser = subparsers.add_parser(
        "tags",
        formatter_class=F,
        help="List/create/delete space tags, audit usage, add/remove tags on tasks",
        description="""\
Manage tags — list, create, delete, and audit Space tags; add or remove tags on tasks.

Subcommands:
  list    — list all tags in a space
  create  — create a Space-level tag (mutating)
  delete  — delete a Space-level tag from a Space (mutating)
  usage   — audit task usage for a Space tag
  add     — add a tag to a task (mutating)
  remove  — remove a tag from a task (mutating)

Tag names are lowercase in the API, even if they display with title case
in the ClickUp UI. The CLI lowercases tag names automatically.""",
        epilog="""\
examples:
  clickup tags list --space <name>
  clickup tags create --space <name> --tag urgent --bg-color "#ff0000"
  clickup --dry-run tags delete --space <name> --tag "in review"
  clickup tags usage --space <name> --tag urgent --include-closed
  clickup tags add abc123 --tag "in review"
  clickup tags remove abc123 --tag "draft" """,
    )
    tags_sub = tags_parser.add_subparsers(dest="command", required=True)

    # tags list
    tgl = tags_sub.add_parser(
        "list",
        formatter_class=F,
        help="List all tags in a space",
        description="""\
List all tags available in a space. Returns tag names, colors, and metadata.

Accepts a configured space name or a raw space ID.""",
        epilog="""\
returns:
  {"tags": [...], "count": N}

examples:
  clickup tags list --space <name>
  clickup --pretty tags list --space <name>""",
    )
    tgl.add_argument(
        "--space",
        required=True,
        type=str,
        help="Space name (from config) or raw space ID",
    )

    # tags create
    tgc = tags_sub.add_parser(
        "create",
        formatter_class=F,
        help="Create a Space-level tag",
        description="""\
Create a tag in a Space. This is a mutating command.

The tag name is automatically lowercased. Use --dry-run to preview the
Space ID and request body without creating the tag.""",
        epilog="""\
returns:
  The created tag response from the API, or a dry-run plan.

examples:
  clickup tags create --space <name> --tag urgent
  clickup tags create --space <name> --tag urgent --fg-color "#fff" --bg-color "#f00"
  clickup --dry-run tags create --space <name> --tag "in review""",
    )
    tgc.add_argument("--space", required=True, type=str, help="Space name or raw ID")
    tgc.add_argument("--tag", required=True, type=str, help="Tag name to create")
    tgc.add_argument("--fg-color", type=str, help="Optional foreground color")
    tgc.add_argument("--bg-color", type=str, help="Optional background color")

    # tags delete
    tgd = tags_sub.add_parser(
        "delete",
        formatter_class=F,
        help="Delete a Space-level tag",
        description="""\
Delete a tag from a Space. This is a mutating command.

Deleting a Space tag removes it from all tasks in that Space. Use --dry-run
to preview the blast radius language and URL-safe tag path.""",
        epilog="""\
returns:
  {"status": "ok", "action": "space_tag_deleted", "space_id": "...", "tag": "..."}

examples:
  clickup --dry-run tags delete --space <name> --tag "in review"
  clickup tags delete --space <name> --tag urgent""",
    )
    tgd.add_argument("--space", required=True, type=str, help="Space name or raw ID")
    tgd.add_argument("--tag", required=True, type=str, help="Tag name to delete")

    # tags usage
    tgu = tags_sub.add_parser(
        "usage",
        formatter_class=F,
        help="Audit task usage for a Space tag",
        description="""\
Scan tasks in a Space and report which tasks currently use a tag.

By default this is a bounded active-task scan. Add --include-closed,
--include-archived, --subtasks, and --all-pages for exhaustive migration
checks.""",
        epilog="""\
returns:
  {"tag": "...", "count": N, "tasks": [...], "results_complete": true|false}

examples:
  clickup tags usage --space <name> --tag urgent
  clickup tags usage --space <name> --tag urgent --include-closed --include-archived --subtasks --all-pages""",
    )
    tgu.add_argument("--space", required=True, type=str, help="Space name or raw ID")
    tgu.add_argument("--tag", required=True, type=str, help="Tag name to audit")
    tgu.add_argument("--include-closed", action="store_true", help="Include closed tasks")
    tgu.add_argument("--include-archived", action="store_true", help="Include archived lists/tasks")
    tgu.add_argument("--subtasks", action="store_true", help="Include subtasks")
    tgu.add_argument("--all-pages", action="store_true", help="Fetch every task page")

    # tags add
    tga = tags_sub.add_parser(
        "add",
        formatter_class=F,
        help="Add a tag to a task",
        description="""\
Add a tag to a task. This is a mutating command.

The tag name is automatically lowercased (ClickUp API requirement).
The tag must already exist in the space — this command does not create tags.

Use --dry-run to preview without applying.
Global flags may appear before or after the command group:
  clickup --dry-run tags add abc123 --tag "in review" """,
        epilog="""\
returns:
  {"status": "ok", "action": "tag_added", "task_id": "...", "tag": "..."}

examples:
  clickup tags add abc123 --tag "in review"
  clickup --dry-run tags add abc123 --tag "draft" """,
    )
    add_id_argument(tga, "task_id", "ClickUp task ID")
    tga.add_argument(
        "--tag", required=True, type=str, help="Tag name to add (auto-lowercased)"
    )

    # tags remove
    tgr = tags_sub.add_parser(
        "remove",
        formatter_class=F,
        help="Remove a tag from a task",
        description="""\
Remove a tag from a task. This is a mutating command.

The tag name is automatically lowercased (ClickUp API requirement).

Use --dry-run to preview without applying.
Global flags may appear before or after the command group:
  clickup --dry-run tags remove abc123 --tag "draft" """,
        epilog="""\
returns:
  {"status": "ok", "action": "tag_removed", "task_id": "...", "tag": "..."}

examples:
  clickup tags remove abc123 --tag "draft"
  clickup --dry-run tags remove abc123 --tag "in review" """,
    )
    add_id_argument(tgr, "task_id", "ClickUp task ID")
    tgr.add_argument(
        "--tag", required=True, type=str, help="Tag name to remove (auto-lowercased)"
    )


def cmd_tags_list(client, args):
    """List all tags in a space."""
    space_id = resolve_space_id(args.space)
    resp = client.get_v2(f"/space/{space_id}/tag")
    tags = resp.get("tags", [])
    return {"tags": tags, "count": len(tags)}


def _space_tag_body(tag_name, fg_color=None, bg_color=None):
    tag = {"name": tag_name}
    if fg_color:
        tag["tag_fg"] = fg_color
    if bg_color:
        tag["tag_bg"] = bg_color
    return {"tag": tag}


def cmd_tags_create(client, args):
    """Create a Space-level tag."""
    space_id = resolve_space_id(args.space)
    tag_name = args.tag.lower()
    body = _space_tag_body(tag_name, args.fg_color, args.bg_color)
    if client.dry_run:
        return {
            "dry_run": True,
            "action": "create_space_tag",
            "space_id": space_id,
            "tag": tag_name,
            "body": body,
        }
    return client.post_v2(f"/space/{space_id}/tag", data=body)


def cmd_tags_delete(client, args):
    """Delete a Space-level tag."""
    space_id = resolve_space_id(args.space)
    tag_name = args.tag.lower()
    encoded_tag = quote(tag_name, safe="")
    if client.dry_run:
        return {
            "dry_run": True,
            "action": "delete_space_tag",
            "space_id": space_id,
            "tag": tag_name,
            "encoded_tag": encoded_tag,
            "warning": "Deleting a Space tag removes it from all tasks in this Space.",
        }
    client.delete_v2(f"/space/{space_id}/tag/{encoded_tag}")
    return {"status": "ok", "action": "space_tag_deleted", "space_id": space_id, "tag": tag_name}


def cmd_tags_usage(client, args):
    """Audit task usage for a Space-level tag."""
    tag_name = args.tag.lower()
    include_archived = getattr(args, "include_archived", False)
    list_ids = _resolve_scope_list_ids(
        client,
        args.space,
        allow_empty=include_archived,
    )
    if include_archived:
        archived_list_ids = _resolve_scope_list_ids(
            client,
            args.space,
            include_archived=True,
            allow_empty=True,
        )
        list_ids = list(dict.fromkeys(list_ids + archived_list_ids))

    params = {"archived": "false"}
    if getattr(args, "include_closed", False):
        params["include_closed"] = "true"
    if getattr(args, "subtasks", False):
        params["subtasks"] = "true"

    budget = None if getattr(args, "all_pages", False) else {"remaining": DEFAULT_TASK_PAGE_BUDGET}
    all_tasks = []
    pages_fetched = 0
    complete = True
    for list_id in list_ids:
        result = _paginate_tasks(client, f"/list/{list_id}/task", dict(params), budget=budget)
        all_tasks.extend(result["tasks"])
        pages_fetched += result["pages_fetched"]
        complete = complete and result["complete"]
        if include_archived:
            archived_params = dict(params)
            archived_params["archived"] = "true"
            result = _paginate_tasks(client, f"/list/{list_id}/task", archived_params, budget=budget)
            all_tasks.extend(result["tasks"])
            pages_fetched += result["pages_fetched"]
            complete = complete and result["complete"]

    matching = _filter_by_tags(all_tasks, [tag_name])
    tasks = [compact_task(task) for task in matching]
    return {
        "tag": tag_name,
        "count": len(tasks),
        "tasks": tasks,
        "lists_scanned": len(list_ids),
        "pages_fetched": pages_fetched,
        "results_complete": complete,
        "results_truncated": not complete,
    }


def _tag_action(client, args, method, dry_action, done_action):
    """Shared logic for tag add/remove."""
    tag_name = args.tag.lower()
    if client.dry_run:
        return {"dry_run": True, "action": dry_action, "task_id": args.task_id, "tag": tag_name}
    method(f"/task/{args.task_id}/tag/{tag_name}", **({"data": {}} if method == client.post_v2 else {}))
    return {"status": "ok", "action": done_action, "task_id": args.task_id, "tag": tag_name}


def cmd_tags_add(client, args):
    """Add a tag to a task."""
    return _tag_action(client, args, client.post_v2, "add_tag", "tag_added")


def cmd_tags_remove(client, args):
    """Remove a tag from a task."""
    return _tag_action(client, args, client.delete_v2, "remove_tag", "tag_removed")

COMMAND_MANIFEST = {
    "group": "tags",
    "register_parser": register_parser,
    "handlers": {
        "list": cmd_tags_list,
        "create": cmd_tags_create,
        "delete": cmd_tags_delete,
        "usage": cmd_tags_usage,
        "add": cmd_tags_add,
        "remove": cmd_tags_remove,
    },
}
