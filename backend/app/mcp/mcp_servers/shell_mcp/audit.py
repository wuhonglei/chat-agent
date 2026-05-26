"""Audit logging for sandbox command execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal

from app.utils.logger import logger

AuditVerdict = Literal["block", "warn", "pass"]


@dataclass
class SandboxAuditEntry:
    """Audit log entry for sandbox execution."""

    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    user_id: str = ""
    conversation_id: str = ""
    command: str = ""
    description: str = ""
    verdict: AuditVerdict = "pass"
    block_reason: str | None = None
    return_code: int | None = None
    duration_ms: int | None = None
    output_size: int = 0


def log_audit_entry(entry: SandboxAuditEntry) -> None:
    """Log audit entry in structured format."""
    logger.info(
        "Sandbox audit",
        timestamp=entry.timestamp.isoformat(),
        user_id=entry.user_id,
        conversation_id=entry.conversation_id,
        command=entry.command[:200],
        description=entry.description,
        verdict=entry.verdict,
        block_reason=entry.block_reason,
        return_code=entry.return_code,
        duration_ms=entry.duration_ms,
        output_size=entry.output_size,
    )
