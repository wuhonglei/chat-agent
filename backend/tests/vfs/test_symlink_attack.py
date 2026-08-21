"""符号链接攻击防护演示

场景：用户在 workspace 里创建符号链接指向 /etc/passwd，
     尝试通过符号链接读取系统敏感文件。

核心原理：.resolve() 会跟随符号链接解析到真实路径，
         然后 startswith 检查发现真实路径不在 workspace 下 → 拒绝。
"""

import os
from pathlib import Path


def resolve_under_root(base_dir: Path, relative: str) -> Path:
    """模拟 resolver.py 的路径解析逻辑。

    和 app/vfs/resolver.py:39-41 同逻辑：
        target = (root / relative).resolve()
        if not str(target).startswith(str(root)):
            raise ValueError("path traversal detected")

    注意：实际 resolver.py 在入口处先 base_dir = base_dir.resolve()（第 132 行），
    所以 startswith 的两端都已经是 resolve 后的路径。
    """
    base_dir = base_dir.resolve()  # resolver.py:132
    target = (base_dir / relative).resolve()
    if not str(target).startswith(str(base_dir)):
        raise ValueError(
            f"path traversal detected: {target} escapes {base_dir}"
        )
    return target


def test_symlink_attack_blocked(tmp_path: Path):
    """符号链接指向 workspace 外的文件 → 被 .resolve() + startswith 拦截。"""
    workspace = tmp_path / "user-aaa" / "conversations" / "conv-111" / "workspace"
    workspace.mkdir(parents=True)

    # 攻击者在 workspace 里创建符号链接，指向 /etc/passwd
    symlink_path = workspace / "passwd"
    target_file = Path("/etc/passwd")

    if not target_file.exists():
        print("SKIP: /etc/passwd 不存在（非 Linux 环境）")
        return

    symlink_path.symlink_to(target_file)

    print("=" * 60)
    print("符号链接攻击演示")
    print("=" * 60)
    print()
    print(f"workspace 目录: {workspace}")
    print(f"符号链接:       {symlink_path}")
    print(f"链接目标:       {symlink_path.readlink()}")
    print()

    # 关键对比：拼接 vs resolve
    joined = workspace / "passwd"          # 简单拼接 — 看起来在 workspace 内
    resolved = (workspace / "passwd").resolve()  # resolve — 跟随链接到真实路径

    print("简单拼接 (不安全):")
    print(f"  workspace / 'passwd' = {joined}")
    print(f"  在 workspace 下? {str(joined).startswith(str(workspace))}  ← True，放行！危险！")
    print()

    print(".resolve() (安全):")
    print(f"  (workspace / 'passwd').resolve() = {resolved}")
    print(f"  在 workspace 下? {str(resolved).startswith(str(workspace))}  ← False，拒绝！")
    print()

    # 用 resolve_under_root 模拟实际拦截
    print("调用 resolve_under_root():")
    try:
        result = resolve_under_root(workspace, "passwd")
        print(f"  ✅ 允许访问: {result}")
    except ValueError as e:
        print(f"  ❌ 拒绝访问: {e}")

    # 清理
    symlink_path.unlink()


def test_normal_file_allowed(tmp_path: Path):
    """正常文件（非符号链接）→ 通过检查。"""
    workspace = tmp_path / "user-aaa" / "conversations" / "conv-111" / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    normal_file = workspace / "report.csv"
    normal_file.write_text("col1,col2\n1,2\n")

    print()
    print("=" * 60)
    print("正常文件访问演示")
    print("=" * 60)
    print()

    resolved = (workspace / "report.csv").resolve()
    print(f"文件:         {normal_file}")
    print(f"resolve 后:   {resolved}")
    print(f"在 workspace 下? {str(resolved).startswith(str(workspace))}")

    try:
        result = resolve_under_root(workspace, "report.csv")
        print(f"✅ 允许访问: {result}")
    except ValueError as e:
        print(f"❌ 拒绝访问: {e}")


def test_traversal_blocked(tmp_path: Path):
    """路径穿越 (../) → resolve 后不在 workspace 下 → 拒绝。"""
    workspace = tmp_path / "user-aaa" / "conversations" / "conv-111" / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)

    # 创建一个 "其他用户" 的文件
    other_user_dir = tmp_path / "user-bbb" / "secret.txt"
    other_user_dir.parent.mkdir(parents=True)
    other_user_dir.write_text("secret data")

    print()
    print("=" * 60)
    print("路径穿越演示")
    print("=" * 60)
    print()

    traversal_path = "../../user-bbb/secret.txt"
    joined = workspace / traversal_path
    resolved = joined.resolve()

    print(f"输入路径:     {traversal_path}")
    print(f"简单拼接:     {joined}")
    print(f"resolve 后:   {resolved}")
    print(f"在 workspace 下? {str(resolved).startswith(str(workspace))}")
    print()

    try:
        result = resolve_under_root(workspace, traversal_path)
        print(f"✅ 允许访问: {result}")
    except ValueError as e:
        print(f"❌ 拒绝访问: {e}")


if __name__ == "__main__":
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        test_symlink_attack_blocked(tmp_path)
        test_normal_file_allowed(tmp_path)
        test_traversal_blocked(tmp_path)
