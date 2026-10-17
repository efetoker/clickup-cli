# Troubleshooting

## `Unknown space: ...`

Configured space aliases are case-sensitive. Use the exact alias from your config file or pass a raw numeric space ID where supported.

## `No API token found`

Run `clickup init` or set `CLICKUP_API_TOKEN`.

## `tasks get` returned fewer comments than expected

That is the default bounded behavior. Check `comments_complete` and `comments_truncated`, or rerun with `--all-comments`.

## `tasks list` or `tasks search` returned incomplete results

Check `results_complete`, `results_truncated`, and `pages_fetched`. Use `--all-pages` when you need an exhaustive scan.

## `docs edit-page` or `docs get-page` returns not found

Doc ID and page ID are different. Use `clickup docs pages <doc_id>` first, then use the returned page ID.

## `python -m clickup_cli.cli ...` does not work

Use `python3 -m clickup_cli.cli ...` on systems where `python` is not available, or install the package and use the `clickup` entrypoint.

## `--dry-run` still performed a read request

Some read-path helpers intentionally perform safe lookup requests during dry-run so the CLI can resolve scopes or validate IDs before returning the preview. `tags edit`, `tags migrate`, and strict tag checks also read live tags and tasks to build their previews. Dry-run never sends a mutating request.

## A tag was rejected with strict tags enabled

The tag does not exist in the task's Space. Check `clickup tags list --space <space>` and create the tag with `tags create` if it belongs there. Strict validation runs before any change, so nothing was modified. Use `--no-strict-tags` only when you want ClickUp to create the tag implicitly.

## `tags migrate` stopped partway through

Completed operations are not rolled back. Read `failed`, `remaining`, `resume_from`, and `pending_space_tag_deletions` from the output, then run the same map with `--dry-run` to get a fresh plan for what is left. If some source tags were already deleted, remove them from the map before retrying, otherwise validation fails.

## `tasks search` returned no matches

Every word in the query has to appear in the task name or description, and comments are not searched. Check `results_complete` before treating an empty result as proof that no task matches, and use `--all-pages` for an exhaustive search.
