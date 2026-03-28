"""Comment command handlers — list, add, update, delete, thread, reply."""

from ..helpers import read_content, error, fetch_all_comments


def register_parser(subparsers, F):
    """Register all comments subcommands on the given subparsers object."""
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


def cmd_comments_list(client, args):
    if client.dry_run:
        return {"dry_run": True, "action": "list_comments", "task_id": args.task_id}

    resp = client.get_v2(f"/task/{args.task_id}/comment")
    comments = resp.get("comments", [])

    if not args.fetch_all or len(comments) < 25:
        return {"comments": comments, "count": len(comments)}

    # Paginate through all comments
    all_comments = fetch_all_comments(client, args.task_id)
    return {"comments": all_comments, "count": len(all_comments)}


def cmd_comments_add(client, args):
    text = read_content(args.text, args.file, "--text")
    if not text:
        error("Provide comment text via --text or --file")
    body = {"comment_text": text, "notify_all": False}
    return client.post_v2(f"/task/{args.task_id}/comment", data=body)


def cmd_comments_update(client, args):
    """Update an existing comment's text or resolved status."""
    text = read_content(args.text, args.file, "--text")
    body = {}
    if text:
        body["comment_text"] = text
    if args.resolved is not None:
        body["resolved"] = args.resolved
    if not body:
        error("Nothing to update — provide at least one of: --text, --file, --resolve, --unresolve")
    if client.dry_run:
        return {"dry_run": True, "action": "update", "comment_id": args.comment_id, "body": body}
    client.put_v2(f"/comment/{args.comment_id}", data=body)
    return {"status": "ok", "action": "updated", "comment_id": args.comment_id}


def cmd_comments_delete(client, args):
    """Delete a comment by ID."""
    if client.dry_run:
        return {"dry_run": True, "action": "delete", "comment_id": args.comment_id}
    client.delete_v2(f"/comment/{args.comment_id}")
    return {"status": "ok", "action": "deleted", "comment_id": args.comment_id}


def cmd_comments_thread(client, args):
    """Get threaded replies to a comment."""
    resp = client.get_v2(f"/comment/{args.comment_id}/reply")
    replies = resp.get("comments", resp if isinstance(resp, list) else [])
    return {"replies": replies, "count": len(replies)}


def cmd_comments_reply(client, args):
    """Reply to a comment (threaded)."""
    text = read_content(args.text, args.file, "--text")
    if not text:
        error("Provide reply text via --text or --file")
    body = {"comment_text": text, "notify_all": False}
    if client.dry_run:
        return {"dry_run": True, "action": "reply", "comment_id": args.comment_id, "body": body}
    return client.post_v2(f"/comment/{args.comment_id}/reply", data=body)
