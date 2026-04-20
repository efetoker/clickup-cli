"""Internal task command modules."""

from .parser import register_parser as register_parser
from .read import (
    cmd_tasks_get as cmd_tasks_get,
    cmd_tasks_list as cmd_tasks_list,
    cmd_tasks_search as cmd_tasks_search,
)
from .write import (
    cmd_tasks_add_to_list as cmd_tasks_add_to_list,
    cmd_tasks_create as cmd_tasks_create,
    cmd_tasks_delete as cmd_tasks_delete,
    cmd_tasks_depend as cmd_tasks_depend,
    cmd_tasks_link as cmd_tasks_link,
    cmd_tasks_lists as cmd_tasks_lists,
    cmd_tasks_merge as cmd_tasks_merge,
    cmd_tasks_move as cmd_tasks_move,
    cmd_tasks_remove_from_list as cmd_tasks_remove_from_list,
    cmd_tasks_update as cmd_tasks_update,
)
