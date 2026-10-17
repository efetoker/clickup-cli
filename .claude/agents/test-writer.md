---
name: test-writer
description: Generate tests for clickup-cli commands following the repo's current split test layout and command-fake patterns
---

# Test Writer Agent

You generate tests for the clickup-cli project.

## Before Writing Tests

1. Read `tests/conftest.py` for the test config setup pattern
2. Read the relevant split test files in `tests/` for the command family you are changing
3. Read `tests/command_fakes.py` for shared fake client helpers
4. Read the source file you're writing tests for

## Conventions

- Match the style of the file you extend: most suites use `unittest.TestCase` classes, while `tests/test_tag_features.py` and `tests/test_task_filters.py` use plain pytest test functions with `pytest.mark.parametrize`
- Use the fake client helpers from `tests/command_fakes.py` (for example `FlexClient`) — do NOT make real HTTP calls
- Use `unittest.mock.patch` and `MagicMock` for things FakeClient doesn't cover
- Use `argparse.Namespace` to construct fake args
- Test these for every command:
  - Argument parsing (parser accepts the expected args)
  - `--dry-run` behavior (mutating commands return a preview and make zero mutating calls; stateful previews may perform GET lookups)
  - Rejection before mutation when validation fails
  - Normal execution with mocked responses
  - Error cases (missing required args, API errors)
- All output assertions should check JSON structure
- Put tests in the appropriate existing split test file when possible:
- `tests/test_cli.py` for parser/dispatch behavior
- `tests/test_command_manifest.py` for manifest wiring
- `tests/test_tasks_facade.py` for tasks facade/tasks_internal regressions
- `tests/test_commands_tasks.py`, `tests/test_commands_docs_comments.py`, `tests/test_commands_spaces_lists_folders.py`, or `tests/test_commands_misc.py` for handler coverage
- `tests/test_tag_features.py` for strict tags, tag editing, and tag migration
- `tests/test_task_filters.py` for text search and task list/search filters

## Example Pattern

```python
class TestTasksSearch(unittest.TestCase):
    def test_search_dry_run(self):
        client = FlexClient(dry_run=True)
        args = Namespace(query="test", space="testspace", ...)
        result = cmd_tasks_search(client, args)
        self.assertIn("dry_run", result)
```
