"""CLI parser, dispatch, and main entry point."""

import argparse
import os
import sys

from . import __version__
from .client import ClickUpClient
from .helpers import output, error, resolve_id_args


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
        version=f"%(prog)s {__version__}",
    )

    subparsers = parser.add_subparsers(dest="group", required=True)

    # init (standalone — no register_parser, handled specially in main())
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

    # Register all command group parsers from their modules
    from .commands.tasks import register_parser as tasks_register
    from .commands.comments import register_parser as comments_register
    from .commands.docs import register_parser as docs_register
    from .commands.spaces import register_parser as spaces_register
    from .commands.folders import register_parser as folders_register
    from .commands.lists import register_parser as lists_register
    from .commands.team import register_parser as team_register
    from .commands.tags import register_parser as tags_register

    tasks_register(subparsers, F)
    comments_register(subparsers, F)
    docs_register(subparsers, F)
    spaces_register(subparsers, F)
    folders_register(subparsers, F)
    lists_register(subparsers, F)
    team_register(subparsers, F)
    tags_register(subparsers, F)

    return parser


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
    resolve_id_args(args)

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
