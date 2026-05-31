"""Command-level security auditing for shell MCP (deerflow SandboxAuditMiddleware equivalent)."""

from __future__ import annotations

import re
import shlex
from dataclasses import dataclass
from typing import Literal

from app.mcp.mcp_servers.shell_mcp.config import shell_config

AuditVerdict = Literal["block", "warn", "pass"]

# Each pattern is compiled once at import time.
_HIGH_RISK_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"rm\s+-[^\s]*r[^\s]*\s+(/\*?|~/?\*?|/home\b|/root\b)\s*$"),
    re.compile(r"dd\s+if="),
    re.compile(r"mkfs"),
    re.compile(r"cat\s+/etc/shadow"),
    re.compile(r">+\s*/etc/"),
    re.compile(r"\|\s*(ba)?sh\b"),
    re.compile(r"[`$]\(?\s*(curl|wget|bash|sh|python|ruby|perl|base64)"),
    re.compile(r"base64\s+.*-d.*\|"),
    re.compile(r">+\s*(/usr/bin/|/bin/|/sbin/)"),
    re.compile(r">+\s*~/?\.(bashrc|profile|zshrc|bash_profile)"),
    re.compile(r"/proc/[^/]+/environ"),
    re.compile(r"\b(LD_PRELOAD|LD_LIBRARY_PATH)\s*="),
    re.compile(r"/dev/tcp/"),
    re.compile(r"\S+\(\)\s*\{[^}]*\|\s*\S+\s*&"),
    re.compile(r"while\s+true.*&\s*done"),
]

_MEDIUM_RISK_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"chmod\s+777"),
    re.compile(r"pip3?\s+install"),
    re.compile(r"apt(-get)?\s+install"),
    re.compile(r"\b(sudo|su)\b"),
    re.compile(r"\bPATH\s*="),
]

MEDIUM_RISK_WARNING = (
    "\n\n⚠️ Warning: `{command}` is a medium-risk command that "
    "may modify the runtime environment."
)


@dataclass(frozen=True)
class CommandAuditResult:
    """Result of command security audit."""

    verdict: AuditVerdict
    reason: str | None = None


def _split_compound_command(command: str) -> list[str]:
    """Split a compound command into sub-commands (quote-aware)."""
    parts: list[str] = []
    current: list[str] = []
    in_single_quote = False
    in_double_quote = False
    escaping = False
    index = 0

    while index < len(command):
        char = command[index]

        if escaping:
            current.append(char)
            escaping = False
            index += 1
            continue

        if char == "\\" and not in_single_quote:
            current.append(char)
            escaping = True
            index += 1
            continue

        if char == "'" and not in_double_quote:
            in_single_quote = not in_single_quote
            current.append(char)
            index += 1
            continue

        if char == '"' and not in_single_quote:
            in_double_quote = not in_double_quote
            current.append(char)
            index += 1
            continue

        if not in_single_quote and not in_double_quote:
            if command.startswith("&&", index) or command.startswith("||", index):
                part = "".join(current).strip()
                if part:
                    parts.append(part)
                current = []
                index += 2
                continue
            if char == ";":
                part = "".join(current).strip()
                if part:
                    parts.append(part)
                current = []
                index += 1
                continue

        current.append(char)
        index += 1

    if in_single_quote or in_double_quote or escaping:
        return [command]

    part = "".join(current).strip()
    if part:
        parts.append(part)
    return parts if parts else [command]


def _classify_single_command(command: str) -> AuditVerdict:
    """Classify a single (non-compound) command."""
    normalized = " ".join(command.split())

    for pattern in _HIGH_RISK_PATTERNS:
        if pattern.search(normalized):
            return "block"

    try:
        tokens = shlex.split(command)
        joined = " ".join(tokens)
        for pattern in _HIGH_RISK_PATTERNS:
            if pattern.search(joined):
                return "block"
    except ValueError:
        return "block"

    for pattern in _MEDIUM_RISK_PATTERNS:
        if pattern.search(normalized):
            return "warn"

    return "pass"


def classify_command(command: str) -> AuditVerdict:
    """Return block, warn, or pass for a shell command string."""
    normalized = " ".join(command.split())
    for pattern in _HIGH_RISK_PATTERNS:
        if pattern.search(normalized):
            return "block"

    sub_commands = _split_compound_command(command)
    worst: AuditVerdict = "pass"
    for sub in sub_commands:
        verdict = _classify_single_command(sub)
        if verdict == "block":
            return "block"
        if verdict == "warn":
            worst = "warn"
    return worst


def _validate_input(command: str) -> str | None:
    """Return rejection reason if input is invalid, else None."""
    if not command.strip():
        return "empty command"
    if len(command) > shell_config.max_command_chars:
        return "command too long"
    if "\x00" in command:
        return "null byte detected"
    return None


def audit_command(command: str) -> CommandAuditResult:
    """Audit a shell command; block on invalid input or high-risk patterns."""
    reject_reason = _validate_input(command)
    if reject_reason:
        return CommandAuditResult(verdict="block", reason=reject_reason)

    verdict = classify_command(command)
    if verdict == "block":
        return CommandAuditResult(
            verdict="block",
            reason="security violation detected",
        )
    return CommandAuditResult(verdict=verdict)


def format_medium_risk_warning(command: str) -> str:
    """Return deerflow-style warning suffix for medium-risk commands."""
    return MEDIUM_RISK_WARNING.format(command=command)
