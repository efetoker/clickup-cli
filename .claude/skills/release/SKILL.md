---
name: release
description: Bump version, validate, tag, and build for PyPI release
disable-model-invocation: true
---

# Release Workflow

`RELEASE.md` is the canonical release checklist. Follow it step by step; update that file first if the workflow changes.

## Agent Guardrails

- Do not publish to PyPI, push tags, push branches, or create GitHub Releases without explicit maintainer confirmation.
- Before changing the version, verify the current git/PyPI tag state described in `RELEASE.md`.
- When bumping the version, update both `src/clickup_cli/__init__.py` and `tests/test_cli.py::test_version_flag`.
- Run the full pre-flight from `RELEASE.md`: `ruff check src/ tests/`, `pytest -v`, and `scripts/validate-cli-output.sh`.
- Build artifacts with `python -m build` and validate with `python -m twine check dist/*` before any publish/push step.

## Confirmation Gates

Ask the maintainer before:

- Uploading to PyPI.
- Pushing `main` or release tags.
- Creating the GitHub Release or uploading release artifacts.
