"""List command handlers — list, get, create, update, delete."""

from ..helpers import read_content, error, resolve_space_id, add_id_argument


def register_parser(subparsers, F):
    """Register all lists subcommands on the given subparsers object."""
    lists_parser = subparsers.add_parser(
        "lists",
        formatter_class=F,
        help="Full list CRUD: list, get, create, update, delete",
        description="""\
Manage ClickUp lists — the containers that hold tasks.

Lists can live directly in a space (folderless) or inside a folder.
Use --folder or --space to specify the parent depending on the context.

Subcommands:
  list    — list lists in a folder or folderless lists in a space
  get     — fetch full details of a list by ID
  create  — create a new list in a folder or space (mutating)
  update  — update a list's name, content, or status (mutating)
  delete  — delete a list (destructive)""",
        epilog="""\
examples:
  clickup lists list --folder 12345
  clickup lists list --space <name>
  clickup lists get 12345
  clickup --dry-run lists create --folder 12345 --name "Tasks"
  clickup lists create --space <name> --name "Backlog"
  clickup lists update 12345 --name "Renamed list"
  clickup --dry-run lists delete 12345""",
    )
    lists_sub = lists_parser.add_subparsers(dest="command", required=True)

    # lists list
    ll = lists_sub.add_parser(
        "list",
        formatter_class=F,
        help="List lists in a folder or folderless lists in a space",
        description="""\
List lists in a specific context. Exactly one of --folder or --space
is required:

  --folder <id>   — lists all lists inside a folder
  --space <name>  — lists only folderless lists in a space""",
        epilog="""\
returns:
  {"lists": [...], "count": N}

examples:
  clickup lists list --folder 12345
  clickup lists list --space <name>
  clickup --pretty lists list --space <name>

notes:
  --folder and --space are mutually exclusive.
  --space only returns folderless lists. To see lists inside folders,
  use 'folders list --space <name>' first to find folder IDs, then
  'lists list --folder <id>' for each folder.""",
    )
    ll_target = ll.add_mutually_exclusive_group(required=True)
    ll_target.add_argument(
        "--folder", type=str, help="Folder ID — list all lists inside this folder"
    )
    ll_target.add_argument(
        "--space",
        type=str,
        help="Space name or ID — list folderless lists in this space",
    )

    # lists get
    lg = lists_sub.add_parser(
        "get",
        formatter_class=F,
        help="Fetch full details of a list by ID",
        description="""\
Fetch full details of a list by its ClickUp list ID.

Returns list metadata including name, content, task count, statuses,
folder, and space information.""",
        epilog="""\
returns:
  One list JSON object with all fields.

examples:
  clickup lists get 901816700000
  clickup --pretty lists get 12345""",
    )
    add_id_argument(lg, "list_id", "ClickUp list ID")

    # lists create
    lc = lists_sub.add_parser(
        "create",
        formatter_class=F,
        help="Create a new list in a folder or space",
        description="""\
Create a new list. This is a mutating command.

Exactly one of --folder or --space is required:

  --folder <id>   — creates the list inside a folder
  --space <name>  — creates a folderless list directly in a space

Use --dry-run to preview the request body without creating the list.
Global flags may appear before or after the command group:
  clickup --dry-run lists create --folder 12345 --name "Tasks" """,
        epilog="""\
returns:
  The created list object from the API.

examples:
  clickup lists create --folder 12345 --name "Tasks"
  clickup lists create --space <name> --name "Backlog"
  clickup --dry-run lists create --space <name> --name "Test list"

notes:
  --folder and --space are mutually exclusive. Using both is an error.""",
    )
    lc_target = lc.add_mutually_exclusive_group(required=True)
    lc_target.add_argument(
        "--folder", type=str, help="Folder ID — create list inside this folder"
    )
    lc_target.add_argument(
        "--space",
        type=str,
        help="Space name or ID — create a folderless list in this space",
    )
    lc.add_argument("--name", required=True, help="List name (required)")
    lc.add_argument("--content", type=str, help="List description/content")
    lc.add_argument("--status", type=str, help="Initial list status")

    # lists update
    lu = lists_sub.add_parser(
        "update",
        formatter_class=F,
        help="Update a list (name, content, status)",
        description="""\
Update a list's name, content, or status. This is a mutating command.

At least one mutable field is required: --name, --content, --content-file,
or --status. If none are provided, the command exits with an error.

Use --dry-run to preview the request body without applying changes.
Global flags may appear before or after the command group:
  clickup --dry-run lists update 12345 --name "New name" """,
        epilog="""\
returns:
  The updated list object from the API.

examples:
  clickup lists update 12345 --name "Renamed list"
  clickup lists update 12345 --content "Updated description"
  clickup --dry-run lists update 12345 --name "Test rename" """,
    )
    add_id_argument(lu, "list_id", "ClickUp list ID to update")
    lu.add_argument("--name", type=str, help="New list name")
    lu.add_argument(
        "--content",
        type=str,
        help="Inline description (mutually exclusive with --content-file)",
    )
    lu.add_argument(
        "--content-file", type=str, help="Path to a file containing list description"
    )
    lu.add_argument("--status", type=str, help="New list status")

    # lists delete
    ld = lists_sub.add_parser(
        "delete",
        formatter_class=F,
        help="Delete a list (destructive)",
        description="""\
Delete a list permanently. This is a destructive, irreversible command.

Deleting a list also deletes all tasks inside it. Use with extreme caution.

Use --dry-run to preview the operation without deleting anything.
Global flags may appear before or after the command group:
  clickup --dry-run lists delete 12345""",
        epilog="""\
returns:
  {"status": "ok", "action": "deleted", "list_id": "..."}

examples:
  clickup --dry-run lists delete 12345
  clickup lists delete 12345""",
    )
    add_id_argument(ld, "list_id", "ClickUp list ID to delete")


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
