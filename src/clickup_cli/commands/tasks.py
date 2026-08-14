"""Compatibility facade for task command entrypoints."""

from .tasks_internal.parser import register_parser
from .tasks_internal.read import cmd_tasks_get, cmd_tasks_list, cmd_tasks_search
from .tasks_internal.write import (
    cmd_tasks_add_to_list,
    cmd_tasks_bulk,
    cmd_tasks_create,
    cmd_tasks_delete,
    cmd_tasks_depend,
    cmd_tasks_link,
    cmd_tasks_lists,
    cmd_tasks_merge,
    cmd_tasks_move,
    cmd_tasks_remove_from_list,
    cmd_tasks_update,
)

__all__ = [
    "COMMAND_MANIFEST",
    "cmd_tasks_add_to_list",
    "cmd_tasks_bulk",
    "cmd_tasks_create",
    "cmd_tasks_delete",
    "cmd_tasks_depend",
    "cmd_tasks_get",
    "cmd_tasks_link",
    "cmd_tasks_list",
    "cmd_tasks_lists",
    "cmd_tasks_merge",
    "cmd_tasks_move",
    "cmd_tasks_remove_from_list",
    "cmd_tasks_search",
    "cmd_tasks_update",
    "register_parser",
]

COMMAND_MANIFEST = {
    "group": "tasks",
    "register_parser": register_parser,
    "handlers": {
        "list": cmd_tasks_list,
        "get": cmd_tasks_get,
        "create": cmd_tasks_create,
        "update": cmd_tasks_update,
        "search": cmd_tasks_search,
        "delete": cmd_tasks_delete,
        "move": cmd_tasks_move,
        "merge": cmd_tasks_merge,
        "lists": cmd_tasks_lists,
        "add-to-list": cmd_tasks_add_to_list,
        "remove-from-list": cmd_tasks_remove_from_list,
        "bulk": cmd_tasks_bulk,
        "link": cmd_tasks_link,
        "depend": cmd_tasks_depend,
    },
}
