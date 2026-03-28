"""Doc command handlers — list, get, create, pages, get-page, edit-page, create-page."""

from ..config import WORKSPACE_ID, SPACES
from ..helpers import read_content, error


def _append_markdown(existing, new_content):
    """Append markdown content with a readable separator when both sides exist."""
    existing = existing or ""
    new_content = new_content or ""

    if not existing:
        return new_content
    if not new_content:
        return existing

    return f"{existing.rstrip()}\n\n{new_content.lstrip()}"


def cmd_docs_list(client, args):
    if client.dry_run:
        return {"dry_run": True, "action": "list_docs", "space": getattr(args, "space", None)}

    params = {"limit": "100"}
    if args.space:
        space = SPACES.get(args.space)
        if space:
            params["parent_id"] = space["space_id"]
            params["parent_type"] = "SPACE"

    all_docs = []
    cursor = None
    while True:
        if cursor:
            params["cursor"] = cursor
        resp = client.get_v3(f"/workspaces/{WORKSPACE_ID}/docs", params=params)
        docs = resp.get("docs", [])
        all_docs.extend(docs)
        cursor = resp.get("next_cursor")
        if not cursor:
            break

    return {"docs": all_docs, "count": len(all_docs)}


def cmd_docs_get(client, args):
    return client.get_v3(f"/workspaces/{WORKSPACE_ID}/docs/{args.doc_id}")


def cmd_docs_create(client, args):
    """Create a new doc in a space."""
    content = read_content(args.content, args.content_file, "--content")
    space = SPACES.get(args.space)
    if not space:
        error(f"Unknown space: {args.space}. Check your config file.")

    body = {"name": args.name}
    body["parent"] = {"id": space["space_id"], "type": 4}
    if args.visibility:
        body["visibility"] = args.visibility

    if client.dry_run:
        return {"dry_run": True, "action": "create_doc", "body": body}

    doc = client.post_v3(f"/workspaces/{WORKSPACE_ID}/docs", data=body)

    # If content provided, write it to the auto-created default page
    if content and not client.dry_run:
        doc_id = doc.get("id")
        if doc_id:
            pages = client.get_v3(
                f"/workspaces/{WORKSPACE_ID}/docs/{doc_id}/pages",
                params={"content_format": "text/md"},
            )
            page_list = pages if isinstance(pages, list) else pages.get("pages", [])
            if page_list:
                page_id = page_list[0].get("id")
                if page_id:
                    client.put_v3(
                        f"/workspaces/{WORKSPACE_ID}/docs/{doc_id}/pages/{page_id}",
                        data={"content": content, "content_format": "text/md"},
                    )
                    doc["_initial_content_written"] = True
                    doc["_page_id"] = page_id

    return doc


def cmd_docs_pages(client, args):
    params = {"content_format": "text/md"}
    return client.get_v3(
        f"/workspaces/{WORKSPACE_ID}/docs/{args.doc_id}/pages", params=params
    )


def cmd_docs_get_page(client, args):
    fmt = "text/md" if args.format == "md" else "text/plain"
    params = {"content_format": fmt}
    return client.get_v3(
        f"/workspaces/{WORKSPACE_ID}/docs/{args.doc_id}/pages/{args.page_id}",
        params=params,
    )


def cmd_docs_edit_page(client, args):
    content = read_content(args.content, args.content_file, "--content")
    body = {}

    if getattr(args, "append", False):
        if not content:
            error("--append requires --content or --content-file")
        page = client.get_v3(
            f"/workspaces/{WORKSPACE_ID}/docs/{args.doc_id}/pages/{args.page_id}",
            params={"content_format": "text/md"},
            allow_dry_run=True,
        )
        content = _append_markdown(page.get("content", ""), content)

    if content:
        body["content"] = content
        body["content_format"] = "text/md"
    if args.name:
        body["name"] = args.name

    if not body:
        error(
            "Nothing to update — provide at least one of: --content, --content-file, --name"
        )

    if client.dry_run:
        return {
            "dry_run": True,
            "action": "edit_page",
            "doc_id": args.doc_id,
            "page_id": args.page_id,
            "body": body,
        }

    return client.put_v3(
        f"/workspaces/{WORKSPACE_ID}/docs/{args.doc_id}/pages/{args.page_id}",
        data=body,
    )


def cmd_docs_create_page(client, args):
    content = read_content(args.content, args.content_file, "--content")
    body = {"name": args.name}
    if content:
        body["content"] = content
        body["content_format"] = "text/md"

    return client.post_v3(
        f"/workspaces/{WORKSPACE_ID}/docs/{args.doc_id}/pages",
        data=body,
    )
