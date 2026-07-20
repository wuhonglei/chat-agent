# Function Call 参数校验四层机制对比

## 1 类型校验 — 参数类型是否正确

检查 LLM 返回的参数值是否符合预期类型（string / number / boolean / array / object）

| chat-agent | 无显式类型校验 _filter_arguments 只做 key 白名单过滤，不检查 value 类型。MCP server 自己兜底。 | 弱 |
|---|---|---|
| claude-code | Zodschema.safeParse 每个工具定义inputSchema （Zod schema），类型不对直接返回InputValidationError 给模型。最严格。 | 强 |
| deer-flow | LangChain @tool 从 type hints 自动做基础类型转换，ToolNode 内部调用前尝试 coerce 参数类型。 | 中 |
| hermes-agent | 无框架级类型校验 _parse_tool_arguments 只检查是否是合法 JSON dict，不校验字段类型。工具自己负责。 | 弱 |

## 2 格式校验 — 必填字段、字段范围、schema 合规

检查必填参数是否存在、字段值是否在允许范围内、是否符合 schema 定义

| chat-agent | schema required 校验 _validate_required : 检查schema.required 中的字段是否存在，缺少必填参数直接raise ValueError 。 _filter_arguments : strict_whitelist 模式下移除 schema 外的字段，并生成 warning。 | 中 |
|---|---|---|
| claude-code | ZodvalidateInput Zod 的safeParse 同时覆盖类型 + 格式（required / optional / enum / min / max 等）。校验失败返回详细的formatZodValidationError 。 额外有tool.validateInput() 二次校验（工具自定义逻辑）。 | 强 |
| deer-flow | LangChain @toolPydantic @tool 装饰器从 docstring 解析 Args 描述，LangChain 做基础 required 检查。Pydantic model 工具自动做 schema 验证。 | 中 |
| hermes-agent | 无框架级格式校验 工具自己检查参数合法性。框架不介入。 | 弱 |

## 3 权限校验 — 是否有权执行这个工具

在工具实际执行前，检查当前 session / 用户是否有权限调用该工具

| chat-agent | 无权限校验 所有注册的 MCP 工具都可以被调用。无用户级/session 级权限控制。 | 无 |
|---|---|---|
| claude-code | PreToolUseHookscanUseToolclassifier 三层权限： 1.runPreToolUseHooks : 前置钩子可拦截/修改输入 2.resolveHookPermissionDecision → canUseTool :allow /deny /ask 三种结果，ask 弹出用户确认对话框 3. BashTool 额外有 AI classifier 判断命令安全性（startSpeculativeClassifierCheck 并行预判） 权限来源：session 临时授权 / 永久配置 / policy / hook | 最强 |
| deer-flow | GuardrailMiddlewareGuardrailProvider 工具调用前通过provider.evaluate() 做授权决策。 支持 allow / deny，deny 返回错误 ToolMessage。 支持fail_closed=True （provider 异常时默认拒绝）。 支持user_role / oauth 做角色级权限控制。 | 强 |
| hermes-agent | pre_tool_blockToolSearch scope gate 1. 插件层resolve_pre_tool_block 可拦截工具调用 2.ToolSearch scope gate : 检查工具是否在当前 session 的工具集内，越权直接拒绝 3.tool_guardrails.before_call : 断路器模式（见 Layer 4） | 中 |

## 4 业务边界校验 — 参数值是否合理、是否会导致危险操作

检查参数值本身是否安全合理，防止死循环、危险命令、路径冲突等业务层面的风险

| chat-agent | 执行后校验 _resolve_tool_outcome : 执行后判断成功/失败（不是执行前）。 shell 看 exit_code / blocked / timed_out；code_exec 看 compile_code / run_code；其他看内容是否为空。 URL 去重 : web_pages_extract 检查 URL 是否已提取过，避免重复抓取。 | 中（后置） |
|---|---|---|
| claude-code | BashTool 安全路径边界 BashTool 有专门的业务边界校验： -bashSecurity.ts : 检测危险命令模式 -bashPermissions.ts : 命令前缀规则匹配 -_simulatedSedEdit 防注入 : 剥离模型伪造的内部字段 File 工具:expandPath 做路径规范化 + 边界检查 | 强 |
| deer-flow | GuardrailProvidersandboxbudget middleware -GuardrailProvider.evaluate() 可包含业务规则，基于 tool_name + tool_input 做策略判断 - 基于user_role 做角色级业务限制 -sandbox_config : 沙箱环境限制工具能力 -tool_output_budget_middleware : 控制工具输出大小 | 强 |
| hermes-agent | 断路器危险命令检测路径冲突检测 断路器模式 （ToolCallGuardrailConfig ）： -exact_failure_block_after=5 : 同参数失败 5 次自动阻断 -same_tool_failure_halt_after=8 : 同工具失败 8 次停止整个 turn -no_progress_block_after=5 : 幂等工具无进展 5 次阻断 - 区分idempotent_tools （只读）vsmutating_tools （写入） 危险命令 :_is_destructive_command 检测 shell 危险命令 路径冲突 :_paths_overlap 检测并行工具的文件路径冲突 | 强 |

## 📊 校验完整性总览

claude-code

4 层全覆盖 · Zod 类型+格式一体化 · 权限系统最复杂

hermes-agent

框架不管类型/格式（工具自管）· 权限+业务边界靠断路器

deer-flow

LangChain 做基础类型 · GuardrailMiddleware 做权限+业务

chat-agent

只做 schema 白名单 + 必填校验 · 无权限 · 业务边界靠执行后判断

为什么 chat-agent 最轻量？
 作为内部 MCP 工具平台，工具来源可信（自研 MCP server），当前的轻量校验是合理的。如果未来要支持用户自定义工具或第三方 MCP，建议至少加一层 Zod / Pydantic 类型校验。

## 🔍 附录：hermes-agent 的路径冲突检测机制

当 LLM 一次返回多个文件操作工具调用时，如何判断哪些可以并行、哪些必须串行

场景：LLM 一次返回 3 个工具调用 1. write_file(path="a.txt", content="hello") 2. write_file(path="a.txt", content="world") ← 同一个文件！ 3. read_file(path="b.txt") 调度过程（_plan_tool_batch_segments）： 遍历 tool_calls: write_file("a.txt") → reserved_paths = [a.txt] → 加入并行组 write_file("a.txt") → paths_overlap(a.txt, a.txt) = True → 关闭当前并行组 开始新组 read_file("b.txt") → 无冲突 → 加入新并行组 输出： ┌─ parallel: [write_file("a.txt")] ← 第一组 └─ parallel: [write_file("a.txt"), read_file("b.txt")] ← 第二组 执行： 第一组先完成 → 第二组再并行执行_paths_overlap 判断逻辑（Path.parts 前缀比较）： Path("/a/b/c").parts → ('/','a','b','c') Path("/a/b/d").parts → ('/','a','b','d') 前缀('/','a','b') 相同 → 冲突 （保守策略，宁可串行不冒险） Path("/a/b").parts → ('/','a','b') Path("/x/y").parts → ('/','x','y') 前缀('/',) 之后不同 → 不冲突，可并行 只对文件类工具生效： read_file / write_file / patch（_PATH_SCOPED_TOOLS） terminal / search 等工具不做路径检查，要么在安全列表里直接并行，要么强制串行。
