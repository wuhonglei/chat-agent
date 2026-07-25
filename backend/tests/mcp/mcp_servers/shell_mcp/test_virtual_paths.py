"""Tests for local sandbox virtual path handling in shell MCP."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.mcp.mcp_servers.shell_mcp.virtual_paths import (
    LocalCommandPathError,
    build_path_mappings,
    mask_paths_in_output,
    replace_virtual_path,
    replace_virtual_paths_in_command,
    validate_local_command_paths,
)
from app.vfs.config import vfs_config
from app.vfs.paths import VIRTUAL_PATH_PREFIX, Paths


@pytest.fixture
def path_layout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[Paths, str, str]:
    """Create user/conversation dirs and return (Paths, user_id, conversation_id)."""
    paths = Paths(base_dir=tmp_path / "user_data")
    user_id = "user-1"
    conversation_id = "conv-1"
    paths.ensure_conversation_dirs(user_id, conversation_id)
    paths.ensure_user_skills_dir(user_id)
    from app.vfs import paths as paths_module

    monkeypatch.setattr(paths_module, "_paths", paths)
    return paths, user_id, conversation_id


@pytest.fixture
def mappings(path_layout: tuple[Paths, str, str]) -> dict[str, str]:
    _paths, user_id, conversation_id = path_layout
    return build_path_mappings(user_id, conversation_id)


def test_build_path_mappings_includes_user_data_and_skills(
    path_layout: tuple[Paths, str, str],
) -> None:
    paths, user_id, conversation_id = path_layout
    result = build_path_mappings(user_id, conversation_id)

    workspace = paths.sandbox_work_dir(user_id, conversation_id).resolve()
    assert result[vfs_config.workspace_prefix.rstrip("/")] == str(workspace)
    assert VIRTUAL_PATH_PREFIX in result
    assert result[VIRTUAL_PATH_PREFIX] == str(
        paths.conversation_dir(user_id, conversation_id).resolve()
    )


def test_replace_virtual_path_maps_workspace_and_root(
    mappings: dict[str, str],
) -> None:
    workspace_virtual = vfs_config.workspace_prefix.rstrip("/")
    assert replace_virtual_path(f"{workspace_virtual}/a.txt", mappings).endswith(
        "workspace/a.txt"
    )
    assert Path(replace_virtual_path(VIRTUAL_PATH_PREFIX, mappings)).name == "conv-1"


def test_replace_virtual_path_preserves_trailing_slash(
    mappings: dict[str, str],
) -> None:
    workspace_virtual = vfs_config.workspace_prefix.rstrip("/")
    result = replace_virtual_path(f"{workspace_virtual}/", mappings)
    assert result.endswith("/")


def test_replace_virtual_paths_in_command(mappings: dict[str, str]) -> None:
    cmd = f"cat {vfs_config.uploads_prefix}report.pdf"
    result = replace_virtual_paths_in_command(cmd, mappings)
    assert vfs_config.uploads_prefix not in result
    assert "report.pdf" in result


def test_replace_virtual_paths_skills_public(mappings: dict[str, str]) -> None:
    cmd = "python /mnt/skills/public/foo/scripts/run.py"
    result = replace_virtual_paths_in_command(cmd, mappings)
    assert "/mnt/skills/" not in result
    assert "skills" in result.lower()


def test_validate_rejects_host_absolute_path(mappings: dict[str, str]) -> None:
    with pytest.raises(LocalCommandPathError, match="Unsafe absolute paths"):
        validate_local_command_paths("cat /Users/me/secret.txt", mappings)


def test_validate_rejects_path_traversal(mappings: dict[str, str]) -> None:
    with pytest.raises(LocalCommandPathError, match="path traversal"):
        validate_local_command_paths(
            f"cat {vfs_config.workspace_prefix}../../etc/passwd",
            mappings,
        )


def test_validate_allows_virtual_workspace_path(mappings: dict[str, str]) -> None:
    validate_local_command_paths(
        f"cat {vfs_config.workspace_prefix}hello.txt",
        mappings,
    )


def test_validate_allows_system_bin_path(mappings: dict[str, str]) -> None:
    validate_local_command_paths("ls /usr/bin | head", mappings)


def test_validate_rejects_cat_root(mappings: dict[str, str]) -> None:
    with pytest.raises(LocalCommandPathError, match="Unsafe absolute paths"):
        validate_local_command_paths("cat /", mappings)


def test_validate_rejects_command_cd_outside_virtual(
    mappings: dict[str, str],
) -> None:
    with pytest.raises(LocalCommandPathError, match="Unsafe working directory"):
        validate_local_command_paths("command cd /etc", mappings)


def test_validate_allows_cd_skills(mappings: dict[str, str]) -> None:
    validate_local_command_paths(
        f"cd {vfs_config.skills_public_prefix.rstrip('/')}",
        mappings,
    )


def test_validate_allows_js_import_alias_in_command(
    mappings: dict[str, str],
) -> None:
    """JS/TS aliases like "@/*" must not be treated as absolute paths."""
    validate_local_command_paths(
        f'cd {vfs_config.workspace_prefix.rstrip("/")} && '
        'npx create-next-app@latest personal-blog --typescript --tailwind '
        '--app --no-src-dir --import-alias "@/*" --yes',
        mappings,
    )


def test_validate_allows_double_slash_line_comments_in_heredoc(
    mappings: dict[str, str],
) -> None:
    """TS/JS // comments inside heredoc must not be treated as absolute paths."""
    workspace = vfs_config.workspace_prefix.rstrip("/")
    command = f"""cat > {workspace}/types/dashboard.ts << 'EOF'
// type definitions
export interface MetricCard {{
  change: number; // percent change
  trend: 'up' | 'down' | 'neutral';
}}
EOF"""
    validate_local_command_paths(command, mappings)


def test_validate_allows_jsx_closing_tags_in_heredoc(
    mappings: dict[str, str],
) -> None:
    """JSX closing tags like </Card> must not be treated as absolute paths."""
    workspace = vfs_config.workspace_prefix.rstrip("/")
    command = f"""cat > {workspace}/components/MetricCards.tsx << 'EOF'
import {{ Card, CardContent }} from '@/components/ui/card';

export function MetricCards() {{
  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
      <Card>
        <CardContent className="p-6">
          <p className="text-sm">title</p>
          <span className="text-green-500">1%</span>
        </CardContent>
      </Card>
    </div>
  );
}}
EOF"""
    validate_local_command_paths(command, mappings)


def test_validate_allows_js_template_date_slash_in_python_c(
    mappings: dict[str, str],
) -> None:
    """JS template `${month}/${day}` inside python -c must not look like a path."""
    workspace = vfs_config.workspace_prefix.rstrip("/")
    command = (
        f'cd {workspace}/components && python3 -c "'
        "content = '''"
        "return \\`\\${date.getMonth() + 1}/\\${date.getDate()}\\`;"
        "'''\n"
        "open('TrendChart.tsx','w').write(content)"
        '"'
    )
    validate_local_command_paths(command, mappings)


def test_validate_rejects_quoted_host_absolute_path(
    mappings: dict[str, str],
) -> None:
    """Quoted path args must still be validated (e.g. cat \"/etc/passwd\")."""
    with pytest.raises(LocalCommandPathError, match="Unsafe absolute paths"):
        validate_local_command_paths('cat "/etc/passwd"', mappings)
    with pytest.raises(LocalCommandPathError, match="Unsafe absolute paths"):
        validate_local_command_paths("cat '/Users/me/secret.txt'", mappings)


def test_validate_allows_quoted_virtual_path(mappings: dict[str, str]) -> None:
    workspace = vfs_config.workspace_prefix.rstrip("/")
    validate_local_command_paths(f'cat "{workspace}/hello.txt"', mappings)


def test_validate_skips_multiline_quoted_script_body(
    mappings: dict[str, str],
) -> None:
    """Multi-line quotes (inline scripts) are not scanned for incidental /tags."""
    workspace = vfs_config.workspace_prefix.rstrip("/")
    command = (
        f"python3 -c \"\n"
        f"content = '<div><Card></Card></div>'\n"
        f"open('{workspace}/App.tsx', 'w').write(content)\n"
        f"\""
    )
    validate_local_command_paths(command, mappings)


def test_mask_paths_in_output(path_layout: tuple[Paths, str, str]) -> None:
    paths, user_id, conversation_id = path_layout
    workspace = str(paths.sandbox_work_dir(user_id, conversation_id).resolve())
    output = f"Created: {workspace}/result.txt"
    masked = mask_paths_in_output(output, user_id, conversation_id)

    assert workspace not in masked
    assert f"{vfs_config.workspace_prefix}result.txt" in masked
