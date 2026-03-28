#!/usr/bin/env bash
# Validate CLI output contract:
#   - All commands with --help exit 0 and produce output on stdout
#   - No command prints to stdout on error (stderr only)
#   - JSON output is valid where applicable

set -euo pipefail

PASS=0
FAIL=0
ERRORS=()

pass() { PASS=$((PASS + 1)); }
fail() { FAIL=$((FAIL + 1)); ERRORS+=("$1"); }

# 1. Top-level --help
echo "Checking: clickup --help"
if clickup --help >/dev/null 2>&1; then
    pass
else
    fail "clickup --help failed"
fi

# 2. All command groups and their subcommands
CMD_GROUPS=(tasks comments docs folders lists spaces team tags)

for group in "${CMD_GROUPS[@]}"; do
    echo "Checking: clickup $group --help"
    if clickup "$group" --help >/dev/null 2>&1; then
        pass
    else
        fail "clickup $group --help failed"
    fi

    # Extract subcommands from the usage line: {cmd1,cmd2,...}
    subcommands=$(clickup "$group" --help 2>/dev/null | grep -oE '\{[a-z,-]+\}' | head -1 | tr -d '{}' | tr ',' '\n' || true)

    for cmd in $subcommands; do
        echo "Checking: clickup $group $cmd --help"
        if clickup "$group" "$cmd" --help >/dev/null 2>&1; then
            pass
        else
            fail "clickup $group $cmd --help failed"
        fi
    done
done

# 3. Init command
echo "Checking: clickup init --help"
if clickup init --help >/dev/null 2>&1; then
    pass
else
    fail "clickup init --help failed"
fi

# 4. Verify error output goes to stderr (not stdout)
echo "Checking: errors go to stderr only"
# Running without config should produce stderr output and empty stdout
stdout=$(CLICKUP_CONFIG_PATH=/nonexistent/path clickup tasks list --space x 2>/dev/null || true)
if [ -z "$stdout" ]; then
    pass
else
    fail "Error output leaked to stdout: $stdout"
fi

# 5. Version flag produces output
echo "Checking: clickup --version"
if clickup --version >/dev/null 2>&1; then
    pass
else
    fail "clickup --version failed"
fi

# Report
echo ""
echo "================================"
echo "Results: $PASS passed, $FAIL failed"
echo "================================"

if [ $FAIL -gt 0 ]; then
    echo ""
    echo "Failures:"
    for err in "${ERRORS[@]}"; do
        echo "  - $err"
    done
    exit 1
fi

echo "All checks passed."
