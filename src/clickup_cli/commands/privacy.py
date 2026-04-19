"""Shared privacy helpers for the spaces/folders/lists `privacy` subcommands.

These helpers keep the parser contract and runtime response envelope aligned:
every privacy command accepts the shared ID argument pattern, requires exactly
one of `--private` / `--public`, supports `--dry-run`, and returns the same
JSON shape regardless of object type.
"""

from ..helpers import add_id_argument


def register_privacy_subcommand(
    subparsers,
    formatter_class,
    *,
    object_type,
    id_argument,
    id_help,
    description,
    epilog,
):
    """Register a `privacy` parser with the shared CLI contract.

    The caller supplies object-specific help text, but the command shape stays
    fixed: one positional/flag ID argument via `add_id_argument()` plus a
    required mutually exclusive `--private` or `--public` mode selection.
    """
    parser = subparsers.add_parser(
        "privacy",
        formatter_class=formatter_class,
        help=f"Make a {object_type} private or public",
        description=description,
        epilog=epilog,
    )
    add_id_argument(parser, id_argument, id_help)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--private", action="store_true", help=f"Make this {object_type} private"
    )
    mode.add_argument(
        "--public", action="store_true", help=f"Make this {object_type} public"
    )
    return parser


def handle_privacy_request(client, args, *, object_type, object_id, path_segment):
    """Execute the shared privacy toggle contract for spaces, folders, and lists.

    Runtime requests always PATCH the v3 ACL endpoint with `{"private": bool}`.
    `--dry-run` returns a structured plan that includes the action, object
    identity, and request body without making an API call. Live requests return
    the stable success envelope used by all privacy commands:
    `status`, `action`, `object_type`, `object_id`, and the resolved `private`
    boolean.
    """
    private = bool(args.private)
    body = {"private": private}
    path = f"/workspaces/{client.runtime.workspace_id}/{path_segment}/{object_id}/acls"

    if client.dry_run:
        return {
            "dry_run": True,
            "action": "set_privacy",
            "object_type": object_type,
            "object_id": object_id,
            "body": body,
        }

    client.patch_v3(path, data=body)
    return {
        "status": "ok",
        "action": "set_privacy",
        "object_type": object_type,
        "object_id": object_id,
        "private": private,
    }
