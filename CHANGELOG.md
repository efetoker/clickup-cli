# Changelog

## 1.2.0 (2026-03-29)

- Accept flag aliases for all positional arguments — agents can now use `--task-id`, `--query`, `--doc-id`, `--page-id`, `--folder-id`, `--list-id`, `--comment-id`, `--space` instead of positional args. Both forms work; positional args are unchanged for backwards compatibility.
- Auto-infer `--space` from `--list` on `tasks create` — when `--list` is provided without `--space`, the CLI fetches the list metadata via API to resolve its parent space automatically. Eliminates the most common agent error (12+ failures in 3 days).
- Make `--space` optional on `tasks create` (was required) — now only required if `--list` is also absent.
- Expand test suite to 305 tests — full behavioral coverage for `cmd_init` (12 tests), `main()` integration (4 tests), `cmd_docs_create` content paths (3 tests), and 429 retry edge case (1 test).
- Simplify codebase: use shared `error()` in config.py, DRY up tag add/remove, task list/search epilogue, list folder/space resolution, client retry logic. -24 net lines across 7 files.

## 1.1.3 (2026-03-29)

- Refactor: split 1633-line `build_parser()` — each command module now owns its parser via `register_parser()`
- Refactor: extract shared `_paginate_tasks()` helper, removing duplicate pagination logic in tasks list/search
- Refactor: extract `_extract_status()` and `_extract_priority()` helpers in helpers.py, deduplicating field extraction
- Clean up dead code in `client.py` (unreachable None guards, pointless variable rename)
- Expand test suite from 55 to 89 tests — comprehensive parser coverage for all 8 command groups
- Fix stale version assertion in tests (was checking 1.1.0 instead of current version)

## 1.1.2 (2026-03-29)

- Add auto-lint hook — ruff check/format runs automatically on every Python file edit
- Add sensitive file guard — blocks edits to `.env`, `.secret`, `.pem`, `.key`, and credentials files
- Add context7 MCP server (`.mcp.json`) — live ClickUp API docs for contributors
- Add `test-writer` subagent (`.claude/agents/`) — generates pytest tests following project patterns
- Add `/release` skill — version bump, validate, tag, build, publish workflow
- Clean up permission allowlist in `.claude/settings.local.json`

## 1.1.1 (2026-03-29)

- Add `.env` and `.env.*` to `.gitignore` for API token safety
- Add `scripts/validate-cli-output.sh` — validates all CLI help commands, error routing, and version flag
- Add `.claude/skills/add-command.md` — prescriptive dev workflow for adding new commands
- Replace hardcoded `myspace` with `<name>` / `<space_name>` placeholders in skill and README

## 1.1.0 (2026-03-29)

- Auto-detect workspace ID for single-workspace accounts — no need to set it manually
- Fix user detection in `clickup init` — now prompts for selection in multi-member workspaces
- workspace_id is saved back to config file after auto-detection
- Add `--debug` flag — logs API requests and responses to stderr for troubleshooting
- Improve space name resolution — clear error with available names when a space isn't found in config
- Fix comment pagination — no longer hardcodes page size assumption

## 1.0.0 (2026-03-28)

Initial public release.

- 8 command groups: tasks, comments, docs, folders, lists, spaces, team, tags
- Full task CRUD with search, move, merge
- Full comment CRUD with threading
- Docs management with page editing
- Folder and list management
- Tag management
- Workspace discovery via `clickup init`
- JSON-only stdout, errors to stderr
- Dry-run mode for all mutations
- Rate limit handling with automatic retry
- Config via JSON file or environment variables
