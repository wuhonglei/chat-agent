"""支持 SKILL.md 的 Skill 注册中心"""

import json
from pathlib import Path
from typing import Any

from .loader import DocumentedSkill, SkillLoader, SkillMetadata


class DocumentedSkillRegistry:
    """支持 SKILL.md 的注册中心"""

    def __init__(self, skills_dir: Path | None = None) -> None:
        self.skills_dir = skills_dir or Path(__file__).parent
        self._skills: dict[str, DocumentedSkill] = {}
        self._metadata_cache: dict[str, SkillMetadata] = {}
        self._skill_dirs: dict[str, Path] = {}  # skill_name -> skill_dir

    def discover(self, skip_errors: bool = True) -> list[str]:
        """发现并加载所有 Skill"""
        loaded: list[str] = []

        for item in self.skills_dir.iterdir():
            if not item.is_dir() or item.name.startswith("_"):
                continue

            skill_md = item / "SKILL.md"
            if not skill_md.exists():
                continue

            try:
                metadata, impl_class = SkillLoader.load_from_directory(item)
                skill = DocumentedSkill(metadata, impl_class)

                self._skills[metadata.name] = skill
                self._metadata_cache[metadata.name] = metadata
                self._skill_dirs[metadata.name] = item
                loaded.append(metadata.name)

                print(
                    f"[Registry] ✓ Loaded '{metadata.name}' v{metadata.version} "
                    f"by {metadata.author} [permissions: {metadata.permissions}]"
                )

            except Exception as e:
                if not skip_errors:
                    raise
                print(f"[Registry] ✗ Failed to load {item.name}: {e}")

        return loaded

    def get(self, name: str) -> DocumentedSkill | None:
        return self._skills.get(name)

    def list_skills(self, tag_filter: str | None = None) -> list[dict[str, Any]]:
        """列出 Skills，支持按标签过滤"""
        skills: list[dict[str, Any]] = []
        for name, skill in self._skills.items():
            meta = self._metadata_cache[name]
            if tag_filter and tag_filter not in (meta.tags or []):
                continue

            skills.append(
                {
                    "name": meta.name,
                    "description": meta.description,
                    "version": meta.version,
                    "author": meta.author,
                    "tags": meta.tags,
                    "permissions": meta.permissions,
                    "warnings": len(meta.warnings or []) > 0,
                    "timeout": meta.timeout,
                }
            )
        return skills

    def get_raw_skill_md(self, skill_name: str) -> str | None:
        """按需读取技能的完整 SKILL.md 原始内容"""
        skill_dir = self._skill_dirs.get(skill_name)
        if not skill_dir:
            return None
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            return None
        return skill_md.read_text(encoding="utf-8")

    def get_skill_full_documentation(self, skill_name: str) -> str | None:
        """返回技能完整文档：SKILL.md 原始内容 + 参数 Schema（供 LLM 按需阅读后决定调用）"""
        raw_md = self.get_raw_skill_md(skill_name)
        if not raw_md:
            return None

        meta = self._metadata_cache.get(skill_name)
        if meta and meta.parameters:
            raw_md += "\n\n## 参数 Schema\n\n```json\n"
            raw_md += json.dumps(meta.parameters, indent=2, ensure_ascii=False)
            raw_md += "\n```\n"
        return raw_md

    def generate_documentation_page(self, skill_name: str) -> str:
        """为 Skill 生成文档页面（Markdown）"""
        skill = self._skills.get(skill_name)
        if not skill:
            return f"Skill '{skill_name}' not found"

        meta = self._metadata_cache[skill_name]
        doc = f"""# {meta.name}

**版本**: {meta.version} | **作者**: {meta.author}

{meta.description}

## 权限要求
"""
        if meta.permissions:
            for perm in meta.permissions:
                doc += f"- `{perm}`\n"
        else:
            doc += "无特殊权限要求\n"

        if meta.warnings:
            doc += "\n## ⚠️ 警告\n"
            for warning in meta.warnings:
                doc += f"- {warning}\n"

        doc += """
## 参数 Schema

```json
"""
        doc += json.dumps(meta.parameters or {}, indent=2, ensure_ascii=False)
        doc += "\n```\n"
        return doc

    def to_tool_definitions(self) -> list[dict[str, Any]]:
        """将 Skills 转换为 LLM 工具定义格式（OpenAI tools）"""
        tools: list[dict[str, Any]] = []
        for name, skill in self._skills.items():
            meta = self._metadata_cache[name]
            tool = {
                "type": "function",
                "function": {
                    "name": meta.name,
                    "description": meta.description,
                    "parameters": {
                        "type": "object",
                        "properties": meta.parameters or {},
                        "required": list((meta.parameters or {}).keys()),
                    },
                },
            }
            tools.append(tool)
        return tools
