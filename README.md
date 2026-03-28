# clickup-cli

The missing ClickUp CLI. Built for developers and AI agents.

There's no official ClickUp CLI. If you're a developer who lives in the terminal, or an AI agent that needs structured data from ClickUp, this fills the gap. JSON stdout, errors to stderr, dry-run on every mutation.

## Install

```bash
pip install clickup-cli
```

## Setup

```bash
clickup init
```

This prompts for your API token, discovers your workspaces and spaces, identifies your user, and writes a config file to `~/.config/clickup-cli/config.json`.

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
| `tasks` | list, get, create, update, search, delete, move, merge | Full task CRUD |
| `comments` | list, add, update, delete, thread, reply | Full comment CRUD with threading |
| `docs` | list, get, create, pages, get-page, edit-page, create-page | Docs and page management |
| `folders` | list, get, create, update, delete | Folder CRUD |
| `lists` | list, get, create, update, delete | List CRUD |
| `spaces` | list, get, statuses | Space inspection |
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

- **`tasks get`** auto-fetches comments and appends them to the output. Use `--no-comments` to skip.
- **`tasks search`** auto-detects task ID patterns like `PROJ-39` and applies prefix filtering.
- **`tasks create`** checks for duplicates before creating. Use `--skip-dedup` to bypass.
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
    "myspace": {"space_id": "111", "list_id": "222"}
  },
  "default_tags": [],
  "draft_tag": "draft",
  "good_as_is_tag": "good as is",
  "default_priority": 4
}
```

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

**Covered:** tasks, comments, docs/pages, folders, lists, spaces, tags, team/workspace info.

**Not yet covered:** checklists, time tracking, custom fields, task relationships, attachments, goals, webhooks, automations.

## Contributing

```bash
git clone https://github.com/efetoker/clickup-cli.git
cd clickup-cli
pip install -e ".[dev]"
pytest -v
```

Issues and PRs welcome at [github.com/efetoker/clickup-cli](https://github.com/efetoker/clickup-cli).

## License

MIT
