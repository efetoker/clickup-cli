# Changelog

## 1.4.0 (2026-04-11)

- **`tasks update` now handles tags, assignees, and custom fields.** Five new repeatable flags: `--add-assignee` / `--remove-assignee` (packed into the PUT body), `--add-tag` / `--remove-tag` (issues one POST/DELETE per tag), and `--custom-field FIELD_ID=VALUE` (issues one POST per field). When no PUT body is needed, the task is re-fetched at the end so the returned JSON always reflects final state. `--dry-run` returns a structured plan with no API calls.
- **New `tasks depend` subcommand group** — `add`, `remove`, and `list` for task dependencies. Direction is required and mutually exclusive: `--depends-on OTHER` (this task waits on OTHER) or `--depended-on-by OTHER` (OTHER waits on this). `list` partitions the task's `dependencies` array into both directions from the target task's point of view.
- **`tasks list` and `tasks search` accept `--include-archived`.** Since ClickUp's `archived` param is a filter (returns only archived), the flag issues a second paginated request with `archived=true` and merges the results. Default behavior unchanged.
- **Raw numeric IDs accepted on all name-lookup flags.** `--space` / `--folder` on folders, lists, spaces, and tasks commands now transparently accept raw ClickUp IDs alongside config aliases. On tasks commands, raw space IDs resolve via a one-call API lookup to the first folderless list in that space. Help metavars updated to `SPACE_NAME_OR_ID` for discoverability. Case-sensitive alias matching is unchanged — `Personal` vs `personal` remains a deliberate error.
- **Fix: `tasks create` no longer leaks `hint: inferred --space` to stderr.** Same fix applied to `tasks search`'s auto name-prefix hint. Both are deterministic from inputs and the JSON response — the hints were informational noise that broke `2>&1 | jq` pipes.
- **Fix: `tasks create` is now truly neutral.** The v1.3.0 release advertised neutral defaults but still read `default_tags` from the config file and applied it silently. Removed `default_tags` from the config schema entirely; stale entries in existing configs are now ignored.
- **Fix: `tasks list --full` returns a consistent status shape.** Compact mode already flattened status to a string, but `--full` passed raw API shapes through — sometimes dict, sometimes string. Now `--full` always returns status as a dict (`{status, color, type, orderindex}`), upgrading string statuses with null metadata.
- **Client: `delete_v2` accepts an optional `params` kwarg** to forward query parameters (needed for the dependency remove endpoint).
- Test suite: 305 → 332 tests. Added coverage for stderr contract, archived pagination, status-shape normalization, raw-ID lookups, expanded update paths, and dependency CRUD.

## 1.3.0 (2026-04-10)

- Add `--tag` filter on `tasks list` (API-level, repeatable, auto-lowercased) and `tasks search` (client-side filter).
- Remove opinionated `tasks create` defaults: no auto-assignee, no auto-priority, no auto-tags unless explicitly passed. (Note: `default_tags` config field was not fully removed until 1.4.0.)
- Explicit `--assign <user_id>` flag for `tasks create` when you do want to assign.

## 1.2.0 (2026-03-29)

**First PyPI release** — `pip install clickup-cli`

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
