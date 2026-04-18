"""Compatibility facade for task command entrypoints."""

from .tasks_internal.parser import register_parser as register_parser
from .tasks_internal.read import (
    cmd_tasks_get as cmd_tasks_get,
    cmd_tasks_list as cmd_tasks_list,
    cmd_tasks_search as cmd_tasks_search,
)
from .tasks_internal.write import (
    cmd_tasks_create as cmd_tasks_create,
    cmd_tasks_delete as cmd_tasks_delete,
    cmd_tasks_depend as cmd_tasks_depend,
    cmd_tasks_merge as cmd_tasks_merge,
    cmd_tasks_move as cmd_tasks_move,
    cmd_tasks_update as cmd_tasks_update,
)

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
        "depend": cmd_tasks_depend,
    },
}
