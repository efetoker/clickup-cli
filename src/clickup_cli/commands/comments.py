"""Comment command handlers — list, add, update, delete, thread, reply."""

from ..helpers import read_content, error, fetch_all_comments


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
