# Changelog

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
