"""Virtual path handling for local sandbox shell execution."""

from __future__ import annotations

import re
import shlex
from pathlib import Path

from app.vfs.config import SKILLS_ROOT, vfs_config
from app.vfs.mapper import MappingContext, VirtualPathMapper
from app.vfs.paths import VIRTUAL_PATH_PREFIX, get_paths

PathMappings = dict[str, str]

_ABSOLUTE_PATH_PATTERN = re.compile(r"(?<![:\w])(?<!:/)/(?:[^\s\"'`;&|<>()]+)")
_FILE_URL_PATTERN = re.compile(r"\bfile://\S+", re.IGNORECASE)
_URL_WITH_SCHEME_PATTERN = re.compile(r"^[a-z][a-z0-9+.-]*://", re.IGNORECASE)
_URL_IN_COMMAND_PATTERN = re.compile(
    r"\b[a-z][a-z0-9+.-]*://[^\s\"'`;&|<>()]+", re.IGNORECASE
)
_DOTDOT_PATH_SEGMENT_PATTERN = re.compile(r"(?:^|[/\\=])\.\.(?:$|[/\\])")
_VIRTUAL_PATH_SUFFIX = r"(/[^\s\"';&|<>()]*)?"
_SYSTEM_PATH_PREFIXES = (
    "/bin/",
    "/usr/bin/",
    "/usr/sbin/",
    "/sbin/",
    "/opt/homebrew/bin/",
    "/dev/",
)
_SHELL_COMMAND_SEPARATORS = frozenset({";", "&&", "||", "|", "|&", "&", "(", ")"})
_SHELL_REDIRECTION_OPERATORS = frozenset(
    {
        "<",
        ">",
        "<<",
        ">>",
        "<<<",
        "<>",
        ">&",
        "<&",
        "&>",
        "&>>",
        ">|",
    }
)
_LOCAL_BASH_CWD_COMMANDS = frozenset({"cd", "pushd"})
_LOCAL_BASH_COMMAND_WRAPPERS = frozenset({"command", "builtin"})
_LOCAL_BASH_COMMAND_PREFIX_KEYWORDS = frozenset(
    {
        "!",
        "{",
        "case",
        "do",
        "elif",
        "else",
        "for",
        "if",
        "select",
        "then",
        "time",
        "until",
        "while",
    }
)
_LOCAL_BASH_COMMAND_END_KEYWORDS = frozenset({"}", "done", "esac", "fi"})
_LOCAL_BASH_ROOT_PATH_COMMANDS = frozenset(
    {
        "awk",
        "cat",
        "cp",
        "du",
        "find",
        "grep",
        "head",
        "less",
        "ln",
        "ls",
        "more",
        "mv",
        "rm",
        "sed",
        "tail",
        "tar",
    }
)


class LocalCommandPathError(PermissionError):
    """Raised when a local shell command references disallowed paths."""


def build_path_mappings(user_id: str, conversation_id: str) -> PathMappings:
    """Build virtual-to-physical path mappings (longest-prefix wins when sorted)."""
    paths = get_paths()
    uid = paths.validate_user_id(user_id)
    cid = paths.validate_conversation_id(conversation_id)

    workspace = str(paths.sandbox_work_dir(uid, cid).resolve())
    uploads = str(paths.sandbox_uploads_dir(uid, cid).resolve())
    outputs = str(paths.sandbox_outputs_dir(uid, cid).resolve())
    skills_custom = str(paths.user_skills_dir(uid).resolve())
    skills = str(SKILLS_ROOT.resolve())

    mappings: PathMappings = {
        vfs_config.workspace_prefix.rstrip("/"): workspace,
        vfs_config.uploads_prefix.rstrip("/"): uploads,
        vfs_config.outputs_prefix.rstrip("/"): outputs,
        vfs_config.skills_custom_prefix.rstrip("/"): skills_custom,
        vfs_config.skills_prefix.rstrip("/"): skills,
    }

    conversation_dir = str(paths.conversation_dir(uid, cid).resolve())
    if all(
        str(Path(p).parent) == conversation_dir for p in (workspace, uploads, outputs)
    ):
        mappings[VIRTUAL_PATH_PREFIX] = conversation_dir

    return mappings


def _path_separator_for_style(base: str) -> str:
    return "\\" if "\\" in base else "/"


def _join_path_preserving_style(base: str, rest: str) -> str:
    if not rest:
        return base
    sep = _path_separator_for_style(base)
    trimmed_base = base.rstrip("/\\")
    return f"{trimmed_base}{sep}{rest.replace('/', sep)}"


def replace_virtual_path(path: str, mappings: PathMappings) -> str:
    """Replace a single virtual path token with its physical path."""
    if not mappings:
        return path

    for virtual_base, actual_base in sorted(
        mappings.items(), key=lambda item: len(item[0]), reverse=True
    ):
        if path == virtual_base:
            return actual_base
        prefix = f"{virtual_base}/"
        if path.startswith(prefix):
            rest = path[len(virtual_base) :].lstrip("/")
            result = _join_path_preserving_style(actual_base, rest)
            if path.endswith("/") and not result.endswith(("/", "\\")):
                result += _path_separator_for_style(actual_base)
            return result

    return path


def replace_virtual_paths_in_command(command: str, mappings: PathMappings) -> str:
    """Replace all known virtual path prefixes in a shell command string."""
    result = command

    skills_custom = vfs_config.skills_custom_prefix.rstrip("/")
    if skills_custom in mappings and skills_custom in result:
        pattern = re.compile(rf"{re.escape(skills_custom)}{_VIRTUAL_PATH_SUFFIX}")
        result = pattern.sub(
            lambda m: replace_virtual_path(m.group(0), mappings), result
        )

    skills_prefix = vfs_config.skills_prefix.rstrip("/")
    if skills_prefix in mappings and skills_prefix in result:
        pattern = re.compile(rf"{re.escape(skills_prefix)}{_VIRTUAL_PATH_SUFFIX}")
        result = pattern.sub(
            lambda m: replace_virtual_path(m.group(0), mappings), result
        )

    if VIRTUAL_PATH_PREFIX in result:
        pattern = re.compile(rf"{re.escape(VIRTUAL_PATH_PREFIX)}{_VIRTUAL_PATH_SUFFIX}")
        result = pattern.sub(
            lambda m: replace_virtual_path(m.group(0), mappings), result
        )

    return result


def _reject_path_traversal(path: str) -> None:
    normalised = path.replace("\\", "/")
    for segment in normalised.split("/"):
        if segment == "..":
            raise LocalCommandPathError("Access denied: path traversal detected")


def _is_allowed_absolute_path(path: str, *, allow_system_paths: bool = True) -> bool:
    if path == VIRTUAL_PATH_PREFIX or path.startswith(f"{VIRTUAL_PATH_PREFIX}/"):
        _reject_path_traversal(path)
        return True

    skills_prefix = vfs_config.skills_prefix.rstrip("/")
    if path == skills_prefix or path.startswith(f"{skills_prefix}/"):
        _reject_path_traversal(path)
        return True

    if allow_system_paths and any(
        path == prefix.rstrip("/") or path.startswith(prefix)
        for prefix in _SYSTEM_PATH_PREFIXES
    ):
        return True

    return False


def _is_non_file_url_token(token: str) -> bool:
    values = [token]
    if "=" in token:
        values.append(token.split("=", 1)[1])

    for value in values:
        match = _URL_WITH_SCHEME_PATTERN.match(value)
        if match and not value.lower().startswith("file://"):
            return True
    return False


def _non_file_url_spans(command: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    for match in _URL_IN_COMMAND_PATTERN.finditer(command):
        if not match.group().lower().startswith("file://"):
            spans.append(match.span())
    return spans


def _is_in_spans(position: int, spans: list[tuple[int, int]]) -> bool:
    return any(start <= position < end for start, end in spans)


def _has_dotdot_path_segment(token: str) -> bool:
    if _is_non_file_url_token(token):
        return False
    return bool(_DOTDOT_PATH_SEGMENT_PATTERN.search(token))


def _split_shell_tokens(command: str) -> list[str]:
    try:
        normalized = (
            command.replace("\r\n", "\n").replace("\r", "\n").replace("\n", " ; ")
        )
        lexer = shlex.shlex(normalized, posix=True, punctuation_chars=True)
        lexer.whitespace_split = True
        lexer.commenters = ""
        return list(lexer)
    except ValueError:
        return command.split()


def _is_shell_command_separator(token: str) -> bool:
    return token in _SHELL_COMMAND_SEPARATORS


def _is_shell_redirection_operator(token: str) -> bool:
    return token in _SHELL_REDIRECTION_OPERATORS


def _is_shell_assignment(token: str) -> bool:
    name, separator, _ = token.partition("=")
    if not separator or not name:
        return False
    return bool(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name))


def _next_cd_target(tokens: list[str], start_index: int) -> tuple[str | None, int]:
    index = start_index
    while index < len(tokens):
        token = tokens[index]
        if _is_shell_command_separator(token):
            return None, index
        if _is_shell_redirection_operator(token):
            index += 2
            continue
        if token == "--":
            index += 1
            continue
        if token in {"-L", "-P", "-e", "-@"}:
            index += 1
            continue
        if token.startswith("-") and token != "-":
            index += 1
            continue
        return token, index + 1
    return None, index


def _validate_cwd_target(command_name: str, target: str | None) -> None:
    if target is None or target == "-":
        raise LocalCommandPathError(
            f"Unsafe working directory change in command: {command_name}. "
            f"Use paths under {VIRTUAL_PATH_PREFIX}"
        )
    if target.startswith(("$", "`")):
        raise LocalCommandPathError(
            f"Unsafe working directory change in command: {command_name} {target}. "
            f"Use paths under {VIRTUAL_PATH_PREFIX}"
        )
    if target.startswith("~"):
        raise LocalCommandPathError(
            f"Unsafe working directory change in command: {command_name} {target}. "
            f"Use paths under {VIRTUAL_PATH_PREFIX}"
        )
    if target.startswith("/"):
        _reject_path_traversal(target)
        if not _is_allowed_absolute_path(target, allow_system_paths=False):
            raise LocalCommandPathError(
                f"Unsafe working directory change in command: {command_name} {target}. "
                f"Use paths under {VIRTUAL_PATH_PREFIX}"
            )


def _validate_root_path_args(
    command_name: str, tokens: list[str], start_index: int
) -> None:
    if command_name not in _LOCAL_BASH_ROOT_PATH_COMMANDS:
        return

    index = start_index
    while index < len(tokens):
        token = tokens[index]
        if _is_shell_command_separator(token):
            return
        if _is_shell_redirection_operator(token):
            index += 2
            continue
        if token == "/" and not _is_non_file_url_token(token):
            raise LocalCommandPathError(
                f"Unsafe absolute paths in command: /. "
                f"Use paths under {VIRTUAL_PATH_PREFIX}"
            )
        index += 1


def _validate_shell_tokens(command: str) -> None:
    """Conservatively reject path escapes missed by absolute-path scanning."""
    if re.search(r"\$\([^)]*\b(?:cd|pushd)\b", command):
        raise LocalCommandPathError(
            f"Unsafe working directory change in command substitution. "
            f"Use paths under {VIRTUAL_PATH_PREFIX}"
        )

    tokens = _split_shell_tokens(command)

    for token in tokens:
        if _is_shell_command_separator(token) or _is_shell_redirection_operator(token):
            continue
        if _has_dotdot_path_segment(token):
            raise LocalCommandPathError("Access denied: path traversal detected")

    at_command_start = True
    index = 0
    while index < len(tokens):
        token = tokens[index]

        if _is_shell_command_separator(token):
            at_command_start = True
            index += 1
            continue

        if _is_shell_redirection_operator(token):
            index += 1
            continue

        if at_command_start and _is_shell_assignment(token):
            index += 1
            continue

        command_name = token.rsplit("/", 1)[-1]
        if at_command_start and command_name in (
            _LOCAL_BASH_COMMAND_PREFIX_KEYWORDS | _LOCAL_BASH_COMMAND_END_KEYWORDS
        ):
            index += 1
            continue

        if not at_command_start:
            index += 1
            continue

        at_command_start = False
        if command_name in _LOCAL_BASH_COMMAND_WRAPPERS and index + 1 < len(tokens):
            wrapped_name = tokens[index + 1].rsplit("/", 1)[-1]
            if wrapped_name in _LOCAL_BASH_CWD_COMMANDS:
                target, next_index = _next_cd_target(tokens, index + 2)
                _validate_cwd_target(wrapped_name, target)
                index = next_index
                continue
            _validate_root_path_args(wrapped_name, tokens, index + 2)

        if command_name not in _LOCAL_BASH_CWD_COMMANDS:
            _validate_root_path_args(command_name, tokens, index + 1)
            index += 1
            continue

        target, next_index = _next_cd_target(tokens, index + 1)
        _validate_cwd_target(command_name, target)
        index = next_index


def validate_local_command_paths(command: str, mappings: PathMappings) -> None:
    """Validate absolute paths in a local-sandbox command (before virtual→physical replace)."""
    _ = mappings
    file_url_match = _FILE_URL_PATTERN.search(command)
    if file_url_match:
        raise LocalCommandPathError(
            f"Unsafe file:// URL in command: {file_url_match.group()}. "
            f"Use paths under {VIRTUAL_PATH_PREFIX}"
        )

    _validate_shell_tokens(command)

    unsafe_paths: list[str] = []
    url_spans = _non_file_url_spans(command)
    for match in _ABSOLUTE_PATH_PATTERN.finditer(command):
        if _is_in_spans(match.start(), url_spans):
            continue
        absolute_path = match.group()
        if absolute_path == "/":
            unsafe_paths.append(absolute_path)
            continue
        try:
            if _is_allowed_absolute_path(absolute_path):
                continue
        except LocalCommandPathError:
            raise
        unsafe_paths.append(absolute_path)

    if unsafe_paths:
        unsafe = ", ".join(sorted(dict.fromkeys(unsafe_paths)))
        raise LocalCommandPathError(
            f"Unsafe absolute paths in command: {unsafe}. "
            f"Use paths under {VIRTUAL_PATH_PREFIX}"
        )


def mask_paths_in_output(text: str, user_id: str, conversation_id: str) -> str:
    """Replace physical paths in shell output with virtual paths."""
    ctx = MappingContext(user_id=user_id, conversation_id=conversation_id)
    return VirtualPathMapper().mask_paths_in_text(text, ctx)
