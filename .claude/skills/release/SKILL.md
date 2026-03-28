---
name: release
description: Bump version, validate, tag, and build for PyPI release
disable-model-invocation: true
---

# Release Workflow

Follow these steps to publish a new release of clickup-cli.

## 1. Pre-flight checks

```bash
ruff check src/ tests/
pytest -v
clickup --help  # smoke test
```

All must pass before proceeding.

## 2. Bump version

The version is in `src/clickup_cli/__init__.py`. Update it following semver:
- **patch** (0.x.Y): bug fixes
- **minor** (0.X.0): new commands or features
- **major** (X.0.0): breaking changes

## 3. Update changelog

If `CHANGELOG.md` exists, add an entry for the new version with a summary of changes since the last tag:

```bash
git log $(git describe --tags --abbrev=0)..HEAD --oneline
```

## 4. Commit and tag

```bash
git add -A
git commit -m "release: v<version>"
git tag v<version>
```

## 5. Build

```bash
pip install build
python -m build
```

Verify the dist/ output looks correct (check file sizes, version in filenames).

## 6. Publish (requires user confirmation)

**Ask the user before running this step.**

```bash
pip install twine
twine upload dist/*
```

## 7. Push

```bash
git push origin main --tags
```
