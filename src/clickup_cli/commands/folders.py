"""Folder command handlers — list, get, create, update, delete, privacy."""

from ..helpers import error, resolve_space_id, add_id_argument
from .backup import backup_list, backup_options, count_folder_tasks, folder_child_lists, write_json
from .privacy import handle_privacy_request, register_privacy_subcommand


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
  list     — list all folders in a space
  get      — fetch full details of a folder by ID
  create   — create a new folder in a space (mutating)
  update   — update a folder's name (mutating)
  delete   — delete a folder (destructive)
  backup   — export folder/list metadata and tasks to local JSON files
  purge-empty — delete only if exhaustive scans prove the folder is empty
  privacy  — make a folder private or public (mutating)

Does not cover: reordering folders or setting folder-level statuses
(use the ClickUp UI for these).""",
        epilog="""\
examples:
  clickup folders list --space <name>
  clickup folders get 12345
  clickup --dry-run folders create --space <name> --name "My folder"
  clickup folders update 12345 --name "Renamed folder"
  clickup --dry-run folders delete 12345
  clickup folders privacy 12345 --private""",
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
        metavar="SPACE_NAME_OR_ID",
        required=True,
        type=str,
        help="Space name (from config) or raw ClickUp space ID",
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
        metavar="SPACE_NAME_OR_ID",
        required=True,
        type=str,
        help="Space name (from config) or raw ClickUp space ID",
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

    fb = folders_sub.add_parser(
        "backup",
        formatter_class=F,
        help="Back up a folder and child lists to local JSON files",
        description="""\
Back up a folder before migration or deletion. Writes folder metadata,
per-list backups, per-task full JSON, and a deterministic manifest.json to
--output-dir.

Defaults are safety-first: include closed tasks, archived tasks, subtasks,
all task pages, and all comments unless explicitly disabled.""",
        epilog="""\
returns:
  {"status": "ok", "action": "backup_folder", "folder_id": "...", ...}

examples:
  clickup folders backup 12345 --output-dir ./backup/folder-12345
  clickup folders backup --folder-id 12345 --output-dir ./backup --no-comments

notes:
  This command writes local files and does not mutate ClickUp.""",
    )
    add_id_argument(fb, "folder_id", "ClickUp folder ID to back up")
    fb.add_argument("--output-dir", required=True, help="Directory for backup JSON files")
    fb.add_argument("--no-closed", action="store_true", help="Do not include closed tasks")
    fb.add_argument("--no-archived", action="store_true", help="Do not include archived tasks")
    fb.add_argument("--no-subtasks", action="store_true", help="Do not include subtasks")
    fb.add_argument("--first-page", action="store_true", help="Only fetch the first task page")
    fb.add_argument("--no-comments", action="store_true", help="Do not hydrate task comments")

    fpe = folders_sub.add_parser(
        "purge-empty",
        formatter_class=F,
        help="Delete a folder only after proving every child list is empty",
        description="""\
Exhaustively scans every child list for active, closed, archived, and subtask
items. The folder is deleted only when all scans are complete and zero tasks
are found. Use --dry-run to preview the proof without deleting.""",
        epilog="""\
returns:
  {"status": "ok", "action": "purged_empty_folder", "folder_id": "..."}

examples:
  clickup --dry-run folders purge-empty 12345
  clickup folders purge-empty 12345""",
    )
    add_id_argument(fpe, "folder_id", "ClickUp folder ID to purge if empty")

    register_privacy_subcommand(
        folders_sub,
        F,
        object_type="folder",
        id_argument="folder_id",
        id_help="ClickUp folder ID",
        description="""\
Toggle the privacy of a folder via the v3 ACLs endpoint. This flips the
private/public boolean only — it does not grant or revoke individual
member or guest access. Use the ClickUp UI for granular sharing.

Exactly one of --private or --public is required.

This is a mutating command. Use --dry-run to preview the request body.""",
        epilog="""\
returns:
  {"status": "ok", "action": "set_privacy",
   "object_type": "folder", "object_id": "...", "private": true|false}

examples:
  clickup folders privacy 12345 --private
  clickup folders privacy 12345 --public
  clickup folders privacy --folder-id 12345 --private
  clickup --dry-run folders privacy 12345 --private

notes:
  Hits PATCH /v3/workspaces/{wid}/folder/{id}/acls.""",
    )


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
        folder = client.get_v2(f"/folder/{args.folder_id}", allow_dry_run=True)
        task_counts = count_folder_tasks(client, folder)
        return {
            "dry_run": True,
            "action": "delete_folder",
            "folder_id": args.folder_id,
            "folder": folder,
            "lists": folder.get("lists", []),
            "task_counts": task_counts,
        }

    client.delete_v2(f"/folder/{args.folder_id}")
    return {"status": "ok", "action": "deleted", "folder_id": args.folder_id}


def cmd_folders_backup(client, args):
    """Back up a folder and its child lists to local JSON files."""
    from pathlib import Path

    root = Path(args.output_dir)
    options = backup_options(args)
    folder = client.get_v2(f"/folder/{args.folder_id}", allow_dry_run=True)
    write_json(root / "folder.json", folder)

    files = ["folder.json"]
    list_ids = []
    task_ids = []
    task_count = 0
    complete = True
    list_manifests = []
    for child_list in folder_child_lists(client, folder, include_archived=options["include_archived"]):
        list_id = child_list["id"]
        list_ids.append(list_id)
        list_manifest = backup_list(
            client,
            list_id,
            root / "lists" / list_id,
            options,
            prefix=f"lists/{list_id}/",
        )
        list_manifests.append(list_manifest)
        task_ids.extend(list_manifest["task_ids"])
        task_count += list_manifest["task_count"]
        complete = complete and list_manifest["complete"]
        files.extend(list_manifest["files"])

    manifest = {
        "type": "folder_backup",
        "folder_id": args.folder_id,
        "list_ids": list_ids,
        "task_ids": task_ids,
        "task_count": task_count,
        "options": options,
        "complete": complete,
        "lists": list_manifests,
        "files": files,
    }
    write_json(root / "manifest.json", manifest)
    return {
        "status": "ok",
        "action": "backup_folder",
        "folder_id": args.folder_id,
        "output_dir": args.output_dir,
        "manifest": "manifest.json",
        "task_count": task_count,
        "complete": complete,
    }


def cmd_folders_purge_empty(client, args):
    """Delete a folder only after exhaustive scans prove it is empty."""
    folder = client.get_v2(f"/folder/{args.folder_id}", allow_dry_run=True)
    task_counts = count_folder_tasks(client, folder)
    if not task_counts["complete"]:
        error("Cannot purge folder: exhaustive task scan did not complete")
    if task_counts["total"] > 0:
        error("Cannot purge folder: child lists contain tasks")

    if client.dry_run:
        return {
            "dry_run": True,
            "action": "purge_empty_folder",
            "folder_id": args.folder_id,
            "deletable": True,
            "folder": folder,
            "task_counts": task_counts,
        }

    client.delete_v2(f"/folder/{args.folder_id}")
    return {"status": "ok", "action": "purged_empty_folder", "folder_id": args.folder_id}


def cmd_folders_privacy(client, args):
    """Set a folder private or public via the v3 ACLs endpoint."""
    return handle_privacy_request(
        client,
        args,
        object_type="folder",
        object_id=args.folder_id,
        path_segment="folder",
    )

COMMAND_MANIFEST = {
    "group": "folders",
    "register_parser": register_parser,
    "handlers": {
        "list": cmd_folders_list,
        "get": cmd_folders_get,
        "create": cmd_folders_create,
        "update": cmd_folders_update,
        "delete": cmd_folders_delete,
        "backup": cmd_folders_backup,
        "purge-empty": cmd_folders_purge_empty,
        "privacy": cmd_folders_privacy,
    },
}
