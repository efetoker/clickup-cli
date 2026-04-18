"""Runtime context passed from the CLI entrypoint into command handlers."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class RuntimeContext:
    workspace_id: str
    user_id: str = ""
    spaces: dict = field(default_factory=dict)
