"""Command policy engine with AST-level parsing."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.utils.logger import logger


@dataclass
class PolicyDecision:
    """Policy engine decision."""

    allowed: bool
    reason: str | None = None


class CommandPolicyEngine:
    """Three-layer policy engine for command validation.

    Layer 1: bashlex AST parsing (detect dangerous patterns)
    Layer 2: Command whitelist
    Layer 3: Argument/path constraints
    """

    # Layer 2: Allowed commands
    ALLOWED_COMMANDS = {
        # Basic tools
        "ls",
        "cat",
        "grep",
        "find",
        "head",
        "tail",
        "wc",
        "sort",
        "cp",
        "mv",
        "rm",
        "mkdir",
        "touch",
        "echo",
        "cd",
        "pwd",
        "whoami",
        "date",
        "env",
        "printenv",
        "which",
        "file",
        "stat",
        "diff",
        "patch",
        "ln",
        "readlink",
        "basename",
        "dirname",
        "tr",
        "cut",
        "paste",
        "join",
        "uniq",
        "tee",
        # Development tools
        "node",
        "npm",
        "npx",
        "python",
        "python3",
        "pip",
        "pip3",
        "git",
        "cargo",
        "go",
        "pnpm",
        "yarn",
        "bun",
        "deno",
        "tsx",
        "ts-node",
        "babel",
        "esbuild",
        # Build tools
        "make",
        "cmake",
        "gcc",
        "g++",
        "clang",
        "rustc",
        # Data tools
        "jq",
        "yq",
        "xargs",
        "awk",
        "sed",
        # Archive
        "tar",
        "gzip",
        "gunzip",
        "zip",
        "unzip",
        # Other safe tools
        "time",
        "timeout",
        "true",
        "false",
        "test",
    }

    # Layer 2: Blocked commands (always dangerous)
    BLOCKED_COMMANDS = {
        "sudo",
        "su",
        "mount",
        "umount",
        "iptables",
        "dd",
        "mkfs",
        "fdisk",
        "parted",
        "lvm",
        "lvcreate",
        "lvremove",
        "shutdown",
        "reboot",
        "poweroff",
        "halt",
        "init",
        "systemctl",
        "service",
        "journalctl",
        "useradd",
        "userdel",
        "usermod",
        "groupadd",
        "groupdel",
        "passwd",
        "chpasswd",
        "chsh",
        "chfn",
        "crontab",
        "at",
        "batch",
        "nc",
        "ncat",
        "netcat",
        "socat",
        "curl",
        "wget",  # Blocked in sandbox (network disabled anyway)
    }

    # Layer 3: Dangerous argument patterns
    DANGEROUS_PATTERNS = [
        r"rm\s+(-[a-zA-Z]*\s+)*-rf\s+/",  # rm -rf /
        r"rm\s+(-[a-zA-Z]*\s+)*-rf\s+/\*",  # rm -rf /*
        r"rm\s+(-[a-zA-Z]*\s+)*-rf\s+~/",  # rm -rf ~/
        r":\(\)\{",  # Fork bomb
        r"mkfs\.",  # mkfs.ext4 etc.
        r"dd\s+if=/dev/zero",  # dd wipe
        r"chmod\s+(-[a-zA-Z]*\s+)*777\s+/",  # chmod 777 /
        r"chown\s+(-[a-zA-Z]*\s+)*.*\s+/",  # chown /
        r"\|\s*(ba)?sh",  # Pipe to shell
        r"bash\s+-c",  # bash -c
        r"eval\s+",  # eval
        r"exec\s+",  # exec
        r"/dev/tcp/",  # Network via /dev/tcp
        r">\s*/dev/sd",  # Write to disk device
    ]

    def __init__(self) -> None:
        self._dangerous_regex = re.compile("|".join(self.DANGEROUS_PATTERNS))

    def validate_command(self, command: str) -> PolicyDecision:
        """Validate command against policy engine.

        Returns PolicyDecision with allowed=True/False and reason.
        """
        if not command or not command.strip():
            return PolicyDecision(allowed=False, reason="Command is empty")

        # Normalize command for analysis
        normalized = command.strip()

        # Layer 1: Try AST parsing (if bashlex available)
        ast_result = self._validate_ast(normalized)
        if not ast_result.allowed:
            return ast_result

        # Layer 2: Check command whitelist
        whitelist_result = self._validate_whitelist(normalized)
        if not whitelist_result.allowed:
            return whitelist_result

        # Layer 3: Check dangerous patterns
        pattern_result = self._validate_patterns(normalized)
        if not pattern_result.allowed:
            return pattern_result

        return PolicyDecision(allowed=True)

    def _validate_ast(self, command: str) -> PolicyDecision:
        """Layer 1: AST-level validation using bashlex."""
        try:
            import bashlex

            # Try to parse the command
            parts = bashlex.parse(command)

            # Check for dangerous AST nodes
            for part in parts:
                if self._check_ast_node(part):
                    return PolicyDecision(
                        allowed=False,
                        reason="Command contains dangerous AST patterns (subshell, eval, etc.)",
                    )

            return PolicyDecision(allowed=True)

        except ImportError:
            # bashlex not installed, skip AST validation
            logger.warning("bashlex not installed, skipping AST validation")
            return PolicyDecision(allowed=True)

        except Exception as e:
            # Parse failure = reject (safe default)
            logger.warning("bashlex parse failed, rejecting command", error=str(e))
            return PolicyDecision(allowed=False, reason=f"Command parsing failed: {e}")

    def _check_ast_node(self, node: Any) -> bool:
        """Recursively check AST node for dangerous patterns."""
        try:
            # Check node type
            if hasattr(node, "kind"):
                # Check for command substitution
                if node.kind == "commandsubstitution":
                    return True
                # Check for process substitution
                if node.kind == "processsubstitution":
                    return True

            # Recursively check children
            if hasattr(node, "parts"):
                for part in node.parts:
                    if self._check_ast_node(part):
                        return True

            return False

        except Exception:
            return False

    @staticmethod
    def _command_node_to_str(node: Any) -> str:
        return " ".join(
            part.word for part in node.parts if hasattr(part, "word") and part.word
        )

    def _split_command_segments(self, command: str) -> list[str]:
        """Split compound commands (&&, ||, ;) into segments for whitelist checks."""
        try:
            import bashlex

            segments: list[str] = []
            for parsed in bashlex.parse(command):
                if not hasattr(parsed, "parts"):
                    continue
                for part in parsed.parts:
                    if getattr(part, "kind", None) == "command":
                        segment = self._command_node_to_str(part)
                        if segment:
                            segments.append(segment)

            if segments:
                return segments
        except ImportError:
            pass
        except Exception:
            pass

        # Fallback: split on chain operators (simple heuristic)
        normalized = command.replace("\n", " ")
        parts = re.split(r"\s*(?:&&|\|\||;)\s*", normalized)
        return [part.strip() for part in parts if part.strip()]

    def _validate_cd_segment(self, segment: str) -> PolicyDecision:
        """Restrict cd targets to workspace-safe paths."""
        parts = segment.split()
        if len(parts) < 2:
            return PolicyDecision(allowed=True)

        target = parts[1]
        if ".." in target:
            return PolicyDecision(
                allowed=False,
                reason="cd path traversal (..) is not allowed",
            )
        from app.vfs.config import vfs_config

        allowed_roots = (
            vfs_config.workspace_prefix.rstrip("/"),
            vfs_config.uploads_prefix.rstrip("/"),
            vfs_config.outputs_prefix.rstrip("/"),
        )
        if target.startswith("/") and not target.startswith(allowed_roots):
            return PolicyDecision(
                allowed=False,
                reason=f"cd outside sandbox paths is not allowed: {target}",
            )
        return PolicyDecision(allowed=True)

    def _validate_whitelist_segment(self, segment: str) -> PolicyDecision:
        """Validate a single command segment against the whitelist."""
        parts = segment.split()
        if not parts:
            return PolicyDecision(allowed=False, reason="Empty command segment")

        base_cmd = parts[0].split("/")[-1]

        if base_cmd in self.BLOCKED_COMMANDS:
            return PolicyDecision(
                allowed=False,
                reason=f"Command '{base_cmd}' is blocked by security policy",
            )

        if base_cmd not in self.ALLOWED_COMMANDS:
            return PolicyDecision(
                allowed=False,
                reason=f"Command '{base_cmd}' is not in the allowed commands list",
            )

        if base_cmd == "cd":
            return self._validate_cd_segment(segment)

        return PolicyDecision(allowed=True)

    def _validate_whitelist(self, command: str) -> PolicyDecision:
        """Layer 2: Command whitelist validation for simple and chained commands."""
        segments = self._split_command_segments(command)
        if not segments:
            return PolicyDecision(allowed=False, reason="Empty command")

        for segment in segments:
            result = self._validate_whitelist_segment(segment)
            if not result.allowed:
                return result

        return PolicyDecision(allowed=True)

    def _validate_patterns(self, command: str) -> PolicyDecision:
        """Layer 3: Dangerous pattern validation."""
        # Check for dangerous patterns
        match = self._dangerous_regex.search(command)
        if match:
            return PolicyDecision(
                allowed=False,
                reason=f"Command contains dangerous pattern: {match.group()}",
            )

        # Check for path traversal in arguments
        if ".." in command:
            # Allow .. in git commands (git log, git diff, etc.)
            if not command.strip().startswith("git "):
                return PolicyDecision(
                    allowed=False, reason="Path traversal (..) not allowed"
                )

        return PolicyDecision(allowed=True)


# Global policy engine instance
policy_engine = CommandPolicyEngine()
