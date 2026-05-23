# Contributing

Thanks for your interest in clickup-cli.

## Getting Started

```bash
git clone https://github.com/efetoker/clickup-cli.git
cd clickup-cli
pip install -e ".[dev]"
```

## Running Tests

```bash
pytest -v
scripts/validate-cli-output.sh
```

Current suite shape:

- `tests/test_cli.py` — parser, dispatch, global flags, ID alias resolution
- `tests/test_client.py` — API wrapper behavior, dry-run, debug, retries
- `tests/test_command_manifest.py` — manifest-derived registration and handlers
- `tests/test_commands_tasks.py` — task commands and task-specific behavior
- `tests/test_commands_docs_comments.py` — docs and comments commands
- `tests/test_commands_metadata.py` — fields and task-types metadata commands
- `tests/test_commands_spaces_lists_folders.py` — spaces, lists, folders, privacy
- `tests/test_commands_misc.py` — tags, team, init, misc dispatch coverage
- `tests/test_config.py` — config loading and fallback rules
- `tests/test_helpers.py` — stdout/stderr helpers, task formatting, pagination helpers
- `tests/test_tasks_facade.py` — task facade exports

Use `pytest --collect-only -q` when you need the current collection count.

## Linting

```bash
ruff check src/ tests/
ruff format src/ tests/
```

## Guidelines

- **JSON stdout, errors to stderr** — all commands follow this convention
- **Dry-run on mutations** — every mutating command must support `--dry-run`
- **Help text is documentation** — `--help` should be self-sufficient for discovering usage
- **No workspace-specific values** — help text and source must not contain hardcoded workspace IDs, space names, or user data
- **Tests required** — new commands need test coverage in `tests/`

## Adding a New Command

1. Create or extend a file in `src/clickup_cli/commands/`
2. Keep parser registration and handlers in the same command module, or behind the existing task facade/internal split when working on tasks
3. Expose a `COMMAND_MANIFEST` from that module and add it to `COMMAND_MANIFESTS` in `src/clickup_cli/commands/__init__.py`
4. Let the derived `HANDLERS` map pick up handlers from the manifest instead of maintaining a separate manual registry
5. Use `add_id_argument()` from `helpers.py` for positional ID arguments so both positional and `--flag` forms work
6. Add self-sufficient `--help` text with examples, return-shape notes, and `--dry-run` guidance for mutating commands
7. Add or update focused tests in the relevant `tests/test_*.py` file

## Submitting Changes

1. Fork the repo and create a feature branch
2. Make your changes with tests
3. Run `pytest -v`, `ruff check src/ tests/`, and `scripts/validate-cli-output.sh`
4. Open a PR with a clear description of what changed and why

## Maintainer Workflows

- Maintainer release steps live in [RELEASE.md](RELEASE.md)
- Public support and disclosure docs live in `README.md`, `SECURITY.md`, `CODE_OF_CONDUCT.md`, `INTEGRATION.md`, and `TROUBLESHOOTING.md`

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
