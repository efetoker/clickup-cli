"""List command handlers — list, get, create, update, delete."""

from ..helpers import read_content, error, resolve_space_id


def cmd_lists_list(client, args):
    """List lists in a folder or folderless lists in a space."""
    if args.folder:
        resp = client.get_v2(f"/folder/{args.folder}/list")
        lists = resp.get("lists", [])
        return {"lists": lists, "count": len(lists)}
    elif args.space:
        space_id = resolve_space_id(args.space)
        resp = client.get_v2(f"/space/{space_id}/list")
        lists = resp.get("lists", [])
        return {"lists": lists, "count": len(lists)}
    else:
        error("Provide either --folder <folder_id> or --space <name|id>")


def cmd_lists_get(client, args):
    """Get full details of a list by ID."""
    return client.get_v2(f"/list/{args.list_id}")


def cmd_lists_create(client, args):
    """Create a list in a folder or directly in a space (folderless)."""
    body = {"name": args.name}
    if args.content:
        body["content"] = args.content
    if args.status:
        body["status"] = args.status

    if args.folder:
        endpoint = f"/folder/{args.folder}/list"
        target = {"folder_id": args.folder}
    elif args.space:
        space_id = resolve_space_id(args.space)
        endpoint = f"/space/{space_id}/list"
        target = {"space_id": space_id}
    else:
        error("Provide either --folder <folder_id> or --space <name|id>")

    if client.dry_run:
        return {"dry_run": True, "action": "create_list", **target, "body": body}

    return client.post_v2(endpoint, data=body)


def cmd_lists_update(client, args):
    """Update a list (name, content, status)."""
    desc = read_content(args.content, args.content_file, "--content")
    body = {}
    if args.name:
        body["name"] = args.name
    if desc:
        body["content"] = desc
    if args.status:
        body["status"] = args.status

    if not body:
        error("Nothing to update — provide at least one of: --name, --content, --content-file, --status")

    if client.dry_run:
        return {"dry_run": True, "action": "update_list", "list_id": args.list_id, "body": body}

    return client.put_v2(f"/list/{args.list_id}", data=body)


def cmd_lists_delete(client, args):
    """Delete a list by ID."""
    if client.dry_run:
        return {"dry_run": True, "action": "delete_list", "list_id": args.list_id}

    client.delete_v2(f"/list/{args.list_id}")
    return {"status": "ok", "action": "deleted", "list_id": args.list_id}
