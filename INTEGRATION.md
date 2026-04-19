# Integration Guide

## Contract

`clickup-cli` is designed for scripts, terminals, and agent runtimes that need predictable command behavior.

- Successful output is JSON on stdout
- Errors and warnings go to stderr
- Mutating commands support `--dry-run`
- Global flags such as `--pretty`, `--dry-run`, and `--debug` work before or after the command group

## Output Modes

- Default task list and search output is compact
- `--fields` returns only the requested fields
- `--full` returns full task objects with normalized status metadata

## Bounded Defaults

- `tasks list` and `tasks search` use a bounded default page scan and return `pages_fetched`, `results_complete`, and `results_truncated`
- `tasks get` fetches a bounded default comment slice and returns `comment_count_returned`, `comments_complete`, and `comments_truncated`
- Use `--all-pages` or `--all-comments` when your integration needs exhaustive results

## IDs and Scope

- Positional IDs also accept flag forms such as `--task-id`, `--doc-id`, `--page-id`, and `--comment-id`
- `--space` accepts either a configured alias or a raw numeric space ID where supported
- `tasks create` can infer `--space` from `--list`
- `tasks search --space` scopes to the full space by expanding to the lists in that space

## Safe Usage Notes

- Validate response metadata instead of assuming a default scan is exhaustive
- Use `--dry-run` before automating mutations in a new environment
- Treat doc IDs and page IDs as different values
