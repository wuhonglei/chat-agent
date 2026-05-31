"""Map shell MCP structured_content to frontend display payloads."""

from __future__ import annotations

from typing import Any

from app.schemas.shell_display import ShellExecDisplayItem


def build_shell_display_items(
    structured_content: dict[str, Any],
) -> list[dict[str, Any]]:
    item = ShellExecDisplayItem.from_structured_content(structured_content)
    return [item.model_dump(mode="json")]
