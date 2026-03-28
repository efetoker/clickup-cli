"""Command handler registry — maps dispatch keys to handler functions."""

from .tasks import (
    cmd_tasks_list, cmd_tasks_get, cmd_tasks_create,
    cmd_tasks_update, cmd_tasks_search,
    cmd_tasks_delete, cmd_tasks_move, cmd_tasks_merge,
)
from .comments import (
    cmd_comments_list, cmd_comments_add,
    cmd_comments_update, cmd_comments_delete,
    cmd_comments_thread, cmd_comments_reply,
)
from .docs import (
    cmd_docs_list, cmd_docs_get, cmd_docs_create, cmd_docs_pages,
    cmd_docs_get_page, cmd_docs_edit_page, cmd_docs_create_page,
)
from .spaces import cmd_spaces_list, cmd_spaces_get, cmd_spaces_statuses
from .team import cmd_team_whoami, cmd_team_members
from .tags import cmd_tags_list, cmd_tags_add, cmd_tags_remove
from .folders import (
    cmd_folders_list, cmd_folders_get, cmd_folders_create,
    cmd_folders_update, cmd_folders_delete,
)
from .lists import (
    cmd_lists_list, cmd_lists_get, cmd_lists_create,
    cmd_lists_update, cmd_lists_delete,
)

# Keys use f"{args.group}_{args.command}" format from dispatch().
# Some keys retain hyphens matching argparse subparser names.
HANDLERS = {
    "tasks_list": cmd_tasks_list,
    "tasks_get": cmd_tasks_get,
    "tasks_create": cmd_tasks_create,
    "tasks_update": cmd_tasks_update,
    "tasks_search": cmd_tasks_search,
    "tasks_delete": cmd_tasks_delete,
    "tasks_move": cmd_tasks_move,
    "tasks_merge": cmd_tasks_merge,
    "comments_list": cmd_comments_list,
    "comments_add": cmd_comments_add,
    "comments_update": cmd_comments_update,
    "comments_delete": cmd_comments_delete,
    "comments_thread": cmd_comments_thread,
    "comments_reply": cmd_comments_reply,
    "docs_list": cmd_docs_list,
    "docs_get": cmd_docs_get,
    "docs_create": cmd_docs_create,
    "docs_pages": cmd_docs_pages,
    "docs_get-page": cmd_docs_get_page,
    "docs_edit-page": cmd_docs_edit_page,
    "docs_create-page": cmd_docs_create_page,
    "spaces_list": cmd_spaces_list,
    "spaces_get": cmd_spaces_get,
    "spaces_statuses": cmd_spaces_statuses,
    "team_whoami": cmd_team_whoami,
    "team_members": cmd_team_members,
    "tags_list": cmd_tags_list,
    "tags_add": cmd_tags_add,
    "tags_remove": cmd_tags_remove,
    "folders_list": cmd_folders_list,
    "folders_get": cmd_folders_get,
    "folders_create": cmd_folders_create,
    "folders_update": cmd_folders_update,
    "folders_delete": cmd_folders_delete,
    "lists_list": cmd_lists_list,
    "lists_get": cmd_lists_get,
    "lists_create": cmd_lists_create,
    "lists_update": cmd_lists_update,
    "lists_delete": cmd_lists_delete,
}
