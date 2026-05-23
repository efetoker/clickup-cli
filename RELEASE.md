# Release Guide

## Maintainer Checklist

This file is the canonical release checklist. Repo-local agent skills may add prompts or guardrails, but release steps should be updated here first.

1. Update user-facing docs if command behavior changed.
2. Run pre-flight checks:
   ```bash
   ruff check src/ tests/
   pytest -v
   scripts/validate-cli-output.sh
   ```
3. Verify the tag for the current `__version__` does not already exist on git or PyPI. If a previous PyPI release is missing a git tag, backfill the missing tag at the correct commit before releasing.
4. Bump the dynamic version in `src/clickup_cli/__init__.py` and update `tests/test_cli.py::test_version_flag` to match.
5. Update `CHANGELOG.md` from commits since the last tag:
   ```bash
   git log $(git describe --tags --abbrev=0)..HEAD --oneline
   ```
6. Commit the release changes and create a local tag:
   ```bash
   git add -A
   git commit -m "release: v<version>"
   git tag v<version>
   ```
7. Build and validate distributions:
   ```bash
   python -m build
   python -m twine check dist/*
   ```
8. Publish to PyPI only after explicit maintainer confirmation, then verify PyPI shows the new version.
9. Push `main` and the tag.
10. Create a GitHub Release and attach both `dist/` artifacts.

## Notes

- Keep public docs aligned with actual CLI help text and tested behavior
- Do not document unsupported ClickUp API surface as if it is implemented
- If release steps change, update this file first, then update `CONTRIBUTING.md` or agent skills only if their pointers become stale
