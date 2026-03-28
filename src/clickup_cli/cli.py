"""CLI parser, dispatch, and main entry point."""

import argparse
import os
import sys

from .client import ClickUpClient
from .helpers import output, error


GLOBAL_FLAGS = {"--pretty", "--dry-run", "--debug"}


def normalize_cli_argv(argv):
    """Allow global flags before or after the command group."""
    front = []
    rest = []

    for arg in argv:
        if arg in GLOBAL_FLAGS:
            if arg not in front:
                front.append(arg)
        else:
            rest.append(arg)

    return front + rest


def build_parser():
    F = argparse.RawDescriptionHelpFormatter

    parser = argparse.ArgumentParser(
        prog="clickup",
        formatter_class=F,
        description="""\
ClickUp CLI — manage tasks, comments, docs, folders, lists, spaces, and teams from the command line.

Covers eight command groups: tasks, comments, docs, folders, lists, spaces, team, and tags.
All successful output is JSON printed to stdout.
Errors are printed to stderr with a non-zero exit code.

Global flags can appear before or after the command group:
  clickup --pretty tasks list --space <name>
  clickup tasks list --space <name> --pretty
  clickup --dry-run tasks create --space <name> --name "My task"
  clickup --debug tasks list --space <name>""",
        epilog="""\
examples:
  clickup init                              # set up config
  clickup tasks list --space <name>
  clickup tasks list --list 12345
  clickup --dry-run tasks create --space <name> --name "Fix login"
  clickup folders list --space <name>
  clickup lists list --folder 12345
  clickup comments list abc123
  clickup docs pages doc_abc123

current coverage:
  tasks     — list, get, create, update, search, delete, move, merge
  comments  — list, add, update, delete, thread, reply
  docs      — list, get, create, pages, get-page, edit-page, create-page
  folders   — list, get, create, update, delete
  lists     — list, get, create, update, delete
  spaces    — list, get, statuses
  team      — whoami, members
  tags      — list, add, remove

Use <group> --help for details on each group.""",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print JSON output with indentation",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview the API request without executing it (safe for mutations)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Log API requests and responses to stderr for troubleshooting",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {_get_version()}",
    )

    subparsers = parser.add_subparsers(dest="group", required=True)

    # ---------------------------------------------------------------
    # init
    # ---------------------------------------------------------------
    init_parser = subparsers.add_parser(
        "init",
        formatter_class=F,
        help="Set up ClickUp CLI configuration",
        description="""\
Set up the ClickUp CLI by connecting to your workspace.

Fetches your workspaces and spaces, then writes a config file to
~/.config/clickup-cli/config.json.

Run interactively (prompts for token) or pass --token for automation.""",
        epilog="""\
examples:
  clickup init
  clickup init --token pk_YOUR_API_TOKEN""",
    )
    init_parser.add_argument(
        "--token",
        type=str,
        help="ClickUp API token (skips interactive prompt)",
    )

    # ---------------------------------------------------------------
    # tasks
    # ---------------------------------------------------------------
    tasks_parser = subparsers.add_parser(
        "tasks",
        formatter_class=F,
        help="Full task CRUD: list, get, create, update, search, delete, move, merge",
        description="""\
Manage ClickUp tasks — full CRUD plus search, move, and merge.

Subcommands:
  list    — list tasks in a list or space (paginated internally)
  get     — fetch one task by ID
  create  — create a new task in a list or space (mutating)
  update  — update fields on an existing task (mutating)
  search  — search tasks by query across workspace or within a space
  delete  — delete a task (destructive)
  move    — move a task to a different list/space (mutating, v3)
  merge   — merge source tasks into a target task (mutating)

Tasks live in lists. Each space has a default list, but you can also
target a specific list (e.g. one inside a folder) using --list <id>.
Use 'folders list' and 'lists list' to discover list IDs.

Does not cover: checklists, custom fields, time tracking, or attachments.""",
        epilog="""\
examples:
  clickup tasks list --space <name>
  clickup tasks list --list 12345
  clickup tasks get abc123
  clickup --dry-run tasks create --space <name> --name "New feature"
  clickup tasks create --space <name> --list 12345 --name "In a folder list"
  clickup tasks search "login bug" --space <name>
  clickup tasks list --space <name> --subtasks
  clickup tasks search "bug" --list 12345""",
    )
    tasks_sub = tasks_parser.add_subparsers(dest="command", required=True)

    # tasks list
    tl = tasks_sub.add_parser(
        "list",
        formatter_class=F,
        help="List tasks in a list or space",
        description="""\
List all tasks in a list. Results are paginated internally and returned
as a single JSON object with a tasks array and count.

By default, output is compact (id, name, status, priority, url).
Use --full for the raw API response, or --fields to pick specific fields.

Target the list using --space (uses the space's default list) or
--list (targets a specific list ID, e.g. one inside a folder).
If both are given, --list takes precedence.

Use --subtasks to include nested child tasks in the results. Without it,
only top-level tasks are returned (ClickUp API default).

Use this when you need to see all tasks, optionally filtered by status
or including closed tasks.""",
        epilog="""\
returns:
  {"tasks": [...], "count": N}

examples:
  clickup tasks list --space <name>
  clickup tasks list --space <name> --full
  clickup tasks list --space <name> --fields id,name,url
  clickup tasks list --space <name> --include-closed
  clickup tasks list --space <name> --status "in progress"
  clickup tasks list --space <name> --subtasks

notes:
  Output is compact by default (id, name, status, priority, url).
  Use --full for raw API response, or --fields for custom field selection.
  At least one of --space or --list is required.
  If both are given, --list takes precedence.
  Use --subtasks to include nested child tasks (e.g. Epic/Story/Task hierarchies).
  Use 'lists list --folder <id>' or 'lists list --space <name>' to
  discover list IDs for lists inside folders.
  Status values are space-specific. Check the space configuration
  for valid status names before filtering.""",
    )
    tl.add_argument(
        "--space",
        type=str,
        help="Space name (from config) or raw space ID — uses the space's default list",
    )
    tl.add_argument(
        "--list",
        type=str,
        dest="list_id",
        help="Raw list ID — targets a specific list (overrides --space)",
    )
    tl.add_argument(
        "--include-closed",
        action="store_true",
        help="Include closed/completed tasks in results",
    )
    tl.add_argument(
        "--status", type=str, help="Filter tasks by status name (space-specific)"
    )
    tl.add_argument(
        "--subtasks",
        action="store_true",
        help="Include subtasks (nested child tasks) in results",
    )
    tl.add_argument(
        "--fields",
        type=str,
        help="Comma-separated list of fields to return per task (e.g. id,name,status,url)",
    )
    tl.add_argument(
        "--full",
        action="store_true",
        help="Return full raw API response (default is compact: id, name, status, priority, url)",
    )

    # tasks get
    tg = tasks_sub.add_parser(
        "get",
        formatter_class=F,
        help="Fetch one task by ID (includes comments by default)",
        description="""\
Fetch a single task by its ClickUp task ID.

By default, comments are fetched and appended to the task output under
a "comments" key (array of {id, comment_text, user, date}) and a
"comment_count" field. This ensures task context is always complete
without needing a separate comments list call.

Use --no-comments to suppress comment fetching if output is too verbose
or you only need the task fields.""",
        epilog="""\
returns:
  One task JSON object with all fields, plus:
    "comments": [{id, comment_text, user, date}, ...]
    "comment_count": N

  With --no-comments, returns the raw task object without comments.

examples:
  clickup tasks get abc123
  clickup --pretty tasks get abc123
  clickup tasks get abc123 --no-comments""",
    )
    tg.add_argument("task_id", type=str, help="ClickUp task ID")
    tg.add_argument(
        "--no-comments",
        action="store_true",
        help="Skip auto-fetching comments (default: comments included)",
    )

    # tasks create
    tc = tasks_sub.add_parser(
        "create",
        formatter_class=F,
        help="Create a new task in a list or space",
        description="""\
Create a new task in a list. This is a mutating command.

--space is always required (used to resolve the target list).
By default, the task is created in the space's default list. Use --list
to target a specific list instead (e.g. one inside a folder).

Tags are applied automatically based on config (default_tags, draft_tag).

Use --desc for inline text or --desc-file for file-based content.
Do not use both at the same time.

Use --dry-run to preview the request body without creating the task.
Global flags may appear before or after the command group:
  clickup --dry-run tasks create --space <name> --name "My task"
  clickup tasks create --space <name> --name "My task" --dry-run""",
        epilog="""\
returns:
  The created task object from the API.

examples:
  clickup tasks create --space <name> --name "Add login page"
  clickup tasks create --space <name> --name "Fix bug" --desc "Details here"
  clickup tasks create --space <name> --list 12345 --name "In folder list"
  clickup tasks create --space <name> --name "Read article" --desc-file notes.md
  clickup --dry-run tasks create --space <name> --name "Test" --good-as-is

notes:
  --space is always required (to resolve target list). --list is optional.
  If --list is given, the task is created in that list instead of the
  space's default list.
  --desc and --desc-file are mutually exclusive. Using both is an error.
  --good-as-is marks the task as intentionally simple (no draft tag).
  --no-assign skips the default assignee.
  --priority defaults to the value in your config (default: low).
  Does not support: checklists, custom fields, attachments, or due dates.""",
    )
    tc.add_argument(
        "--space",
        required=True,
        type=str,
        help="Target space (required)",
    )
    tc.add_argument(
        "--list",
        type=str,
        dest="list_id",
        help="Raw list ID — creates task in this list (overrides space default)",
    )
    tc.add_argument(
        "--name",
        required=True,
        help="Task title (required)",
    )
    tc.add_argument(
        "--desc",
        type=str,
        help="Inline description text (mutually exclusive with --desc-file)",
    )
    tc.add_argument(
        "--desc-file", type=str, help="Path to a file containing description content"
    )
    tc.add_argument("--status", type=str, help="Initial task status (space-specific)")
    tc.add_argument(
        "--priority",
        type=str,
        help="Priority: urgent, high, normal, low (default: from config)",
    )
    tc.add_argument("--no-assign", action="store_true", help="Skip default assignee")
    tc.add_argument(
        "--good-as-is",
        action="store_true",
        help="Mark task as intentionally simple (no draft tag)",
    )
    tc.add_argument(
        "--skip-dedup",
        action="store_true",
        default=False,
        help="Skip duplicate check and create the task even if one with the same name exists",
    )

    # tasks update
    tu = tasks_sub.add_parser(
        "update",
        formatter_class=F,
        help="Update fields on an existing task",
        description="""\
Update one or more fields on an existing task. This is a mutating command.

At least one mutable field is required: --name, --status, --priority,
--desc, or --desc-file. If none are provided, the command exits with an error.

Use --desc for inline text or --desc-file for file-based content.
Do not use both at the same time.

Use --dry-run to preview the request body without applying changes.
Global flags may appear before or after the command group:
  clickup --dry-run tasks update abc123 --status "complete" """,
        epilog="""\
returns:
  The updated task object from the API.

examples:
  clickup tasks update abc123 --name "Renamed task"
  clickup tasks update abc123 --status "complete"
  clickup tasks update abc123 --desc-file updated_spec.md
  clickup --dry-run tasks update abc123 --status "in progress"

notes:
  --desc and --desc-file are mutually exclusive. Using both is an error.
  Does not support: changing assignees, tags, or custom fields.""",
    )
    tu.add_argument("task_id", type=str, help="ClickUp task ID to update")
    tu.add_argument("--name", type=str, help="New task name")
    tu.add_argument("--status", type=str, help="New status (space-specific)")
    tu.add_argument(
        "--priority", type=str, help="Priority: urgent, high, normal, low (or 1-4)"
    )
    tu.add_argument(
        "--desc",
        type=str,
        help="Inline description text (mutually exclusive with --desc-file)",
    )
    tu.add_argument(
        "--desc-file", type=str, help="Path to a file containing description content"
    )

    # tasks search
    ts = tasks_sub.add_parser(
        "search",
        formatter_class=F,
        help="Search tasks by query string",
        description="""\
Search tasks across the workspace by a text query.

Results are paginated internally and returned as a single JSON object.
By default, output is compact (id, name, status, priority, url).
Use --full for the raw API response, or --fields to pick specific fields.

Use --space, --list, or --folder to scope results. Without any scope
filter, results may include tasks from all spaces.

When the query looks like a task ID (e.g. PROJ-39, PROJ-12), --name-prefix
is auto-applied to filter exact matches. Use --name-prefix explicitly for
other prefix-based filtering.""",
        epilog="""\
returns:
  {"tasks": [...], "count": N}

examples:
  clickup tasks search "login bug"
  clickup tasks search "PROJ-39" --space <name>
  clickup tasks search "PROJ-8" --space <name>
  clickup tasks search "PROJ" --space <name> --name-prefix "PROJ-9"
  clickup tasks search "deploy" --include-closed --full
  clickup tasks search "bug" --fields id,name,url
  clickup tasks search "bug" --list 12345

notes:
  Output is compact by default (id, name, status, priority, url).
  Use --full for raw API response, or --fields for custom field selection.
  Queries matching the pattern ABC-123 auto-apply --name-prefix.
  Use --space, --list, or --folder to scope results.
  --name-prefix filters the returned tasks client-side by task name prefix.
  The search API has a default page size — this CLI handles pagination
  automatically and returns all matching results.""",
    )
    ts.add_argument("query", type=str, help="Search query string")
    ts.add_argument(
        "--include-closed",
        action="store_true",
        help="Include closed/completed tasks in results",
    )
    ts.add_argument(
        "--space", type=str, help="Scope search to a specific space"
    )
    ts.add_argument(
        "--list", type=str, dest="list_id", help="Scope search to a specific list ID"
    )
    ts.add_argument(
        "--folder",
        type=str,
        dest="folder_id",
        help="Scope search to a specific folder ID (ClickUp calls this project_ids)",
    )
    ts.add_argument(
        "--name-prefix",
        type=str,
        help="Keep only tasks whose name starts with this prefix (client-side filter)",
    )
    ts.add_argument(
        "--fields",
        type=str,
        help="Comma-separated list of fields to return per task (e.g. id,name,status,url)",
    )
    ts.add_argument(
        "--full",
        action="store_true",
        help="Return full raw API response (default is compact: id, name, status, priority, url)",
    )

    # tasks delete
    td = tasks_sub.add_parser(
        "delete",
        formatter_class=F,
        help="Delete a task (destructive)",
        description="""\
Delete a task permanently. This is a destructive, irreversible command.

Use --dry-run to preview the operation without deleting anything.
Global flags may appear before or after the command group:
  clickup --dry-run tasks delete abc123""",
        epilog="""\
returns:
  {"status": "ok", "action": "deleted", "task_id": "..."}

examples:
  clickup --dry-run tasks delete abc123
  clickup tasks delete abc123""",
    )
    td.add_argument("task_id", type=str, help="ClickUp task ID to delete")

    # tasks move
    tm = tasks_sub.add_parser(
        "move",
        formatter_class=F,
        help="Move a task to a different list/space",
        description="""\
Move a task to a different list. This is a mutating command (v3 API).

The destination can be a configured space name — which resolves
to that space's default list — or a raw ClickUp list ID.

For tasks in multiple lists, this changes the home list only.

Use --dry-run to preview without moving.
Global flags may appear before or after the command group:
  clickup --dry-run tasks move abc123 --to <space-or-list-id>""",
        epilog="""\
returns:
  The updated task object from the API.

examples:
  clickup tasks move abc123 --to <space-or-list-id>
  clickup tasks move abc123 --to 901816700000
  clickup --dry-run tasks move abc123 --to <space-or-list-id>""",
    )
    tm.add_argument("task_id", type=str, help="ClickUp task ID to move")
    tm.add_argument(
        "--to",
        required=True,
        dest="to_list",
        help="Destination space name or raw list ID",
    )

    # tasks merge
    tmg = tasks_sub.add_parser(
        "merge",
        formatter_class=F,
        help="Merge source tasks into a target task",
        description="""\
Merge one or more source tasks into a target task. This is a mutating command.

The source tasks are absorbed into the target. Their comments, attachments,
and activity are consolidated. Source tasks are removed after merging.

Use --dry-run to preview without merging.
Global flags may appear before or after the command group:
  clickup --dry-run tasks merge abc123 --sources def456,ghi789""",
        epilog="""\
returns:
  The merged task object from the API.

examples:
  clickup tasks merge abc123 --sources def456
  clickup tasks merge abc123 --sources def456,ghi789
  clickup --dry-run tasks merge abc123 --sources def456""",
    )
    tmg.add_argument("task_id", type=str, help="Target task ID (tasks merge into this)")
    tmg.add_argument(
        "--sources",
        required=True,
        dest="source_ids",
        help="Comma-separated source task IDs to merge into the target",
    )

    # ---------------------------------------------------------------
    # comments
    # ---------------------------------------------------------------
    comments_parser = subparsers.add_parser(
        "comments",
        formatter_class=F,
        help="Full comment CRUD: list, add, update, delete, thread, reply",
        description="""\
Manage task comments — full CRUD plus threaded replies.

Subcommands:
  list    — list comments on a task
  add     — add a comment to a task (mutating)
  update  — edit an existing comment (mutating)
  delete  — delete a comment (destructive)
  thread  — get threaded replies to a comment
  reply   — reply to a comment in a thread (mutating)""",
        epilog="""\
examples:
  clickup comments list abc123
  clickup comments add abc123 --text "Work complete"
  clickup --dry-run comments add abc123 --file report.md""",
    )
    comments_sub = comments_parser.add_subparsers(dest="command", required=True)

    # comments list
    cl = comments_sub.add_parser(
        "list",
        formatter_class=F,
        help="List comments on a task",
        description="""\
List comments on a task. By default returns the first page (up to 25).
Use --all to paginate through every comment on the task.

Use this when you need to read discussion or work logs on a task.""",
        epilog="""\
returns:
  {"comments": [...], "count": N}

examples:
  clickup comments list abc123
  clickup comments list abc123 --all
  clickup --pretty comments list abc123""",
    )
    cl.add_argument("task_id", type=str, help="ClickUp task ID")
    cl.add_argument(
        "--all",
        action="store_true",
        dest="fetch_all",
        help="Fetch all comment pages (default: first page only)",
    )

    # comments add
    ca = comments_sub.add_parser(
        "add",
        formatter_class=F,
        help="Add a comment to a task",
        description="""\
Add a comment to a task. This is a mutating command.

Exactly one of --text or --file is required.
Use --text for short inline comments. Use --file to post content from
a file (useful for longer markdown or structured logs).

Use --dry-run to preview the request body without posting the comment.
Global flags may appear before or after the command group:
  clickup --dry-run comments add abc123 --text "Preview this" """,
        epilog="""\
returns:
  The created comment object from the API.

examples:
  clickup comments add abc123 --text "Task complete"
  clickup comments add abc123 --file session_log.md
  clickup --dry-run comments add abc123 --text "Test comment"

notes:
  --text and --file are mutually exclusive. Using both is an error.""",
    )
    ca.add_argument("task_id", type=str, help="ClickUp task ID")
    ca.add_argument(
        "--text", type=str, help="Inline comment text (mutually exclusive with --file)"
    )
    ca.add_argument(
        "--file", type=str, help="Path to a file containing comment content"
    )

    # comments update
    cu = comments_sub.add_parser(
        "update",
        formatter_class=F,
        help="Edit an existing comment",
        description="""\
Edit an existing comment's text or resolved status. This is a mutating command.

At least one change is required: --text/--file for new text, or
--resolve/--unresolve to change the resolved state.

Use --dry-run to preview without applying changes.
Global flags may appear before or after the command group:
  clickup --dry-run comments update 456 --text "Fixed text" """,
        epilog="""\
returns:
  {"status": "ok", "action": "updated", "comment_id": "..."}

examples:
  clickup comments update 456 --text "Corrected info"
  clickup comments update 456 --file updated_notes.md
  clickup comments update 456 --resolve
  clickup --dry-run comments update 456 --text "Test"

notes:
  --text and --file are mutually exclusive. Using both is an error.
  --resolve and --unresolve are mutually exclusive.""",
    )
    cu.add_argument("comment_id", type=str, help="ClickUp comment ID")
    cu.add_argument(
        "--text", type=str, help="New comment text (mutually exclusive with --file)"
    )
    cu.add_argument(
        "--file", type=str, help="Path to a file containing new comment text"
    )
    resolve_group = cu.add_mutually_exclusive_group()
    resolve_group.add_argument(
        "--resolve",
        action="store_const",
        const=True,
        dest="resolved",
        help="Mark the comment as resolved",
    )
    resolve_group.add_argument(
        "--unresolve",
        action="store_const",
        const=False,
        dest="resolved",
        help="Mark the comment as unresolved",
    )

    # comments delete
    cd = comments_sub.add_parser(
        "delete",
        formatter_class=F,
        help="Delete a comment (destructive)",
        description="""\
Delete a comment permanently. This is a destructive, irreversible command.

Use --dry-run to preview the operation without deleting anything.
Global flags may appear before or after the command group:
  clickup --dry-run comments delete 456""",
        epilog="""\
returns:
  {"status": "ok", "action": "deleted", "comment_id": "..."}

examples:
  clickup --dry-run comments delete 456
  clickup comments delete 456""",
    )
    cd.add_argument("comment_id", type=str, help="ClickUp comment ID to delete")

    # comments thread
    ct = comments_sub.add_parser(
        "thread",
        formatter_class=F,
        help="Get threaded replies to a comment",
        description="""\
Get all threaded replies to a specific comment. The parent comment is NOT
included in the response — only the replies.

Use this to read conversation threads on tasks.""",
        epilog="""\
returns:
  {"replies": [...], "count": N}

examples:
  clickup comments thread 456
  clickup --pretty comments thread 456""",
    )
    ct.add_argument("comment_id", type=str, help="Parent comment ID")

    # comments reply
    cr = comments_sub.add_parser(
        "reply",
        formatter_class=F,
        help="Reply to a comment in a thread",
        description="""\
Post a threaded reply to a specific comment. This is a mutating command.

Exactly one of --text or --file is required.

Use --dry-run to preview without posting.
Global flags may appear before or after the command group:
  clickup --dry-run comments reply 456 --text "Preview" """,
        epilog="""\
returns:
  The created reply object from the API.

examples:
  clickup comments reply 456 --text "Agreed, let's proceed"
  clickup comments reply 456 --file detailed_response.md
  clickup --dry-run comments reply 456 --text "Test reply"

notes:
  --text and --file are mutually exclusive. Using both is an error.""",
    )
    cr.add_argument("comment_id", type=str, help="Parent comment ID to reply to")
    cr.add_argument(
        "--text", type=str, help="Inline reply text (mutually exclusive with --file)"
    )
    cr.add_argument("--file", type=str, help="Path to a file containing reply content")

    # ---------------------------------------------------------------
    # docs
    # ---------------------------------------------------------------
    docs_parser = subparsers.add_parser(
        "docs",
        formatter_class=F,
        help="Create docs, list, read, and edit docs and pages",
        description="""\
Manage ClickUp docs — create docs, list docs, inspect pages, edit and create pages.

Subcommands:
  list         — list docs in the workspace or a specific space
  get          — fetch one doc by ID
  create       — create a new doc in a space (mutating, v3)
  pages        — list pages in a doc (use this to discover page IDs)
  get-page     — fetch one page by doc ID and page ID
  edit-page    — edit an existing page (mutating)
  create-page  — create a new page in a doc (mutating)

Important: doc ID is not the same as page ID. After finding a doc,
use 'docs pages' to discover page IDs before using get-page or edit-page.

Does not cover: renaming docs, or deleting docs/pages
(these are not supported by the ClickUp API).""",
        epilog="""\
typical workflow:
  1. clickup docs list                   — find the doc ID
  2. clickup docs pages <doc_id>         — find the page ID
  3. clickup docs get-page <doc_id> <page_id>  — read the page
  4. clickup docs edit-page <doc_id> <page_id> --content-file new.md

examples:
  clickup docs list --space <name>
  clickup docs pages doc_abc123
  clickup --dry-run docs edit-page doc_abc page_xyz --content "Updated" """,
    )
    docs_sub = docs_parser.add_subparsers(dest="command", required=True)

    # docs list
    dl = docs_sub.add_parser(
        "list",
        formatter_class=F,
        help="List docs in the workspace or a space",
        description="""\
List docs in the workspace. Optionally filter by space.
Results are paginated internally and returned as a single JSON object.""",
        epilog="""\
returns:
  {"docs": [...], "count": N}

examples:
  clickup docs list
  clickup docs list --space <name>
  clickup --pretty docs list""",
    )
    dl.add_argument(
        "--space", type=str, help="Filter docs to a specific space"
    )

    # docs get
    dg = docs_sub.add_parser(
        "get",
        formatter_class=F,
        help="Fetch one doc by ID",
        description="""\
Fetch a single doc by its ClickUp doc ID.

Use this when you need metadata about a doc. To read page content,
use 'docs pages' followed by 'docs get-page'.""",
        epilog="""\
returns:
  One doc JSON object.

examples:
  clickup docs get doc_abc123
  clickup --pretty docs get doc_abc123""",
    )
    dg.add_argument("doc_id", type=str, help="ClickUp doc ID")

    # docs create
    dc = docs_sub.add_parser(
        "create",
        formatter_class=F,
        help="Create a new doc in a space",
        description="""\
Create a new doc in a space. This is a mutating command (v3 API).

Optionally provide initial content via --content or --content-file.
If content is provided, it is written to the auto-created default page
automatically — no need for a separate edit-page call.

Use --dry-run to preview the request body without creating the doc.
Global flags may appear before or after the command group:
  clickup --dry-run docs create --space <name> --name "My doc" """,
        epilog="""\
returns:
  The created doc object from the API. If content was written, includes
  _initial_content_written: true and _page_id fields.

examples:
  clickup docs create --space <name> --name "Sprint notes"
  clickup docs create --space <name> --name "API spec" --content-file spec.md
  clickup docs create --space <name> --name "Journal" --content "# Entry"
  clickup --dry-run docs create --space <name> --name "Test doc"

notes:
  --content and --content-file are mutually exclusive. Using both is an error.
  Does not support: renaming or deleting docs (ClickUp API limitation).""",
    )
    dc.add_argument(
        "--space",
        required=True,
        type=str,
        help="Space to create the doc in (required)",
    )
    dc.add_argument("--name", required=True, help="Document name (required)")
    dc.add_argument(
        "--content",
        type=str,
        help="Inline initial content as markdown (mutually exclusive with --content-file)",
    )
    dc.add_argument(
        "--content-file", type=str, help="Path to a file containing initial content"
    )
    dc.add_argument(
        "--visibility", type=str, help="Doc visibility (e.g. 'PRIVATE', 'PUBLIC')"
    )

    # docs pages
    dp = docs_sub.add_parser(
        "pages",
        formatter_class=F,
        help="List pages in a doc (use this to discover page IDs)",
        description="""\
List all pages in a doc. Returns page metadata including page IDs.

Use this to discover valid page IDs before calling get-page or edit-page.
Doc ID is not the same as page ID — this command bridges the gap.""",
        epilog="""\
returns:
  A JSON array of page objects with id, name, and content fields.

examples:
  clickup docs pages doc_abc123
  clickup --pretty docs pages doc_abc123

notes:
  Always run this before get-page or edit-page if you do not already
  have the page ID. Using the doc ID as a page ID will fail.""",
    )
    dp.add_argument("doc_id", type=str, help="ClickUp doc ID")

    # docs get-page
    dgp = docs_sub.add_parser(
        "get-page",
        formatter_class=F,
        help="Fetch one page by doc ID and page ID",
        description="""\
Fetch a single page from a doc by its doc ID and page ID.

Use docs pages first to discover valid page IDs. The doc ID is not
a valid page ID — using it as one will fail.

Returns one page object with content in the requested format.""",
        epilog="""\
returns:
  One page JSON object with id, name, and content.

examples:
  clickup docs get-page doc_abc page_xyz
  clickup docs get-page doc_abc page_xyz --format plain
  clickup --pretty docs get-page doc_abc page_xyz

notes:
  Default format is markdown (md). Use --format plain for plain text.
  Page ID must come from 'docs pages', not from the doc ID itself.""",
    )
    dgp.add_argument("doc_id", type=str, help="ClickUp doc ID")
    dgp.add_argument("page_id", type=str, help="Page ID (from 'docs pages')")
    dgp.add_argument(
        "--format",
        choices=["md", "plain"],
        default="md",
        help="Content format: md (default) or plain",
    )

    # docs edit-page
    dep = docs_sub.add_parser(
        "edit-page",
        formatter_class=F,
        help="Edit an existing page in a doc",
        description="""\
Edit an existing page in a doc. This is a mutating command.

At least one editable field is required: --content, --content-file, or --name.
If none are provided, the command exits with an error.

Use --content for inline text or --content-file for file-based content.
Do not use both at the same time. Content is sent as markdown.

Use --append to keep the existing page content and add the new content at
the end. In append mode, the CLI reads the current page first, combines
the content locally, then sends one update request.

Use --dry-run to preview the request body without applying changes.
Global flags may appear before or after the command group:
  clickup --dry-run docs edit-page doc_abc page_xyz --content "New text"
  clickup docs edit-page doc_abc page_xyz --content "New text" --dry-run""",
        epilog="""\
returns:
  The updated page object from the API.

examples:
  clickup docs edit-page doc_abc page_xyz --content "# Updated heading"
  clickup docs edit-page doc_abc page_xyz --content-file revised.md
  clickup docs edit-page doc_abc page_xyz --content-file session.md --append
  clickup docs edit-page doc_abc page_xyz --name "Renamed page"
  clickup --dry-run docs edit-page doc_abc page_xyz --content "Test"

notes:
  --content and --content-file are mutually exclusive. Using both is an error.
  --append requires --content or --content-file.
  Does not support: deleting pages (not available in the ClickUp API).
  Use 'docs pages' to find the correct page ID before editing.""",
    )
    dep.add_argument("doc_id", type=str, help="ClickUp doc ID")
    dep.add_argument("page_id", type=str, help="Page ID (from 'docs pages')")
    dep.add_argument(
        "--content",
        type=str,
        help="Inline page content as markdown (mutually exclusive with --content-file)",
    )
    dep.add_argument(
        "--content-file", type=str, help="Path to a file containing page content"
    )
    dep.add_argument("--name", type=str, help="New page name (rename)")
    dep.add_argument(
        "--append",
        action="store_true",
        help="Append new content to the existing page instead of replacing it",
    )

    # docs create-page
    dcp = docs_sub.add_parser(
        "create-page",
        formatter_class=F,
        help="Create a new page in a doc",
        description="""\
Create a new page inside an existing doc. This is a mutating command.

Use --content for inline text or --content-file for file-based content.
Do not use both at the same time.

Note: when a doc is first created, it already has a blank default page.
If you want to write to that existing page, use 'docs edit-page' instead
of creating an additional page.

Use --dry-run to preview the request body without creating the page.
Global flags may appear before or after the command group:
  clickup --dry-run docs create-page doc_abc --name "New page" """,
        epilog="""\
returns:
  The created page object from the API.

examples:
  clickup docs create-page doc_abc --name "Meeting notes"
  clickup docs create-page doc_abc --name "Spec" --content-file spec.md
  clickup --dry-run docs create-page doc_abc --name "Draft"

notes:
  --content and --content-file are mutually exclusive. Using both is an error.
  A newly created doc already has a default blank page. Use edit-page to
  write to that page instead of creating a duplicate.
  Does not support: deleting pages (not available in the ClickUp API).""",
    )
    dcp.add_argument("doc_id", type=str, help="ClickUp doc ID")
    dcp.add_argument("--name", required=True, help="Page name (required)")
    dcp.add_argument(
        "--content",
        type=str,
        help="Inline page content as markdown (mutually exclusive with --content-file)",
    )
    dcp.add_argument(
        "--content-file", type=str, help="Path to a file containing page content"
    )

    # ---------------------------------------------------------------
    # spaces
    # ---------------------------------------------------------------
    spaces_parser = subparsers.add_parser(
        "spaces",
        formatter_class=F,
        help="List spaces, view details, and discover statuses",
        description="""\
Inspect workspace spaces — list all spaces, view space details, and
discover valid statuses per space.

Subcommands:
  list      — list all spaces in the workspace
  get       — fetch full details of a specific space
  statuses  — list valid statuses for a space

All commands are read-only. Configured space names and raw ClickUp
space IDs are both accepted.""",
        epilog="""\
examples:
  clickup spaces list
  clickup spaces get <space>
  clickup spaces statuses <space>

notes:
  These commands hit the API directly — no caching.
  Use 'spaces statuses' to find valid status names before setting
  task statuses, avoiding "Status does not exist" errors.""",
    )
    spaces_sub = spaces_parser.add_subparsers(dest="command", required=True)

    # spaces list
    spaces_sub.add_parser(
        "list",
        formatter_class=F,
        help="List all spaces in the workspace",
        description="""\
List all spaces in the workspace. Returns space names, IDs, and basic
metadata for every space the authenticated user can access.

Use this for discovery — find available spaces and their IDs without
relying on hardcoded configuration.""",
        epilog="""\
returns:
  {"spaces": [...], "count": N}

examples:
  clickup spaces list
  clickup --pretty spaces list""",
    )

    # spaces get
    sg = spaces_sub.add_parser(
        "get",
        formatter_class=F,
        help="Fetch full details of a specific space",
        description="""\
Fetch full details of a space including statuses, features, and members.

Accepts a configured space name or a raw ClickUp space ID.
Use 'spaces list' to discover available spaces.""",
        epilog="""\
returns:
  One space JSON object with all fields (statuses, features, members, etc.)

examples:
  clickup spaces get <space>
  clickup spaces get 901810200000
  clickup --pretty spaces get <space>""",
    )
    sg.add_argument(
        "space", type=str, help="Space name (from config) or raw space ID"
    )

    # spaces statuses
    ss = spaces_sub.add_parser(
        "statuses",
        formatter_class=F,
        help="List valid statuses for a space",
        description="""\
List the valid workflow statuses for a space. Returns the status name,
type (open, closed, custom), color, and order.

Use this before setting a task status to avoid "Status does not exist"
errors. Status names are space-specific — each space has its own set.""",
        epilog="""\
returns:
  {"space": "<name>", "statuses": [...], "count": N}

  Each status has: status (name), type, color, orderindex.

examples:
  clickup spaces statuses <space>
  clickup spaces statuses 901810200000
  clickup --pretty spaces statuses <space>

notes:
  Accepts a configured space name or raw space ID.
  Statuses can only be modified via the ClickUp UI, not the API.""",
    )
    ss.add_argument(
        "space", type=str, help="Space name (from config) or raw space ID"
    )

    # ---------------------------------------------------------------
    # folders
    # ---------------------------------------------------------------
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
    fg.add_argument("folder_id", type=str, help="ClickUp folder ID")

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
    fu.add_argument("folder_id", type=str, help="ClickUp folder ID to update")
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
    fd.add_argument("folder_id", type=str, help="ClickUp folder ID to delete")

    # ---------------------------------------------------------------
    # lists
    # ---------------------------------------------------------------
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
    lg.add_argument("list_id", type=str, help="ClickUp list ID")

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
    lu.add_argument("list_id", type=str, help="ClickUp list ID to update")
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
    ld.add_argument("list_id", type=str, help="ClickUp list ID to delete")

    # ---------------------------------------------------------------
    # team
    # ---------------------------------------------------------------
    team_parser = subparsers.add_parser(
        "team",
        formatter_class=F,
        help="Workspace and team member information",
        description="""\
Inspect workspace and team details — authenticated user info and member list.

Subcommands:
  whoami   — show workspace info and authenticated user context
  members  — list all members of the workspace

All commands are read-only.""",
        epilog="""\
examples:
  clickup team whoami
  clickup team members
  clickup --pretty team whoami""",
    )
    team_sub = team_parser.add_subparsers(dest="command", required=True)

    # team whoami
    team_sub.add_parser(
        "whoami",
        formatter_class=F,
        help="Show workspace info and member context",
        description="""\
Show the workspace name, ID, and all members visible to the authenticated
user. Use this as a quick sanity check to confirm which workspace and
identity the CLI is operating under.""",
        epilog="""\
returns:
  {"workspace": {"id": ..., "name": ...}, "members": [...], "member_count": N}

examples:
  clickup team whoami
  clickup --pretty team whoami""",
    )

    # team members
    team_sub.add_parser(
        "members",
        formatter_class=F,
        help="List all workspace members",
        description="""\
List all members of the workspace with their IDs, usernames, emails,
and roles. Use this to discover user IDs for task assignment or to
verify team membership.""",
        epilog="""\
returns:
  {"members": [...], "count": N}

  Each member has: id, username, email, role, initials.

examples:
  clickup team members
  clickup --pretty team members""",
    )

    # ---------------------------------------------------------------
    # tags
    # ---------------------------------------------------------------
    tags_parser = subparsers.add_parser(
        "tags",
        formatter_class=F,
        help="List space tags, add/remove tags on tasks",
        description="""\
Manage tags — list available tags in a space, add or remove tags on tasks.

Subcommands:
  list    — list all tags in a space
  add     — add a tag to a task (mutating)
  remove  — remove a tag from a task (mutating)

Tag names are lowercase in the API, even if they display with title case
in the ClickUp UI. The CLI lowercases tag names automatically.""",
        epilog="""\
examples:
  clickup tags list --space <name>
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

    # tags add
    tga = tags_sub.add_parser(
        "add",
        formatter_class=F,
        help="Add a tag to a task",
        description="""\
Add a tag to a task. This is a mutating command.

The tag name is automatically lowercased (ClickUp API requirement).
The tag must already exist in the space — this command does not create tags.

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
    tga.add_argument("task_id", type=str, help="ClickUp task ID")
    tga.add_argument(
        "--tag", required=True, type=str, help="Tag name to add (auto-lowercased)"
    )

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
    tgr.add_argument("task_id", type=str, help="ClickUp task ID")
    tgr.add_argument(
        "--tag", required=True, type=str, help="Tag name to remove (auto-lowercased)"
    )

    return parser


def _get_version():
    from . import __version__
    return __version__


def dispatch(client, args):
    """Route parsed args to the correct command handler."""
    from .commands import HANDLERS

    key = f"{args.group}_{args.command}"
    handler = HANDLERS.get(key)
    if not handler:
        error(f"Unknown command: {args.group} {args.command}")
    assert handler is not None
    return handler(client, args)


def main():
    parser = build_parser()
    args = parser.parse_args(normalize_cli_argv(sys.argv[1:]))

    # Handle init before loading config (config may not exist yet)
    if args.group == "init":
        from .commands.init import cmd_init
        cmd_init(args)
        return

    # Load config and resolve token
    from .config import load_config
    config = load_config()

    token = os.environ.get("CLICKUP_API_TOKEN") or config.get("api_token")
    if not token:
        error(
            "No API token found. Set CLICKUP_API_TOKEN or run: clickup init"
        )

    client = ClickUpClient(token, dry_run=args.dry_run, debug=args.debug)
    result = dispatch(client, args)

    if result is not None:
        output(result, pretty=args.pretty)
