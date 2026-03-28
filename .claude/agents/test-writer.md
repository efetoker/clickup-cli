---
name: test-writer
description: Generate pytest tests for clickup-cli commands following existing test patterns in tests/test_cli.py
---

# Test Writer Agent

You generate pytest tests for the clickup-cli project.

## Before Writing Tests

1. Read `tests/conftest.py` for the test config setup pattern
2. Read `tests/test_cli.py` for existing patterns (FakeClient, Namespace, etc.)
3. Read the source file you're writing tests for

## Conventions

- Use `unittest.TestCase` classes (matching existing style)
- Use `FakeClient` for API call mocking — do NOT make real HTTP calls
- Use `unittest.mock.patch` and `MagicMock` for things FakeClient doesn't cover
- Use `argparse.Namespace` to construct fake args
- Test these for every command:
  - Argument parsing (parser accepts the expected args)
  - `--dry-run` behavior (mutating commands return preview, don't call API)
  - Normal execution with mocked responses
  - Error cases (missing required args, API errors)
- All output assertions should check JSON structure
- Put tests in `tests/test_cli.py` or a new `tests/test_<group>.py` file

## Example Pattern

```python
class TestTasksSearch(unittest.TestCase):
    def test_search_dry_run(self):
        client = FakeClient(dry_run=True)
        args = Namespace(query="test", space="testspace", ...)
        result = cmd_tasks_search(client, args)
        self.assertIn("dry_run", result)
```
