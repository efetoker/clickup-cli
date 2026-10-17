"""Shared opt-in validation for task tag additions."""

from .helpers import error


def add_strict_tag_flags(parser):
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--strict-tags", action="store_true", default=None,
                       help="Reject unknown space tags before any mutation, including dry-run; strict_tags config defaults to false")
    group.add_argument("--no-strict-tags", dest="strict_tags", action="store_false",
                       help="Allow implicit tag creation, overriding the strict_tags config default")


def strict_tags_enabled(client, args):
    explicit = getattr(args, "strict_tags", None)
    if isinstance(explicit, bool):
        return explicit
    return getattr(client.runtime, "strict_tags", False) is True


def space_for_list(client, list_id):
    response = client.get_v2(f"/list/{list_id}", allow_dry_run=True)
    space_id = (response.get("space") or {}).get("id")
    if not space_id:
        error(f"Cannot resolve the space for list {list_id}")
    return str(space_id)


def space_for_task(client, task_id):
    task = client.get_v2(f"/task/{task_id}", allow_dry_run=True)
    space_id = (task.get("space") or {}).get("id")
    if space_id:
        return str(space_id)
    list_id = (task.get("list") or {}).get("id")
    if not list_id:
        error(f"Cannot resolve the space for task {task_id}")
    return space_for_list(client, list_id)


def validate_space_tags(client, space_id, tags, inventories=None):
    inventories = inventories if inventories is not None else {}
    if space_id not in inventories:
        response = client.get_v2(f"/space/{space_id}/tag", allow_dry_run=True)
        if not isinstance(response.get("tags"), list):
            error(f"Cannot read the tag inventory for space {space_id}")
        inventories[space_id] = {tag["name"].lower() for tag in response["tags"]}
    unknown = sorted({tag.lower() for tag in tags} - inventories[space_id])
    if unknown:
        error(f"Unknown tags in space {space_id}: {', '.join(unknown)}. Create them with tags create first.")


def validate_task_tag_plan(client, plan):
    inventories = {}
    for task in plan["tasks"]:
        additions = [op["tag"] for op in task["operations"] if op["action"] == "add"]
        if additions:
            validate_space_tags(client, space_for_task(client, task["task_id"]), additions, inventories)
