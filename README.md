# clickup-cli

[![PyPI version](https://img.shields.io/pypi/v/clickup-cli)](https://pypi.org/project/clickup-cli/)
[![Python versions](https://img.shields.io/pypi/pyversions/clickup-cli)](https://pypi.org/project/clickup-cli/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

The missing ClickUp CLI. Built for developers and AI agents.

There's no official ClickUp CLI. If you're a developer who lives in the terminal, or an AI agent that needs structured data from ClickUp, this fills the gap. JSON stdout, errors to stderr, dry-run on every mutation.

## Documentation

- [Contributing](CONTRIBUTING.md)
- [Security](SECURITY.md)
- [Code of Conduct](CODE_OF_CONDUCT.md)
- [Integration Guide](INTEGRATION.md)
- [Troubleshooting](TROUBLESHOOTING.md)
- [Changelog](CHANGELOG.md)
- [Release Guide](RELEASE.md)

## Install

```bash
pip install clickup-cli
```

## Setup

```bash
clickup init
```

This prompts for your API token, discovers your workspaces and spaces, identifies your user, and writes a config file to `~/.config/clickup-cli/config.json`.

`clickup init` stores each configured space alias with its canonical `space_id`. It does not preload one list per space during setup. Add `list_id` later only if you want a cached default list for list-bound commands.

If you have a single workspace, it's selected automatically. Same for user detection in single-member workspaces.

Get your API token at [app.clickup.com/settings/apps](https://app.clickup.com/settings/apps).

## Quick Start

```bash
clickup spaces list                                    # see your spaces
clickup tasks list --space <name>                     # list tasks
clickup tasks search "login bug"                       # search across workspace
clickup tasks get abc123                               # get task + comments
clickup --dry-run tasks create --space <name> --name "Fix auth"  # preview
clickup tasks create --space <name> --name "Fix auth" # create for real
clickup comments add abc123 --text "Done"              # add a comment
```

## For AI Agents

This CLI is designed to be used by AI coding agents (Claude Code, Codex, etc.) as a tool for interacting with ClickUp.

**What makes it agent-friendly:**
- All output is JSON on stdout — easy to parse
- Errors go to stderr with non-zero exit code — easy to detect
- Every command has detailed `--help` — agents can self-discover usage
- `--dry-run` on all mutations — agents can preview before acting
- `--pretty` for readable output during debugging
- **Flag aliases for all positional args** — agents can use `--task-id`, `--query`, `--doc-id`, `--comment-id` etc. instead of positional arguments (both forms work)
- **Auto-infer `--space` from `--list`** — `tasks create --list 12345 --name "Fix bug"` works without `--space`
- **Bounded defaults with completeness metadata** — `tasks list` and `tasks search` bound pagination by default, and `tasks get` bounds comment hydration by default; each response includes metadata showing whether the result is complete or truncated

**Plug-and-play skill file:** Copy `.claude/skills/clickup-cli.md` from this repo into your project's `.claude/skills/` directory. It teaches Claude Code how to use the CLI: command discovery, safety patterns, common workflows.

**Minimal system prompt snippet:**
```
You have access to the `clickup` CLI for managing ClickUp tasks and docs.
Use `clickup <group> --help` to discover commands.
Always use `--dry-run` before mutating commands.
Output is JSON on stdout; errors go to stderr.
```

## Commands

| Group | Subcommands | Description |
|-------|-------------|-------------|
| `init` | — | Interactive workspace setup |
| `tasks` | list, get, create, update, search, delete, move, merge, depend | Full task CRUD + dependencies |
| `comments` | list, add, update, delete, thread, reply | Full comment CRUD with threading |
| `docs` | list, get, create, pages, get-page, edit-page, create-page | Docs and page management |
| `folders` | list, get, create, update, delete, privacy | Folder CRUD + privacy toggle |
| `lists` | list, get, create, update, delete, privacy | List CRUD + privacy toggle |
| `spaces` | list, get, statuses, privacy | Space inspection + privacy toggle |
| `team` | whoami, members | Workspace and member info |
| `tags` | list, add, remove | Tag management |

Use `clickup <group> <command> --help` for detailed usage, examples, and return format.

## Global Flags

```
--pretty     Pretty-print JSON output
--dry-run    Preview mutations without executing
--debug      Log API requests and responses to stderr
--version    Show version
```

Global flags can appear before or after the command group:

```bash
clickup --pretty tasks list --space <name>
clickup tasks list --space <name> --pretty
```

## Key Behaviors

- **Flag aliases** — every positional argument also accepts a `--flag` form. `tasks get abc123` and `tasks get --task-id abc123` are equivalent. Same for `--query`, `--doc-id`, `--page-id`, `--folder-id`, `--list-id`, `--comment-id`, `--space`.
- **Raw numeric IDs** on `--space` and `--folder` flags are accepted transparently alongside config aliases. On tasks commands, list-bound commands may resolve a raw space ID to its first folderless list via one API call.
- **`tasks create`** auto-infers `--space` from `--list` via API lookup. You can omit `--space` if `--list` is provided.
- **`tasks update`** handles core fields, assignee diffs (`--add-assignee` / `--remove-assignee`), tag diffs (`--add-tag` / `--remove-tag`), and custom fields (`--custom-field FIELD_ID=VALUE`) in one call. All flags are repeatable; `--dry-run` returns a structured plan.
- **`tasks depend`** — `add`, `remove`, and `list` for task dependencies. Direction required on add/remove via `--depends-on` or `--depended-on-by`.
- **`tasks list` / `tasks search --include-archived`** — second paginated call with `archived=true`, merged into the default results. Since ClickUp's `archived` param is a filter, this is the only way to see both in one command.
- **`tasks list` / `tasks search` bounded defaults** — by default, these commands fetch a bounded aggregate scan and return `pages_fetched`, `results_complete`, and `results_truncated`. Use `--all-pages` for an exhaustive scan.
- **`tasks list --full` / `tasks search --full`** return full task objects with a normalized `status` dict shape (`{status, color, type, orderindex}`), not just the compact projection.
- **`tasks get`** auto-fetches comments and appends them to the output. By default this is a bounded slice and the response includes `comment_count_returned`, `comments_complete`, and `comments_truncated`. Use `--all-comments` for exhaustive comment hydration or `--no-comments` to skip it.
- **`tasks search`** auto-detects task ID patterns like `PROJ-39` and applies prefix filtering.
- **`docs edit-page --append`** reads the current page content, appends your new content, and sends one update.
- **Tag names** are auto-lowercased (ClickUp API stores them lowercase regardless of UI display).
- **Doc ID ≠ page ID.** Always use `docs pages <doc_id>` to discover page IDs before using `get-page` or `edit-page`.

## Configuration

### Config file

`clickup init` creates `~/.config/clickup-cli/config.json`:

```json
{
  "api_token": "pk_...",
  "workspace_id": "12345",
  "user_id": "67890",
  "spaces": {
    "myspace": {"space_id": "111"},
    "myspace-with-default-list": {"space_id": "111", "list_id": "222"}
  }
}
```

`space_id` is the identity of a configured alias. `list_id` is optional convenience for commands that need a default list; space-scoped commands still target the full space when the command supports full-space scope.

### Config resolution order

1. `CLICKUP_CONFIG_PATH` env var → exact file path
2. `~/.config/clickup-cli/config.json` → default location
3. `clickup-config.json` in current working directory → project-local override

### Environment variables

| Variable | Purpose |
|----------|---------|
| `CLICKUP_API_TOKEN` | API token (overrides config file token) |
| `CLICKUP_WORKSPACE_ID` | Workspace ID (auto-detected if you have one workspace) |
| `CLICKUP_USER_ID` | User ID for task assignment |
| `CLICKUP_CONFIG_PATH` | Custom config file path |

You can run without a config file by setting just `CLICKUP_API_TOKEN` — the workspace ID is auto-detected if your account has a single workspace. Set `CLICKUP_WORKSPACE_ID` explicitly for multi-workspace accounts.

## Coverage and Gaps

**Covered:** tasks (including dependencies and custom field writes), comments, docs/pages, folders, lists, spaces, tags, team/workspace info.

**Not yet covered:** checklists, time tracking, attachments, goals, webhooks, automations.

## Contributor Notes

Contributor setup stays intentionally standard:

- `pip install -e ".[dev]"`
- `pytest -v`
- `ruff check src/ tests/`

Project-specific maintainer automation and agent tooling live in repo-local config files and are documented in [CONTRIBUTING.md](CONTRIBUTING.md), so the main README can stay focused on public CLI usage.

## Contributing

```bash
git clone https://github.com/efetoker/clickup-cli.git
cd clickup-cli
pip install -e ".[dev]"
pytest -v
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for the current manifest-driven command workflow, test layout, and maintainer notes. Public integration and support docs are linked in the [Documentation](#documentation) section above.

Issues and PRs welcome at [github.com/efetoker/clickup-cli](https://github.com/efetoker/clickup-cli).

## License

MIT
