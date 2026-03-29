"""Folder command handlers — list, get, create, update, delete."""

from ..helpers import error, resolve_space_id, add_id_argument


def register_parser(subparsers, F):
    """Register all folders subcommands on the given subparsers object."""
    folders_parser = subparsers.add_parser(
        "folders",
        formatter_class=F,
        help="Full folder CRUD: list, get, create, update, delete",
        description="""\
Manage ClickUp folders — organize lists within spaces.

Folders are containers that sit between spaces and lists. Use them to
group related lists together (e.g. a "Sprint 1" folder under a space).

Subcommands:
  list    — list all folders in a space
  get     — fetch full details of a folder by ID
  create  — create a new folder in a space (mutating)
  update  — update a folder's name (mutating)
  delete  — delete a folder (destructive)

Does not cover: reordering folders or setting folder-level statuses
(use the ClickUp UI for these).""",
        epilog="""\
examples:
  clickup folders list --space <name>
  clickup folders get 12345
  clickup --dry-run folders create --space <name> --name "My folder"
  clickup folders update 12345 --name "Renamed folder"
  clickup --dry-run folders delete 12345""",
    )
    folders_sub = folders_parser.add_subparsers(dest="command", required=True)

    # folders list
    fl = folders_sub.add_parser(
        "list",
        formatter_class=F,
        help="List all folders in a space",
        description="""\
List all folders in a space. Returns folder names, IDs, and metadata.

Use this to discover folder IDs before creating lists inside them
or to see the organizational structure of a space.""",
        epilog="""\
returns:
  {"folders": [...], "count": N}

examples:
  clickup folders list --space <name>
  clickup folders list --space 901810200000
  clickup --pretty folders list --space <name>""",
    )
    fl.add_argument(
        "--space",
        required=True,
        type=str,
        help="Space name (from config) or raw space ID",
    )

    # folders get
    fg = folders_sub.add_parser(
        "get",
        formatter_class=F,
        help="Fetch full details of a folder by ID",
        description="""\
Fetch full details of a folder including its lists, statuses, and metadata.

Use this when you need to inspect a specific folder or discover the
lists inside it.""",
        epilog="""\
returns:
  One folder JSON object with all fields (id, name, lists, statuses, etc.)

examples:
  clickup folders get 12345
  clickup --pretty folders get 12345""",
    )
    add_id_argument(fg, "folder_id", "ClickUp folder ID")

    # folders create
    fc = folders_sub.add_parser(
        "create",
        formatter_class=F,
        help="Create a new folder in a space",
        description="""\
Create a new folder in a space. This is a mutating command.

Use --dry-run to preview the request body without creating the folder.
Global flags may appear before or after the command group:
  clickup --dry-run folders create --space <name> --name "My folder" """,
        epilog="""\
returns:
  The created folder object from the API.

examples:
  clickup folders create --space <name> --name "My folder"
  clickup --dry-run folders create --space <name> --name "Test folder" """,
    )
    fc.add_argument(
        "--space",
        required=True,
        type=str,
        help="Space name (from config) or raw space ID",
    )
    fc.add_argument("--name", required=True, help="Folder name (required)")

    # folders update
    fu = folders_sub.add_parser(
        "update",
        formatter_class=F,
        help="Update a folder (name)",
        description="""\
Update a folder's name. This is a mutating command.

Use --dry-run to preview without applying changes.
Global flags may appear before or after the command group:
  clickup --dry-run folders update 12345 --name "New name" """,
        epilog="""\
returns:
  The updated folder object from the API.

examples:
  clickup folders update 12345 --name "Renamed folder"
  clickup --dry-run folders update 12345 --name "Test rename" """,
    )
    add_id_argument(fu, "folder_id", "ClickUp folder ID to update")
    fu.add_argument("--name", type=str, help="New folder name")

    # folders delete
    fd = folders_sub.add_parser(
        "delete",
        formatter_class=F,
        help="Delete a folder (destructive)",
        description="""\
Delete a folder permanently. This is a destructive, irreversible command.

Deleting a folder also deletes all lists and tasks inside it.
Use with extreme caution.

Use --dry-run to preview the operation without deleting anything.
Global flags may appear before or after the command group:
  clickup --dry-run folders delete 12345""",
        epilog="""\
returns:
  {"status": "ok", "action": "deleted", "folder_id": "..."}

examples:
  clickup --dry-run folders delete 12345
  clickup folders delete 12345""",
    )
    add_id_argument(fd, "folder_id", "ClickUp folder ID to delete")


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
