---
name: validate-output
description: Verify the CLI's JSON-only stdout contract across all commands. Run after adding new commands or modifying output logic.
---

# Validate CLI Output Contract

Verify that every CLI command produces valid JSON on stdout and errors on stderr.

## Steps

1. Get all command groups and subcommands:

```bash
clickup --help 2>/dev/null
```

2. For each command group, get its subcommands:

```bash
clickup <group> --help 2>/dev/null
```

3. For each subcommand that supports `--dry-run`, run it with dummy arguments and `--dry-run`:

```bash
clickup --dry-run <group> <subcommand> <required-args> 2>/dev/null
```

   Stateful previews such as `tags edit`, `tags migrate`, and strict tag checks read live state even in dry-run, so dummy arguments against the real API are not an offline check for them. Cover those with synthetic fake API responses in the test suite and assert valid JSON plus zero mutating requests.

4. Validate that stdout is valid JSON by piping through `python3 -c "import sys,json; json.load(sys.stdin)"`.

5. For read-only commands (list, get, search), run with `--help` and verify the help text renders without errors.

6. Report results as a summary:
   - Total commands checked
   - Commands producing valid JSON
   - Commands with issues (list each with the error)

## What Counts as a Failure

- Any stdout output that is not valid JSON
- Any command that crashes (non-zero exit without stderr message)
- Help text that fails to render
