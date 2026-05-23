# Integration Guide

## Contract

`clickup-cli` is designed for scripts, terminals, and agent runtimes that need predictable command behavior.

- Successful output is JSON on stdout
- Errors and warnings go to stderr
- Mutating commands support `--dry-run`
- Global flags such as `--pretty`, `--dry-run`, and `--debug` work before or after the command group

## Output Modes

- Default task list and search output is compact
- `--fields` returns only the requested fields on task list/search/get flows
- `--full` returns full task objects with normalized status metadata where applicable
- `fields list` returns `fields`, `count`, and `scope` for the inspected list
- `task-types list` returns `task_types`, `count`, `scope`, `available`, `scope_applied: false`, and `source`

## Bounded Defaults

- `tasks list` and `tasks search` use a bounded default scan of up to 2 pages and return `pages_fetched`, `results_complete`, and `results_truncated`
- `tasks get` fetches a bounded default comment slice and returns `comment_count_returned`, `comments_complete`, and `comments_truncated`
- Use `--all-pages` or `--all-comments` when your integration needs exhaustive results

## IDs and Scope

- Positional IDs also accept flag forms such as `--task-id`, `--doc-id`, `--page-id`, and `--comment-id`
- `--space` accepts either a configured alias or a raw numeric space ID where supported
- `tasks create` can infer `--space` from `--list`
- `tasks search --space` scopes to the full space by expanding to the lists in that space
- `fields list --space` inspects the configured default list for that space, or the first folderless list if no default `list_id` is configured; use `--list` for folder-contained lists
- `task-types list` is workspace-scoped; `--space` and `--list` are echoed in `scope` only and do not filter results
- `clickup init` generates space aliases by lowercasing space names and replacing spaces with hyphens; it stores `space_id` values but no default `list_id` values

## Safe Usage Notes

- Validate response metadata instead of assuming a default scan is exhaustive
- Use `--dry-run` before automating mutations in a new environment
- Use `tasks bulk ...` and backup commands for migration workflows that need resumable failure output or local JSON snapshots
- List backups contain `list.json`, `tasks.json`, `tasks/<task_id>.json`, and `manifest.json`; folder backups contain `folder.json`, nested list backups, and a folder `manifest.json`
- Treat doc IDs and page IDs as different values

## Reliability

- Safe GET requests retry transient 502/503/504 responses up to three attempts
- A 429 with `X-RateLimit-Reset` sleeps until reset and retries once
- Successful responses with fewer than 10 remaining requests sleep until reset before returning, so long-running automation should expect occasional proactive waits
