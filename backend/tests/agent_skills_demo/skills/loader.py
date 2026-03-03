"""从 SKILL.md 目录加载 Skill"""

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .base import BaseSkill, SkillResult


@dataclass
class SkillMetadata:
    """Skill 元数据（从 SKILL.md frontmatter 解析）"""

    name: str
    description: str
    version: str = "1.0.0"
    author: str = "Unknown"
    tags: list[str] | None = None
    permissions: list[str] | None = None
    warnings: list[str] | None = None
    parameters: dict[str, Any] | None = None
    timeout: int | None = None

    def __post_init__(self) -> None:
        if self.tags is None:
            self.tags = []
        if self.permissions is None:
            self.permissions = []
        if self.warnings is None:
            self.warnings = []
        if self.parameters is None:
            self.parameters = {}


@dataclass
class DocumentedSkill:
    """带文档的 Skill"""

    metadata: SkillMetadata
    impl: type[BaseSkill]

    async def execute(
        self,
        params: dict[str, Any],
        context: Any = None,
    ) -> SkillResult:

        instance = self.impl()
        return await instance.execute(params, context)


def _parse_frontmatter(content: str) -> tuple[dict[str, Any], str]:
    """解析 YAML frontmatter，返回 (frontmatter_dict, body)"""
    if not content.strip().startswith("---"):
        return {}, content

    match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", content, re.DOTALL)
    if not match:
        return {}, content

    fm_raw, body = match.group(1), match.group(2)

    # 简单 YAML 解析（支持 key: value 和 key: [a,b,c]）
    fm: dict[str, Any] = {}
    for line in fm_raw.split("\n"):
        line = line.strip()
        if not line:
            continue
        if ":" not in line:
            continue
        key, val = line.split(":", 1)
        key = key.strip().lower()
        val = val.strip()

        if val.startswith("[") and val.endswith("]"):
            # 列表
            inner = val[1:-1].strip()
            fm[key] = (
                [x.strip().strip("'\"").strip() for x in inner.split(",")]
                if inner
                else []
            )
        elif val.lower() in ("true", "false"):
            fm[key] = val.lower() == "true"
        elif val.isdigit():
            fm[key] = int(val)
        else:
            fm[key] = val.strip("'\"")

    return fm, body


def _fm_get(obj: dict[str, Any], key: str, default: Any = None) -> Any:
    v = obj.get(key)
    return v if v is not None else default


class SkillLoader:
    """从目录加载 Skill"""

    @staticmethod
    def load_from_directory(skill_dir: Path) -> tuple[SkillMetadata, type[BaseSkill]]:
        """
        从目录加载 Skill。
        目录需包含 SKILL.md 和 scripts/impl.py（符合 Cursor 官方目录规范）。
        返回 (SkillMetadata, impl_class)
        """
        skill_md = skill_dir / "SKILL.md"
        impl_file = skill_dir / "scripts" / "impl.py"

        if not skill_md.exists():
            raise FileNotFoundError(f"SKILL.md not found in {skill_dir}")

        # 解析 SKILL.md
        content = skill_md.read_text(encoding="utf-8")
        fm, _ = _parse_frontmatter(content)

        # 解析 parameters（可能是 JSON 字符串）
        params = _fm_get(fm, "parameters", {})
        if isinstance(params, str):
            try:
                params = json.loads(params)
            except json.JSONDecodeError:
                params = {}

        # 支持 skill.config.json 覆盖框架元数据（Cursor 标准下 SKILL.md 仅保留 name/description）
        config_file = skill_dir / "skill.config.json"
        config: dict[str, Any] = {}
        if config_file.exists():
            try:
                config = json.loads(config_file.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                pass

        def _get(key: str, default: Any = None) -> Any:
            return config[key] if key in config else _fm_get(fm, key, default)

        params = _get("parameters", params)
        if isinstance(params, str):
            try:
                params = json.loads(params)
            except json.JSONDecodeError:
                params = params if isinstance(params, dict) else {}

        metadata = SkillMetadata(
            name=_fm_get(fm, "name", skill_dir.name),
            description=_fm_get(fm, "description", ""),
            version=_get("version", "1.0.0"),
            author=_get("author", "Unknown"),
            tags=_get("tags", []),
            permissions=_get("permissions", []),
            warnings=_get("warnings", []),
            parameters=params,
            timeout=_get("timeout"),
        )

        if not impl_file.exists():
            raise FileNotFoundError(f"scripts/impl.py not found in {skill_dir}")

        # 动态导入 impl（通过包路径，确保 ..base 等相对导入可用）
        import importlib
        import importlib.util
        import sys

        # 确保 skills 包所在父目录在 sys.path 中
        skills_parent = skill_dir.parent.parent
        if str(skills_parent) not in sys.path:
            sys.path.insert(0, str(skills_parent))

        pkg_name = skill_dir.parent.name
        mod_name = f"{pkg_name}.{skill_dir.name}.scripts.impl"
        try:
            mod = importlib.import_module(mod_name)
        except ModuleNotFoundError:
            spec = importlib.util.spec_from_file_location(
                f"skill_impl_{skill_dir.name}", impl_file
            )
            if spec is None or spec.loader is None:
                raise ImportError(f"Cannot load impl from {impl_file}")
            mod = importlib.util.module_from_spec(spec)
            # 设置 __package__ 以便相对导入
            mod.__package__ = f"{pkg_name}.{skill_dir.name}.scripts"
            spec.loader.exec_module(mod)

        impl_class = getattr(mod, "SkillImpl", None)
        if impl_class is None:
            impl_class = getattr(mod, "skill_impl", None)
        if impl_class is None:
            impl_class = getattr(mod, skill_dir.name.replace("-", "_").title(), None)
        if impl_class is None:
            # 找第一个继承 BaseSkill 的类
            for attr in dir(mod):
                val = getattr(mod, attr)
                if (
                    isinstance(val, type)
                    and issubclass(val, BaseSkill)
                    and val is not BaseSkill
                ):
                    impl_class = val
                    break
        if impl_class is None:
            raise ValueError(
                "scripts/impl.py must export SkillImpl, skill_impl, or a class inheriting BaseSkill"
            )

        return metadata, impl_class
