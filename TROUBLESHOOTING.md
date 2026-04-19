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

Some read-path helpers intentionally perform safe lookup requests during dry-run so the CLI can resolve scopes or validate IDs before returning the preview.
