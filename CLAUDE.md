# ClickUp CLI — Development Instructions

## What This Is

A ClickUp CLI for developers and AI agents. JSON-only stdout, errors to stderr, dry-run on all mutations.

## Package Structure

```
src/clickup_cli/
├── cli.py           # root parser, dispatch, main() — delegates to command modules
├── client.py        # ClickUpClient API wrapper (rate limiting, dry-run, debug)
├── config.py        # Config loader (lazy, fallback chain, workspace auto-detect)
├── helpers.py       # output(), error(), compact_task(), etc.
└── commands/
    ├── __init__.py  # HANDLERS dict
    ├── tasks.py     # tasks parser + handlers (list/get/create/update/search/delete/move/merge)
    ├── comments.py  # comments parser + handlers (list/add/update/delete/thread/reply)
    ├── docs.py      # docs parser + handlers (list/get/create/pages/get-page/edit-page/create-page)
    ├── folders.py   # folders parser + handlers (list/get/create/update/delete)
    ├── lists.py     # lists parser + handlers (list/get/create/update/delete)
    ├── spaces.py    # spaces parser + handlers (list/get/statuses)
    ├── tags.py      # tags parser + handlers (list/add/remove)
    ├── team.py      # team parser + handlers (whoami/members)
    └── init.py      # clickup init setup command
```

Each command module owns both its argparse parser definition (`register_parser()`) and its handler functions. `cli.py` builds the root parser and delegates to each module's `register_parser(subparsers, F)`.

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

`tasks create` auto-infers `--space` from `--list` via a lazy API lookup (`GET /v2/list/{id}`). The `_infer_space_from_list()` function in tasks.py reverse-maps the space ID to a config name. This eliminates the most common agent error.

## Development Setup

```bash
pip install -e ".[dev]"
pytest -v
ruff check src/ tests/
```

## Adding a New Command

1. Create or extend a file in `src/clickup_cli/commands/`
2. Add the handler function and `register_parser()` in the same module
3. Register the handler in `commands/__init__.py` HANDLERS dict
4. If it's a new command group, call `register_parser()` from `cli.py`'s `build_parser()`
5. Add detailed `--help` text (description + epilog with examples)
6. Mutating commands must support `--dry-run`
7. All output goes to stdout as JSON, errors to stderr
8. Add tests in `tests/`

## Rules

- Help text must be self-sufficient — an agent should use `--help` to discover correct usage
- No workspace-specific values in help text or source code
- Stdout is always JSON. Errors and warnings go to stderr.
- Every mutation supports `--dry-run`
- Config is lazy-loaded — the `init` command works without any config file
