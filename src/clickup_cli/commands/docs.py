"""Doc command handlers — list, get, create, pages, get-page, edit-page, create-page."""

from ..config import WORKSPACE_ID, SPACES
from ..helpers import read_content, error


def register_parser(subparsers, F):
    """Register all docs subcommands on the given subparsers object."""
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
