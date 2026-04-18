"""Shared privacy command helpers for spaces, folders, and lists."""

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
    """Register a privacy subcommand with the shared flag contract."""
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
    """Execute the shared privacy runtime contract."""
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
