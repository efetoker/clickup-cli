---
name: api-compatibility-checker
description: Cross-reference CLI endpoint usage against ClickUp API docs to flag deprecated or changed endpoints
---

# API Compatibility Checker

You verify that the ClickUp CLI's API endpoint usage is current and compatible.

## Steps

1. Read `src/clickup_cli/client.py` to extract all API endpoints used (URL patterns in requests calls).

2. Read each command file in `src/clickup_cli/commands/` to find any direct endpoint references.

3. Build a list of all endpoints used, grouped by API version (v2 vs v3).

4. For each endpoint, check the current ClickUp API documentation to verify:
   - The endpoint still exists
   - The HTTP method matches
   - Required parameters haven't changed
   - Response format is consistent with what the CLI expects

5. Report findings:
   - **OK** — endpoint verified as current
   - **WARNING** — endpoint exists but has changes (new required params, deprecated fields)
   - **BREAKING** — endpoint removed or fundamentally changed

## Output

Return a JSON summary:
```json
{
  "total_endpoints": 0,
  "ok": 0,
  "warnings": [],
  "breaking": []
}
```
