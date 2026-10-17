"""Space tag lifecycle, task tag operations, and migration commands."""

import json
import re
import sys
from argparse import Namespace
from contextlib import redirect_stderr
from io import StringIO
from urllib.parse import quote

from ..helpers import add_id_argument, compact_task, error, resolve_space_id
from ..tag_validation import (
    add_strict_tag_flags,
    space_for_task,
    strict_tags_enabled,
    validate_space_tags,
)
from .tasks_internal.shared import (
    DEFAULT_TASK_PAGE_BUDGET,
    _filter_by_tags,
    _paginate_tasks,
    _resolve_scope_list_ids,
    _scope_items,
)
from .tasks_internal.write import _execute_bulk_tag_plan


def register_parser(subparsers, F):
    """Register all tags subcommands on the given subparsers object."""
    tags_parser = subparsers.add_parser(
        "tags",
        formatter_class=F,
        help="List/create/edit/delete space tags, audit or migrate usage, add/remove task tags",
        description="""\
Manage Space tags and task tag assignments.

Subcommands:
  list    — list all tags in a space
  create  — create a Space-level tag (mutating)
  edit    - rename or recolor a Space tag (mutating)
  migrate - merge, rename or drop task tags using a map (mutating)
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
  clickup tags usage personal
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
        help="Audit task usage for a Space tag, or for every tag in the space",
        description="""\
Scan tasks in a Space and report which tasks currently use a tag.

With --tag, audits that single tag and lists the matching tasks. Without
--tag, audits every tag in the space: one space-tag read plus one task
scan, counted client-side, returning per-tag usage counts only (no task
lists). Zero-usage tags are included with count 0, sorted by count
descending then name.

By default this is a bounded active-task scan. Add --include-closed,
--include-archived, --subtasks, and --all-pages for exhaustive migration
checks. These flags apply to both modes.""",
        epilog="""\
returns (single tag):
  {"tag": "...", "count": N, "tasks": [...], "lists_scanned": N,
   "pages_fetched": N, "results_complete": true|false,
   "results_truncated": true|false}

returns (all tags):
  {"tags": [{"name": "...", "count": N}, ...], "count": N,
   "lists_scanned": N, "pages_fetched": N, "results_complete": true|false,
   "results_truncated": true|false}

examples:
  clickup tags usage personal
  clickup tags usage --space personal --tag urgent
  clickup tags usage personal --include-closed --include-archived --subtasks --all-pages""",
    )
    add_id_argument(tgu, "space", "Space name (from config) or raw space ID")
    tgu.add_argument(
        "--tag",
        type=str,
        help="Tag name to audit (omit to audit every tag in the space)",
    )
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
Use --strict-tags to require an existing space tag. Without strict mode,
ClickUp may create an unknown tag implicitly. The strict_tags config setting
provides an optional default, overridden by --strict-tags/--no-strict-tags.

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
    add_strict_tag_flags(tga)

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

    edit = tags_sub.add_parser(
        "edit", formatter_class=F, help="Rename or recolor a Space tag",
        description="""Rename or recolor a Space tag. At least one change flag is required.
Unspecified values are read from the current tag. A missing source or a name
collision fails before mutation. Dry-run performs safe GET lookups only.
Use migrate instead of edit when merging tags into an existing target.""",
        epilog='Example: clickup --dry-run tags edit --space <space> --tag source --name target\n'
               'Returns: status, action, space_id and tag; dry-run includes current and body.',
    )
    edit.add_argument("--space", required=True, help="Space alias or raw ID")
    edit.add_argument("--tag", required=True, help="Current tag name (auto-lowercased)")
    edit.add_argument("--name", help="New tag name (auto-lowercased)")
    edit.add_argument("--fg-color", help="Foreground color: #RGB or #RRGGBB")
    edit.add_argument("--bg-color", help="Background color: #RGB or #RRGGBB")

    migrate = tags_sub.add_parser(
        "migrate", formatter_class=F, help="Apply an exhaustive Space tag migration from JSON",
        description='''Map source tags to arrays of existing targets: {"source": ["target"], "drop": []}.
Sources and targets must exist and cannot overlap. Missing targets are never
created. Always scans closed tasks, archived lists/tasks, subtasks and all pages;
an incomplete scan prevents execution. Adds missing targets before removals.
--delete-old deletes sources only after a fresh complete zero-usage scan and
only when every task operation succeeded. No rollback is attempted on failure.
Dry-run reads live state but makes zero mutating calls. It returns every task
ID/name and ordered operation, planned source deletions, totals and scan metadata.
Live output retains the bulk completed/failed/remaining/resume_from contract,
plus deleted_space_tags and pending_space_tag_deletions. Rerun the map to build
a fresh plan after failure; a map whose sources were deleted fails validation.''',
        epilog="""examples:
  clickup --dry-run tags migrate --space <space> --map migration.json --delete-old
  clickup tags migrate --space <space> --map migration.json --continue-on-error""",
    )
    migrate.add_argument("--space", required=True, help="Space alias or raw ID")
    migrate.add_argument("--map", required=True, dest="map_file", help="JSON source-to-target-array map file")
    migrate.add_argument("--delete-old", action="store_true", help="Delete unused source tags after successful migration")
    migrate.add_argument("--continue-on-error", action="store_true", help="Continue with other tasks after a task failure")


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


def _scan_space_tasks(client, args, require_complete=False):
    """Share hierarchy discovery between usage audits and exhaustive migrations."""
    include_archived = getattr(args, "include_archived", False)
    space_id = resolve_space_id(args.space, spaces=client.runtime.spaces)
    if require_complete:
        space = client.get_v2(f"/space/{space_id}", allow_dry_run=True)
        if str(space.get("id")) != str(space_id) or space.get("archived"):
            error("Cannot establish scan completeness for an inaccessible or archived Space")
    list_ids = _resolve_scope_list_ids(
        client,
        args.space,
        allow_empty=include_archived,
        require_complete=require_complete,
    )
    if include_archived:
        archived_list_ids = _resolve_scope_list_ids(
            client,
            args.space,
            include_archived=True,
            allow_empty=True,
            require_complete=require_complete,
        )
        active_folder_response = client.get_v2(
            f"/space/{space_id}/folder", allow_dry_run=True
        )
        archived_active_folder_list_ids = []
        for folder in _scope_items(active_folder_response, "folders", require_complete):
            folder_lists_response = client.get_v2(
                f"/folder/{folder['id']}/list",
                params={"archived": "true"},
                allow_dry_run=True,
            )
            archived_active_folder_list_ids.extend(
                item["id"] for item in _scope_items(folder_lists_response, "lists", require_complete)
            )
        list_ids = list(
            dict.fromkeys(list_ids + archived_list_ids + archived_active_folder_list_ids)
        )
        if require_complete:
            archived_folders = client.get_v2(
                f"/space/{space_id}/folder", params={"archived": "true"}, allow_dry_run=True
            )
            for folder in _scope_items(archived_folders, "folders", True):
                active_lists = client.get_v2(
                    f"/folder/{folder['id']}/list", params={"archived": "false"}, allow_dry_run=True
                )
                list_ids.extend(item["id"] for item in _scope_items(active_lists, "lists", True))
            list_ids = list(dict.fromkeys(list_ids))

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
        result = _paginate_tasks(client, f"/list/{list_id}/task", dict(params), budget=budget,
                                 require_complete=require_complete)
        all_tasks.extend(result["tasks"])
        pages_fetched += result["pages_fetched"]
        complete = complete and result["complete"]
        if include_archived:
            archived_params = dict(params)
            archived_params["archived"] = "true"
            result = _paginate_tasks(client, f"/list/{list_id}/task", archived_params, budget=budget,
                                     require_complete=require_complete)
            all_tasks.extend(result["tasks"])
            pages_fetched += result["pages_fetched"]
            complete = complete and result["complete"]

    return {"tasks": all_tasks, "lists_scanned": len(list_ids), "pages_fetched": pages_fetched,
            "results_complete": complete, "results_truncated": not complete}


def cmd_tags_usage(client, args):
    """Audit task usage for one Space tag, or every tag in the space."""
    tag_name = args.tag.lower() if getattr(args, "tag", None) is not None else None
    scan = _scan_space_tasks(client, args)
    all_tasks = scan.pop("tasks")
    space_id = resolve_space_id(args.space, spaces=client.runtime.spaces)

    if tag_name is not None:
        matching = _filter_by_tags(all_tasks, [tag_name])
        tasks = [compact_task(task) for task in matching]
        return {
            "tag": tag_name,
            "count": len(tasks),
            "tasks": tasks,
            **scan,
        }

    space_tags = client.get_v2(f"/space/{space_id}/tag", allow_dry_run=True).get("tags", [])
    counts = {tag["name"].lower(): 0 for tag in space_tags}
    for task in all_tasks:
        for tag in task.get("tags", []):
            name = tag["name"].lower()
            if name in counts:
                counts[name] += 1
    tags = [
        {"name": name, "count": counts[name]}
        for name in sorted(counts, key=lambda name: (-counts[name], name))
    ]
    return {
        "tags": tags,
        "count": len(tags),
        **scan,
    }


def _tag_action(client, args, method, dry_action, done_action):
    """Shared logic for tag add/remove."""
    tag_name = args.tag.lower()
    if client.dry_run:
        return {"dry_run": True, "action": dry_action, "task_id": args.task_id, "tag": tag_name}
    method(f"/task/{args.task_id}/tag/{quote(tag_name, safe='')}", **({"data": {}} if method == client.post_v2 else {}))
    return {"status": "ok", "action": done_action, "task_id": args.task_id, "tag": tag_name}


def cmd_tags_add(client, args):
    """Add a tag to a task."""
    if strict_tags_enabled(client, args):
        validate_space_tags(client, space_for_task(client, args.task_id), [args.tag])
    return _tag_action(client, args, client.post_v2, "add_tag", "tag_added")


def cmd_tags_remove(client, args):
    """Remove a tag from a task."""
    return _tag_action(client, args, client.delete_v2, "remove_tag", "tag_removed")


def _space_tags(client, space_id):
    response = client.get_v2(f"/space/{space_id}/tag", allow_dry_run=True)
    if not isinstance(response.get("tags"), list):
        error(f"Cannot read the tag inventory for space {space_id}")
    return {tag["name"].lower(): tag for tag in response["tags"]}


def _color(value):
    if not isinstance(value, str) or not re.fullmatch(r"#[0-9a-fA-F]{3}(?:[0-9a-fA-F]{3})?", value):
        error("Tag colors must use #RGB or #RRGGBB")
    value = value.lower()
    return "#" + "".join(char * 2 for char in value[1:]) if len(value) == 4 else value


def cmd_tags_edit(client, args):
    if not any(value is not None for value in (args.name, args.fg_color, args.bg_color)):
        error("Provide at least one of --name, --fg-color, or --bg-color")
    source = args.tag.lower()
    name = args.name.lower() if args.name is not None else source
    if not source.strip() or not name.strip():
        error("Tag names cannot be empty")
    colors = {key: _color(value) for key, value in
              (("tag_fg", args.fg_color), ("tag_bg", args.bg_color)) if value is not None}
    space_id = resolve_space_id(args.space, spaces=client.runtime.spaces)
    inventory = _space_tags(client, space_id)
    if source not in inventory:
        error(f"Source tag does not exist: {source}")
    if name != source and name in inventory:
        error(f"Target tag already exists: {name}. Use tags migrate to merge tags.")
    current = inventory[source]
    body = {"tag": {"name": name, **{key: colors.get(key, current.get(key))
                                    for key in ("tag_fg", "tag_bg")}}}
    if any(value is None for value in body["tag"].values()):
        error("Current tag colors are unavailable; provide both color flags")
    if client.dry_run:
        return {"dry_run": True, "action": "edit_space_tag", "space_id": space_id,
                "current": current, "body": body}
    client.put_v2(f"/space/{space_id}/tag/{quote(source, safe='')}", data=body)
    updated = _space_tags(client, space_id).get(name)
    if not updated or any(updated.get(key) != value for key, value in body["tag"].items()):
        error("Tag edit could not be verified; inspect tags list before retrying")
    return {"status": "ok", "action": "space_tag_edited", "space_id": space_id, "tag": updated}


def _load_tag_map(path):
    def unique_keys(pairs):
        result = {}
        for key, value in pairs:
            if key.lower() in result:
                raise ValueError(f"Duplicate source tag: {key}")
            result[key.lower()] = value
        return result

    try:
        with open(path, encoding="utf-8") as handle:
            raw = json.load(handle, object_pairs_hook=unique_keys)
    except (OSError, ValueError) as exc:
        error(f"Invalid tag map: {exc}")
    if not isinstance(raw, dict) or not raw:
        error("Invalid tag map: expected a non-empty source-to-target-array object")
    mapping = {}
    for source, targets in raw.items():
        if (not source.strip() or not isinstance(targets, list)
                or any(not isinstance(tag, str) or not tag.strip() for tag in targets)):
            error("Invalid tag map: non-empty tag names and target arrays are required")
        mapping[source] = list(dict.fromkeys(tag.lower() for tag in targets))
    if set(mapping) & {target for targets in mapping.values() for target in targets}:
        error("Invalid tag map: targets must not also be sources (including self-maps)")
    return mapping


def cmd_tags_migrate(client, args):
    mapping = _load_tag_map(args.map_file)
    space_id = resolve_space_id(args.space, spaces=client.runtime.spaces)
    required = set(mapping) | {target for targets in mapping.values() for target in targets}
    validate_space_tags(client, space_id, required)
    scan_args = Namespace(space=args.space, include_archived=True, include_closed=True,
                          subtasks=True, all_pages=True)
    scan = _scan_space_tasks(client, scan_args, require_complete=True)
    tasks = {task["id"]: task for task in scan.pop("tasks")}
    if not scan["results_complete"]:
        error("Refusing tag migration: task scan is incomplete")
    plan = {"tasks": [], "space_tag_deletions": list(mapping) if args.delete_old else []}
    for task_id, task in tasks.items():
        present = {tag["name"].lower() for tag in task.get("tags", [])}
        sources = [source for source in mapping if source in present]
        targets = list(dict.fromkeys(target for source in sources for target in mapping[source]))
        operations = ([{"action": "add", "tag": tag} for tag in targets if tag not in present]
                      + [{"action": "remove", "tag": source} for source in sources])
        if operations:
            plan["tasks"].append({"task_id": task_id, "task_name": task.get("name", ""),
                                  "operations": operations})
    totals = {"tasks": len(plan["tasks"]), "space_tag_deletions": len(plan["space_tag_deletions"]),
              **{action: sum(op["action"] == action for task in plan["tasks"] for op in task["operations"])
                 for action in ("add", "remove")}}
    if client.dry_run:
        return {"dry_run": True, "action": "migrate_tags", "plan": plan, "totals": totals, **scan}
    result = _execute_bulk_tag_plan(client, plan, args.continue_on_error)
    result.update(action="migrate_tags", totals=totals, deleted_space_tags=[],
                  pending_space_tag_deletions=list(plan["space_tag_deletions"]), **scan)
    if args.delete_old and not result["failed"]:
        for source in mapping:
            messages = StringIO()
            try:
                with redirect_stderr(messages):
                    fresh = _scan_space_tasks(client, scan_args, require_complete=True)
                    if not fresh["results_complete"] or _filter_by_tags(fresh["tasks"], [source]):
                        error("Fresh scan did not prove zero usage")
                    client.delete_v2(f"/space/{space_id}/tag/{quote(source, safe='')}")
            except (Exception, SystemExit) as exc:  # noqa: BLE001 - retain deletion failures
                result["failed"].append({"tag": source, "error": messages.getvalue().strip() or str(exc)})
                break
            finally:
                sys.stderr.write(messages.getvalue())
            result["deleted_space_tags"].append(source)
            result["pending_space_tag_deletions"].remove(source)
    if result["failed"]:
        result["status"] = "partial_failure"
    return result

COMMAND_MANIFEST = {
    "group": "tags",
    "register_parser": register_parser,
    "handlers": {
        "list": cmd_tags_list,
        "create": cmd_tags_create,
        "edit": cmd_tags_edit,
        "migrate": cmd_tags_migrate,
        "delete": cmd_tags_delete,
        "usage": cmd_tags_usage,
        "add": cmd_tags_add,
        "remove": cmd_tags_remove,
    },
}
