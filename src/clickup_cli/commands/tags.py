"""Tag command handlers — list, add, remove."""

from ..helpers import resolve_space_id


def cmd_tags_list(client, args):
    """List all tags in a space."""
    space_id = resolve_space_id(args.space)
    resp = client.get_v2(f"/space/{space_id}/tag")
    tags = resp.get("tags", [])
    return {"tags": tags, "count": len(tags)}


def cmd_tags_add(client, args):
    """Add a tag to a task."""
    tag_name = args.tag.lower()
    if client.dry_run:
        return {"dry_run": True, "action": "add_tag", "task_id": args.task_id, "tag": tag_name}
    client.post_v2(f"/task/{args.task_id}/tag/{tag_name}", data={})
    return {"status": "ok", "action": "tag_added", "task_id": args.task_id, "tag": tag_name}


def cmd_tags_remove(client, args):
    """Remove a tag from a task."""
    tag_name = args.tag.lower()
    if client.dry_run:
        return {"dry_run": True, "action": "remove_tag", "task_id": args.task_id, "tag": tag_name}
    client.delete_v2(f"/task/{args.task_id}/tag/{tag_name}")
    return {"status": "ok", "action": "tag_removed", "task_id": args.task_id, "tag": tag_name}
