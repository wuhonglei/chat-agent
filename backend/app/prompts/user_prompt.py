"""用户消息提示词模板模块"""

from jinja2 import Template

# 共用的用户查询 XML（变量名统一为 user_message_text；可选 kb_context_blocks）
_USER_MESSAGE_QUERY_SNIPPET = """
<user_message>
  <query>{{ user_message_text|e }}</query>
  {%- if kb_context_blocks %}
  <attachment_context>
  {%- for attachment in kb_context_blocks %}
    <attachment index="{{ loop.index }}">
      <name>{{ attachment.name|e }}</name>
      {%- if attachment.created_at %}
      <created_at>{{ attachment.created_at|e }}</created_at>
      {%- endif %}
      <content>{{ attachment.content|e }}</content>
    </attachment>
  {%- endfor %}
  </attachment_context>
  {%- endif %}
  {%- if attachment_uploads %}
  <attachment_uploads note="以下为本会话已上传文件, markdown 为原始文件派生的可读 Markdown 文件">
  {%- for f in attachment_uploads %}
    <file index="{{ loop.index }}">
      <name>{{ f.name|e }}</name>
      <type>{{ f.type|e }}</type>
      <virtual_path>{{ f.virtual_path|e }}</virtual_path>
      <file_size>{{ f.human_size }}</file_size>
      {%- if f.token_size is not none %}
      <token_size>{{ f.token_size }}</token_size>
      {%- endif %}
      {%- if f.lines_count is not none %}
      <lines_count>{{ f.lines_count }}</lines_count>
      {%- endif %}
      <uploaded_this_turn>{{ 'true' if f.is_current_turn else 'false' }}</uploaded_this_turn>
      {%- if f.markdown %}
      <markdown>
        <name>{{ f.markdown.name|e }}</name>
        <virtual_path>{{ f.markdown.virtual_path|e }}</virtual_path>
        <file_size>{{ f.markdown.human_size }}</file_size>
        {%- if f.markdown.token_size is not none %}
        <token_size>{{ f.markdown.token_size }}</token_size>
        {%- endif %}
        {%- if f.markdown.lines_count is not none %}
        <lines_count>{{ f.markdown.lines_count }}</lines_count>
        {%- endif %}
      </markdown>
      {%- endif %}
    </file>
  {%- endfor %}
  </attachment_uploads>
  {%- endif %}
</user_message>
""".strip()

user_message_for_default_template: Template = Template(_USER_MESSAGE_QUERY_SNIPPET)

# ============= 工具调用用户消息提示词 =============
user_message_for_tool_call_template: Template = Template(
    _USER_MESSAGE_QUERY_SNIPPET
    + "\n\n"
    + """
<tool_call_context>
{%- if window_out_summary %}
  <window_out_summary>{{ window_out_summary|e }}</window_out_summary>
{%- endif %}
  {%- if user_memories %}
  <user_memories>
  {%- for memory in user_memories %}
    <memory_item>
      <memory>{{ memory.memory|e }}</memory>
      {%- if memory.created_at %}
      <created_at>{{ memory.created_at|e }}</created_at>
      {%- endif %}
      <relevance>{{ memory.relevance|e }}</relevance>
    </memory_item>
  {%- endfor %}
  </user_memories>
  {%- endif %}
  <current_datetime>{{ current_datetime|e }}</current_datetime>
</tool_call_context>
""".strip()
)

user_message_for_reach_tool_call_limit_template: Template = Template(
    _USER_MESSAGE_QUERY_SNIPPET
    + "\n\n"
    + """
<tool_call_limit_notice>
  【系统说明】工具调用已达上限，请仅根据已有对话与工具结果直接作答；信息不足时请说明并给出力所能及的建议，勿再提议调用工具。
</tool_call_limit_notice>
""".strip()
)

user_message_for_no_tool_call_template: Template = Template(
    _USER_MESSAGE_QUERY_SNIPPET
    + "\n\n"
    + """
<no_tool_call_notice>
  【系统说明】没有可用的工具，请直接给出最终回答。
</no_tool_call_notice>
""".strip()
)

gentle_tips_in_web_search_template: Template = Template(
    """
已调用 tavily_web_search，返回内容已包含相关片段，无需再调 tavily_web_pages_extract（除非需要完整网页内容）。
""".strip()
)

tool_call_sufficient_info_template: Template = Template(
    """
⚠️ 搜索结果可能已足够回答问题。请检查已调用工具及其结果，足够则直接给出最终回答，停止调用更多工具。
""".strip()
)

# ============= 上下文摘要相关提示词 =============
# 结构借鉴：hermes Active Task 原话 / opencode 空章节占位与增量合并 /
# claude-code Errors + Next Step。输出供后续对话直接续用。
_WINDOW_OUT_SUMMARY_SECTIONS = """
## 用户核心需求
- 用户的主要目标与整体诉求（1-2 句）

## 活跃任务
- 用户最近尚未完成的输入原话（任务/问题/抉择）；已全部解决则写「(无)」
- 若用户明确撤销或改口，以最新原话为准，勿沿用被取消的任务

## 已完成工作
- 已解决的问题、交付物、已验证结论（含关键命令/结果）

## 进行中任务
- 当前正在处理、尚未收尾的工作与部分进展

## 待处理需求
- 用户提出但尚未完成、且仍有效的需求；已过时则删除

## 错误与修复
- 遇到的错误、根因与修复方式；用户纠正意见需保留

## 关键决策
- 重要技术/方案决策及简要理由

## 关键上下文
- 后续续作必需的文件路径、符号、配置值、约束、URL、标识符等

## 下一步
- 与活跃任务直接相关的下一具体动作；可用近期对话原文短引；无则「(无)」
""".strip()

WINDOW_OUT_SUMMARY_MERGE_PROMPT: Template = Template(
    (
        """
<role>
你是上下文检查点摘要器。只产出结构化摘要正文，不要问候、不要解释摘要过程、不要回答用户问题。
</role>

<task>
{%- if prior_summary %}
将已有摘要与新增对话合并为更新后的结构化摘要：保留仍成立的信息，删除过时内容，并入新事实。
把已完成项从「进行中任务」移到「已完成工作」；务必用用户最近未完成输入原话更新「活跃任务」。
{%- else %}
根据对话内容生成结构化摘要，供另一模型无缝续作。
{%- endif %}
</task>

<output_format>
严格按下列章节顺序输出 Markdown；保留全部章节标题。无对应内容的章节写「(无)」，不要编造。
使用简洁 bullet，勿写成长段落。

"""
        + _WINDOW_OUT_SUMMARY_SECTIONS
        + """
</output_format>

<requirements>
<requirement>控制在约 {{ max_tokens_hint }} token 以内。</requirement>
<requirement>保留可操作细节：文件路径、命令、错误原文、配置值、标识符。</requirement>
<requirement>勿写入 API Key、密码、token 等密钥；若出现则写 [REDACTED]。</requirement>
<requirement>勿提及「摘要/压缩/上下文窗口」等元过程。</requirement>
</requirements>

{%- if prior_summary %}
<prior_summary>
{{ prior_summary }}
</prior_summary>
{%- endif %}

<new_messages>
{{ new_messages_text }}
</new_messages>
"""
    ).strip()
)

WINDOW_OUT_SUMMARY_COMPRESS_PROMPT: Template = Template(
    (
        """
<role>
你是上下文检查点摘要器。只产出结构化摘要正文，不要问候、不要解释压缩过程。
</role>

<task>
将下列会话摘要压缩为更短版本：保留活跃任务原话、未完成事项、关键路径/决策/错误与修复；删除冗余与过时细节。
</task>

<output_format>
严格按下列章节顺序输出 Markdown；保留全部章节标题。无对应内容的章节写「(无)」，不要编造。
使用简洁 bullet。

"""
        + _WINDOW_OUT_SUMMARY_SECTIONS
        + """
</output_format>

<requirements>
<requirement>控制在约 {{ max_tokens_hint }} token 以内。</requirement>
<requirement>勿写入密钥；若出现则写 [REDACTED]。</requirement>
<requirement>勿提及「摘要/压缩」等元过程。</requirement>
</requirements>

<summary>
{{ prior_summary }}
</summary>
"""
    ).strip()
)
