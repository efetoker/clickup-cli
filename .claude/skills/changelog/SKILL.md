---
name: changelog
description: Generate release notes from git log since last tag, categorized by commit type
disable-model-invocation: true
---

# Generate Changelog Entry

Generate a categorized changelog entry for the next release.

## Steps

1. Find the last release tag:

```bash
git describe --tags --abbrev=0 2>/dev/null || echo "none"
```

2. Get all commits since that tag (or all commits if no tag exists):

```bash
git log $(git describe --tags --abbrev=0 2>/dev/null)..HEAD --oneline 2>/dev/null || git log --oneline
```

3. Categorize commits by their prefix:
   - **Added** — `feat:`, `add:`
   - **Changed** — `refactor:`, `update:`, `improve:`
   - **Fixed** — `fix:`, `bugfix:`
   - **Testing** — `test:`
   - **Docs** — `docs:`
   - **Other** — everything else

4. Draft a markdown changelog entry:

```markdown
## [vX.Y.Z] - YYYY-MM-DD

### Added
- Description of new features

### Changed
- Description of changes

### Fixed
- Description of bug fixes
```

5. Present the draft for review. Do not write to any file until the user approves.
