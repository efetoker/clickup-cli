"""Tag command handlers — list, add, remove."""

from ..helpers import resolve_space_id, add_id_argument


def register_parser(subparsers, F):
    """Register all tags subcommands on the given subparsers object."""
    tags_parser = subparsers.add_parser(
        "tags",
        formatter_class=F,
        help="List space tags, add/remove tags on tasks",
        description="""\
Manage tags — list available tags in a space, add or remove tags on tasks.

Subcommands:
  list    — list all tags in a space
  add     — add a tag to a task (mutating)
  remove  — remove a tag from a task (mutating)

Tag names are lowercase in the API, even if they display with title case
in the ClickUp UI. The CLI lowercases tag names automatically.""",
        epilog="""\
examples:
  clickup tags list --space <name>
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
