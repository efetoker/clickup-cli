# Release Guide

## Maintainer Checklist

1. Update user-facing docs if command behavior changed
2. Run `ruff check src/ tests/`
3. Run `pytest -v`
4. Run `scripts/validate-cli-output.sh`
5. Review `CHANGELOG.md` and release notes inputs
6. Publish the new version using the project's normal packaging workflow
7. Verify the release on PyPI and the GitHub releases page

## Notes

- Keep public docs aligned with actual CLI help text and tested behavior
- Do not document unsupported ClickUp API surface as if it is implemented
- If release steps change, update this file and `CONTRIBUTING.md` together
