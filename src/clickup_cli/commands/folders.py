"""Folder command handlers — list, get, create, update, delete."""

from ..helpers import error, resolve_space_id


def cmd_folders_list(client, args):
    """List all folders in a space."""
    space_id = resolve_space_id(args.space)
    resp = client.get_v2(f"/space/{space_id}/folder")
    folders = resp.get("folders", [])
    return {"folders": folders, "count": len(folders)}


def cmd_folders_get(client, args):
    """Get full details of a folder by ID."""
    return client.get_v2(f"/folder/{args.folder_id}")


def cmd_folders_create(client, args):
    """Create a folder in a space."""
    space_id = resolve_space_id(args.space)
    body = {"name": args.name}

    if client.dry_run:
        return {"dry_run": True, "action": "create_folder", "space_id": space_id, "body": body}

    return client.post_v2(f"/space/{space_id}/folder", data=body)


def cmd_folders_update(client, args):
    """Update a folder (name)."""
    body = {}
    if args.name:
        body["name"] = args.name

    if not body:
        error("Nothing to update — provide at least --name")

    if client.dry_run:
        return {"dry_run": True, "action": "update_folder", "folder_id": args.folder_id, "body": body}

    return client.put_v2(f"/folder/{args.folder_id}", data=body)


def cmd_folders_delete(client, args):
    """Delete a folder by ID."""
    if client.dry_run:
        return {"dry_run": True, "action": "delete_folder", "folder_id": args.folder_id}

    client.delete_v2(f"/folder/{args.folder_id}")
    return {"status": "ok", "action": "deleted", "folder_id": args.folder_id}
