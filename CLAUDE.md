# ClickUp CLI — Development Instructions

## What This Is

A ClickUp CLI for developers and AI agents. JSON-only stdout, errors to stderr, dry-run on all mutations.

## Package Structure

```
src/clickup_cli/
├── cli.py           # root parser, dispatch, main() — delegates to command modules
├── client.py        # ClickUpClient API wrapper (rate limiting, dry-run, debug)
├── config.py        # Config loader (lazy, fallback chain, workspace auto-detect)
├── helpers.py       # output(), error(), compact_task(), add_id_argument(), etc.
└── commands/
    ├── __init__.py  # COMMAND_MANIFESTS registry + derived HANDLERS map
    ├── backup.py    # shared backup helpers used by list/folder backups
    ├── tasks.py     # compatibility facade for tasks entrypoints
    ├── tasks_internal/
    │   ├── parser.py   # tasks parser registration
    │   ├── read.py     # list/get/search handlers
    │   ├── write.py    # create/update/delete/move/merge/depend handlers
    │   └── shared.py   # task-scoped resolution helpers
    ├── comments.py  # comments parser + handlers (list/add/update/delete/thread/reply)
    ├── docs.py      # docs parser + handlers (list/get/create/pages/get-page/edit-page/create-page)
    ├── fields.py    # custom field metadata discovery
    ├── folders.py   # folders parser + handlers (list/get/create/update/delete/backup/purge-empty/privacy)
    ├── lists.py     # lists parser + handlers (list/get/create/update/delete/backup/privacy)
    ├── privacy.py   # shared privacy toggle helpers
    ├── spaces.py    # spaces parser + handlers (list/get/create/update/delete/statuses/privacy)
    ├── tags.py      # tags parser + handlers (list/create/delete/usage/add/remove)
    ├── task_types.py # workspace custom task type discovery
    ├── team.py      # team parser + handlers (whoami/members)
    └── init.py      # clickup init setup command
```

Each command group exposes a `COMMAND_MANIFEST` with `group`, `register_parser`, and `handlers`. `cli.py` builds the root parser by iterating `COMMAND_MANIFESTS`, and `commands/__init__.py` derives the dispatch map from those manifests.

## Argument Pattern: Positional + Flag Aliases

Every positional argument (task_id, query, doc_id, page_id, etc.) also accepts a `--flag` form via `add_id_argument()` from helpers.py. This makes the CLI usable by both humans (positional) and AI agents (flags).

```python
# In register_parser():
add_id_argument(parser, "task_id", "ClickUp task ID")

# Accepts both:
#   clickup tasks get abc123
#   clickup tasks get --task-id abc123
```

Resolution happens in `cli.py` via `resolve_id_args(args)` after parsing. If both forms are provided, it errors. If neither is provided, it errors with a helpful message.

When adding new commands with ID arguments, always use `add_id_argument()` instead of `parser.add_argument()` for positional IDs.

## Space Inference

`tasks create` accepts either `--space` or `--list`. If only `--list` is provided, it lazily infers the matching configured space alias from `GET /v2/list/{id}` before resolving the target list.

## Development Setup

```bash
pip install -e ".[dev]"
pytest -v
ruff check src/ tests/
scripts/validate-cli-output.sh   # verify JSON stdout contract
```

## Test Structure

```
tests/
├── conftest.py                             # test config setup before clickup_cli loads
├── command_fakes.py                       # shared fake client helpers for command tests
├── test_cli.py                            # parser, dispatch, global flags, resolve_id_args
├── test_client.py                         # ClickUpClient behavior
├── test_command_manifest.py               # manifest registry + derived handlers
├── test_commands_tasks.py                 # task command handlers
├── test_commands_docs_comments.py         # docs/comments handlers
├── test_commands_metadata.py              # fields/task-types handlers
├── test_commands_spaces_lists_folders.py  # spaces/lists/folders handlers
├── test_commands_misc.py                  # tags/team/init coverage
├── test_tasks_facade.py                   # tasks facade -> tasks_internal regression coverage
├── test_config.py                         # config loading
└── test_helpers.py                        # helpers and pagination utilities
```

See `README.md` and `CONTRIBUTING.md` for contributor-facing usage and workflow details; keep this file focused on repo-local development conventions.

## CI

GitHub Actions (`ci.yml`): lint + test on Python 3.9, 3.11, 3.13. Runs on push to main and PRs.

## Adding a New Command

The canonical human workflow lives in [CONTRIBUTING.md](CONTRIBUTING.md#adding-a-new-command). Keep this section focused on repo-local agent reminders:

1. Follow the manifest pattern; do not hand-edit the derived `HANDLERS` map.
2. For `tasks`, keep the public facade in `commands/tasks.py` and put parser/read/write internals in `commands/tasks_internal/` when extending the split structure.
3. Add self-sufficient help text and update the relevant split test module under `tests/`.

## Rules

- Help text must be self-sufficient — an agent should use `--help` to discover correct usage
- No workspace-specific values in help text or source code
- Stdout is always JSON. Errors and warnings go to stderr.
- Every mutation supports `--dry-run`
- Config is lazy-loaded — the `init` command works without any config file

## Automations

Hooks, skills, and subagents in `.claude/`:

**Hooks** (`settings.json`):
- PostToolUse: ruff auto-lint/format on `.py` edits
- PostToolUse: auto-run affected test file on source edits
- PreToolUse: block `.env`/`.pem`/`.key`/credentials edits
- PreToolUse: block `pyproject.toml` edits (requires explicit approval)

**Skills** (`skills/`):
- `add-command` — step-by-step workflow for adding new CLI commands
- `clickup-cli` — usage guide for the CLI itself
- `release` — version bump, build, PyPI publish workflow
- `validate-output` — verify JSON stdout contract across all commands
- `changelog` — generate categorized release notes from git log

**Subagents** (`agents/`):
- `test-writer` — generate pytest tests following existing patterns
- `api-compatibility-checker` — cross-ref CLI endpoints against ClickUp API docs
