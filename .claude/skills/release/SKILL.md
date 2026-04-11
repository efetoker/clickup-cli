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
clickup --help                          # smoke test
bash scripts/validate-cli-output.sh     # JSON stdout contract
```

All must pass before proceeding.

Also verify the tag for the current `__version__` doesn't already exist on git or PyPI — previous releases were shipped to PyPI without a matching git tag once, which left a gap. If a gap exists, backfill the missing tag at the correct commit (`git tag v<missing> <sha> && git push origin v<missing>`) and add a CHANGELOG entry for it before the new version.

## 2. Bump version

The version is dynamic (read by Hatch from `src/clickup_cli/__init__.py`). Update it following semver:
- **patch** (1.x.Y): bug fixes
- **minor** (1.X.0): new commands or features
- **major** (X.0.0): breaking changes

Also update `tests/test_cli.py::test_version_flag` — the assertion string must match.

## 3. Update CHANGELOG

Summarize changes since the last tag. Start from:

```bash
git log $(git describe --tags --abbrev=0)..HEAD --oneline
```

Group entries into Features / Fixes / Internal. Keep the top of `CHANGELOG.md` the same format as prior entries (one dated section per version, newest first).

## 4. Commit and tag

```bash
git add -A
git commit -m "release: v<version>"
git tag v<version>
```

Do NOT push yet — everything local until the build is verified.

## 5. Build

```bash
pip install build
rm -rf dist/ build/
python -m build
python -m twine check dist/*
```

Verify both the sdist and the wheel are present, file sizes look sane, and the version number is in the filenames.

## 6. Publish to PyPI (requires user confirmation)

**Ask Efe before running this step.**

Claude Code's `!` bash prompt cannot allocate a tty, so `twine upload` run inline will `EOFError` on the getpass prompt. Use one of these two paths:

```bash
# Option A — separate real terminal (safest):
#   Efe runs `python3 -m twine upload dist/*` in a new terminal tab.
# Option B — inline with env token (exposes token in shell history):
#   TWINE_USERNAME=__token__ TWINE_PASSWORD='pypi-...' python3 -m twine upload dist/*
```

Wait for confirmation that PyPI shows the new version before moving on. Verify with:

```bash
curl -s https://pypi.org/pypi/clickup-cli/json | python3 -c "import json,sys; print(json.load(sys.stdin)['info']['version'])"
```

## 7. Push main + tag

```bash
git push origin main
git push origin v<version>
```

## 8. Create the GitHub Release

Pushing a tag does NOT create a GitHub Release — Releases are a separate object layered on top of tags. Without this step, `github.com/<repo>/releases` still shows the previous version as "Latest" even though the tag is live.

```bash
gh release create v<version> \
  dist/clickup_cli-<version>-py3-none-any.whl \
  dist/clickup_cli-<version>.tar.gz \
  --title "v<version>" \
  --notes "$(...release notes from CHANGELOG...)"
```

Attach both dist artifacts. Use the CHANGELOG entry for the notes (or inline them if the CHANGELOG entry is too terse).

Verify `gh release list` shows the new version with the `Latest` marker.

