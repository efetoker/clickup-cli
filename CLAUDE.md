# ClickUp CLI — Development Instructions

## What This Is

A ClickUp CLI for developers and AI agents. JSON-only stdout, errors to stderr, dry-run on all mutations.

## Package Structure

```
src/clickup_cli/
├── cli.py           # argparse parser + dispatch + main()
├── client.py        # ClickUpClient API wrapper (rate limiting, dry-run)
├── config.py        # Config loader (lazy, fallback chain, workspace auto-detect)
├── helpers.py       # output(), error(), compact_task(), etc.
└── commands/
    ├── __init__.py  # HANDLERS dict
    ├── tasks.py     # tasks CRUD + search/move/merge
    ├── comments.py  # comments CRUD + threading
    ├── docs.py      # docs + pages CRUD
    ├── folders.py   # folders CRUD
    ├── lists.py     # lists CRUD
    ├── spaces.py    # spaces read-only
    ├── tags.py      # tags add/remove
    ├── team.py      # whoami, members
    └── init.py      # clickup init setup command
```

## Development Setup

```bash
pip install -e ".[dev]"
pytest -v
ruff check src/ tests/
```

## Adding a New Command

1. Create or extend a file in `src/clickup_cli/commands/`
2. Add detailed `--help` text (description + epilog with examples)
3. Register the handler in `commands/__init__.py` HANDLERS dict
4. Add the subparser in `cli.py` under the appropriate group
5. Mutating commands must support `--dry-run`
6. All output goes to stdout as JSON, errors to stderr
7. Add tests in `tests/`

## Rules

- Help text must be self-sufficient — an agent should use `--help` to discover correct usage
- No workspace-specific values in help text or source code
- Stdout is always JSON. Errors and warnings go to stderr.
- Every mutation supports `--dry-run`
- Config is lazy-loaded — the `init` command works without any config file
