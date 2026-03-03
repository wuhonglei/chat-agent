# Agent Skills Demo - LLM 集成

基于 SKILL.md 的 Skill 框架，支持将 Skills 作为工具暴露给 LLM，实现自然语言驱动的工具调用。

## 目录结构

```
skills/
├── base.py           # BaseSkill、SkillContext、SkillResult
├── loader.py         # 从 SKILL.md 解析并加载 Skill
├── registry.py       # DocumentedSkillRegistry 注册中心
├── calculator/       # 计算器 Skill
│   ├── SKILL.md
│   ├── impl.py
│   └── test_skill.py
├── weather/          # 天气查询 Skill（模拟）
│   ├── SKILL.md
│   ├── impl.py
│   └── schemas/response.json
└── code_executor/    # 代码执行 Skill（RestrictedPython 沙箱）
    ├── SKILL.md
    └── impl.py
```

## 运行方式

```bash
# 从 backend 根目录运行
uv run python -m tests.agent_skills_demo.llm_integration

# 或从 agent_skills_demo 目录
cd tests/agent_skills_demo
uv run python llm_integration.py
```

## LLM 调用

在 `tests/agent_skills_demo/.env` 中配置：

```
OPENAI_API_KEY=your-key
OPENAI_API_BASE=https://api.deepseek.com
```

然后运行：

```bash
uv run python -m tests.agent_skills_demo.llm_integration
```

## 运行单元测试

```bash
uv run pytest tests/agent_skills_demo/skills/calculator/test_skill.py -v
```

## 新增 Skill

1. 在 `skills/` 下创建子目录，如 `my_skill/`
2. 添加 `SKILL.md`（含 frontmatter：name、description、parameters 等）
3. 添加 `impl.py`，导出 `SkillImpl(BaseSkill)` 类
4. 运行 `registry.discover()` 自动发现并加载
