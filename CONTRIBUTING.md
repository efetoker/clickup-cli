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
```

All tests must pass before submitting a PR.

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
2. Implement `register_parser()` and handler functions in the same module
3. Register the handler in `commands/__init__.py`
4. Use `add_id_argument()` from `helpers.py` for positional ID arguments (provides both positional and `--flag` forms)
5. Add `--help` text with description and usage examples
6. Add tests in `tests/`

## Submitting Changes

1. Fork the repo and create a feature branch
2. Make your changes with tests
3. Run `pytest -v` and `ruff check src/ tests/`
4. Open a PR with a clear description of what changed and why

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
