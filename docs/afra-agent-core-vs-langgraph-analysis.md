# Afra Agent Core、LangGraph 与 Claude Code queryEngine 实现差异分析

## 1. 结论摘要

当前 Afra 的 `core/` 不是 Go 版 LangGraph，而是一个面向基础设施工作的 Agent Runtime / Agent Core。两者都能驱动“模型决定下一步、调用工具、继续执行”的 Agent，但设计中心不同：

- LangGraph 的核心是通用有向图运行时：开发者定义 State、Node、Edge，框架负责状态传播、路由、持久化、恢复、流式输出和图级调试。
- Afra 的核心是产品化的长任务执行系统：以 Task、Run、AgentLoop、Tool、Approval、Workspace、Event 为主，重点解决基础设施场景中的安全审批、权限、沙箱、子任务、外部 Agent、技能/MCP 管理、事件审计和多入口接入。
- Afra 当前的 `AgentLoop` 在默认路径上更接近一个“固定的 model → tools → model 循环”，并没有把业务流程抽象成用户可声明的通用图。
- Claude Code 的 `src/query.ts` 是另一种成熟的固定循环：它同样以模型 Tool Use 为驱动，但把流式响应、工具并发、权限 Hook、上下文压缩、fallback 和 Session 恢复做得更深。
- 因此，Afra 相比 LangGraph 多了大量产品运行时与运维安全能力；相比 LangGraph 则缺少通用图编排、精确图状态检查点、节点级错误恢复、原生并行、通用中断恢复和流式图执行能力。

最重要的判断是：Afra 不需要整体改造成 LangGraph。更合适的方向是保留 Task/Run/Approval/Safety/Event 等产品层，在 AgentLoop 下增加一个可选的 Agent Graph 执行层，把当前固定循环作为默认图实现。

## 2. 分析范围与依据

分析对象是当前仓库的：

`/Users/zhangqi.huang/GolandProjects/afra-agent/core/`

本报告重点检查了以下模块：

- `core/engine`：AgentLoop、TaskManager、消息构造、工具选择、安全策略、压缩、工具实现。
- `core/facade`：Agent Core 的组装与对外入口。
- `core/admin`：Agent、Skill、MCP、Provider、Model 等管理目录。
- `core/llm`：LLM Provider 抽象与适配器。
- `store`：SQLite、JSONL、Checkpoint、Memory、Approval 等持久化实现。
- `core/engine/tool`：内置工具、委派、审批、计划、记忆和外部 Agent 工具。

LangGraph 对比依据为官方文档中的 Graph API、Persistence、Time Travel、Interrupts、Streaming、Fault Tolerance、Subgraphs、Memory 等机制：

- [Graph API](https://docs.langchain.com/oss/python/langgraph/graph-api)
- [Persistence](https://docs.langchain.com/oss/python/langgraph/persistence)
- [Time Travel](https://docs.langchain.com/oss/python/langgraph/use-time-travel)
- [Interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts)
- [Streaming](https://docs.langchain.com/oss/python/langgraph/streaming)
- [Fault Tolerance](https://docs.langchain.com/oss/python/langgraph/fault-tolerance)
- [Subgraphs](https://docs.langchain.com/oss/python/langgraph/use-subgraphs)
- [Memory](https://docs.langchain.com/oss/python/langgraph/add-memory)

## 3. Afra 当前 Core 的真实结构

### 3.1 组装关系

Afra 的默认装配链路如下：

```text
AgentCoreFacade
    └── AgentCore
        ├── MessageBuilder
        ├── ToolSelector
        ├── AgentLoop
        │   ├── LLM Provider
        │   ├── Tool Registry
        │   ├── SafetyEngine
        │   ├── ApprovalStore
        │   ├── MessageStore
        │   ├── Checkpoint / RunLog
        │   └── Event / Usage projection
        └── TaskManager
            ├── TaskStore
            ├── RunStore
            ├── EventStore
            └── child Run / recovery orchestration
```

核心组装位于 [`core/facade/agent_core.go`](/Users/zhangqi.huang/GolandProjects/afra-agent/core/facade/agent_core.go:227)。它把消息构造器、工具选择器、AgentLoop 和 TaskManager 连接起来，再向 CLI、TUI、REST Server 提供统一入口。

### 3.2 Afra 的生命周期模型

Afra 的核心实体不是 Graph，而是：

| 实体 | 当前语义 |
|---|---|
| Task | 用户希望完成的持续性工作目标，可包含多个 Run |
| Run | 一次用户消息到 Agent 响应的执行轮次，拥有自己的事件、消息、审批和执行状态 |
| Event | 面向 UI、审计和工作区时间线的事件投影 |
| Agent | 可执行 Worker 的身份、人格、能力、工具、技能和权限配置 |
| Workspace | 组织 Task/Run、工作目录和审批记忆的工作上下文，不是安全边界 |
| Child Run | 通过 `delegate` 创建的子执行单元，仍然是 Run，而不是单纯的函数调用 |

Task、Run 和状态定义位于 [`core/engine/types.go`](/Users/zhangqi.huang/GolandProjects/afra-agent/core/engine/types.go:92)。这套模型适合产品层的会话、任务、审批、恢复和审计，但不像 LangGraph State 那样直接代表任意业务流程中的全部运行状态。

### 3.3 AgentLoop 的默认执行路径

当前 AgentLoop 的主要路径是：

```text
接收 Run
  → 构造系统提示词和 Run 上下文
  → 选择当前可用工具
  → 调用 LLM
  → 解析文本和 Tool Calls
  → 逐个执行工具
  → 写入 Tool Result / Event / Message
  → 再次调用 LLM
  → 最终回答、等待用户输入、等待审批或失败
```

入口位于 [`core/engine/agent_loop.go`](/Users/zhangqi.huang/GolandProjects/afra-agent/core/engine/agent_loop.go:117)。当前工具调用的处理是 AgentLoop 内部的固定控制流，多个 Tool Calls 默认按顺序处理，而不是由可声明的图边或调度器决定。

当前内置工具注册表覆盖的能力包括：

- 文件读写、编辑、Patch、Glob、Grep、目录浏览。
- Bash 和 Git 状态、Diff、Log、Show。
- Web Search、Web Fetch。
- MCP 动态工具。
- Skill 文件读取。
- `update_plan`、`read_plan`、`ask_user`、`checkpoint`、`finish`。
- `delegate` 子 Run 委派。
- Memory 读写。
- 外部 Agent 的发送、查询、取消和等待。
- 睡眠、等待和其他运行时辅助能力。

注册位置见 [`core/engine/tool/builtin_registry.go`](/Users/zhangqi.huang/GolandProjects/afra-agent/core/engine/tool/builtin_registry.go:71)，工具接口和元数据定义见 [`core/engine/tool/tool.go`](/Users/zhangqi.huang/GolandProjects/afra-agent/core/engine/tool/tool.go:11)。

## 4. LangGraph 的核心模型

LangGraph 的抽象中心是：

```text
StateGraph
  ├── State：类型化状态、字段、Reducer
  ├── Node：读取 State 并返回 State 更新
  ├── Edge：固定或条件路由
  ├── Command：在节点内同时更新状态和改变路由
  ├── Send：动态 fan-out，把不同输入发送给多个节点实例
  ├── Super-step：可并行执行的一组节点及其状态归并
  └── Checkpointer：按 thread_id / checkpoint 保存可恢复图状态
```

LangGraph 的关键特点是执行流程显式存在于 Graph 定义中，而不是隐藏在一个 AgentLoop 的循环体中。典型的 Agent 图可以是：

```text
START
  → call_model
      ├── 无 Tool Call → END
      └── 有 Tool Call → tool_node
                            └── call_model
```

复杂流程还可以继续展开为审批节点、重试节点、并行调查节点、聚合节点、人工确认节点和回滚节点。State 的字段更新可以通过 Reducer 合并，节点执行可以借助 Checkpointer、RetryPolicy、Interrupt 和 Streaming 组合成可恢复的长流程。

## 5. 总体能力对比

| 对比维度 | Afra 当前实现 | LangGraph | 判断 |
|---|---|---|---|
| 顶层抽象 | Task、Run、AgentLoop、Workspace | Graph、Thread、State、Checkpoint | 产品生命周期 vs 通用流程编排 |
| 流程表达 | 固定 AgentLoop，部分行为由工具触发 | 显式 Nodes、Edges、条件边 | LangGraph 更通用 |
| 状态模型 | 固定 Go 结构、消息数组、Run 上下文 | 类型化 State、Channels、Reducers | LangGraph 更适合复杂工作流 |
| 路由机制 | 主要由 LLM Tool Calls 和工具内部逻辑决定 | 普通边、条件边、Command、Send | LangGraph 路由可编程 |
| Tool 执行 | Tool 接口 + AgentLoop 顺序执行 | Tool 通常作为图节点或 ToolNode | Afra 更产品化，LangGraph 更可组合 |
| 并行 | 当前 Tool Calls 默认顺序执行；子 Run 仍以任务编排为主 | 同一 super-step 的节点可以并行，支持动态 Send | LangGraph 明显更强 |
| 子 Agent | `delegate` 创建 Child Run，可限深度、限数、等待、取消 | Subgraph、Send、Command、handoff | Afra 具备产品级子任务管理，LangGraph 具备图级组合 |
| 持久化 | SQLite 表、JSONL Run Log、摘要文件、部分 Checkpoint | 每个 super-step 的 State Snapshot | 两者目标不同，Afra 当前持久化较分散 |
| 恢复 | 通过 Run Log 和未完成 Tool Call 重建执行上下文 | 根据 checkpoint 恢复完整 State、next、metadata、pending writes | LangGraph 恢复模型更精确 |
| 时间旅行 | 没有完整的 get_state/history/update_state/replay/fork 图 API | 原生支持历史检查点、分支和重放 | Afra 缺少 |
| 人工介入 | `ask_user`、ApprovalStore、waiting 状态、继续执行 | `interrupt()` + Command(resume) | Afra 有产品审批，LangGraph 中断更通用 |
| 审批编辑 | 当前主要是批准/拒绝和审批后继续 | HITL 支持 approve、edit、reject 等动作 | LangGraph 在交互形态上更灵活 |
| 重试 | 主要是 Run 级恢复和存储重试 | 节点级 RetryPolicy、退避、超时、错误处理 | LangGraph 更细粒度 |
| 流式输出 | Provider 当前以同步 Chat 为主，事件多在阶段完成后写入 | 支持多种 stream mode、节点更新、消息、调试事件 | Afra 需要增强实时性 |
| 短期记忆 | MessageStore、JSONL、Compactor | Checkpoint State + message state | Afra 更偏会话产品，LangGraph 更偏执行状态 |
| 长期记忆 | SQLite Key/Value 和关键词匹配 | Store namespace，可接语义搜索 | LangGraph 扩展点更标准 |
| 安全控制 | 风险等级、幂等性、审批、路径限制、危险命令、沙箱、凭据过滤 | LangGraph Core 不等价提供 OS 级安全运行时 | Afra 明显更强 |
| 基础设施工具 | Bash、Git、文件、Web、MCP、外部 Agent 等 | 通常由应用或生态自行提供 | Afra 开箱能力更多 |
| 管理后台能力 | Agent、Skill、MCP、Provider、Model Catalog | 主要依赖 LangChain/LangGraph Platform 或应用侧 | Afra 产品化程度更高 |
| 可观测性 | EventStore、Run 事件、Usage、Efficiency | Stream、Checkpoint、LangSmith 集成 | 侧重点不同 |
| 工作流缓存 | 当前未见通用节点缓存 | 支持在图节点层实现/配置缓存能力 | Afra 缺少 |
| 图版本管理 | 当前没有公开 Graph Definition / Version 模型 | 应用侧可对图定义和部署版本管理 | Afra 缺少通用机制 |

## 6. Afra 相比 LangGraph 缺少什么

以下是当前实现中最明显的差距。这里的“缺少”指 Afra Core 没有提供与 LangGraph 同层次的通用能力，而不是说应用层无法自行补充。

### 6.1 缺少通用 Graph 执行模型

当前 Afra 没有公开的：

- Node 定义。
- Edge 定义。
- 条件路由。
- `START` / `END`。
- `Command` 式状态更新加路由跳转。
- `Send` 式动态 fan-out。
- super-step 和节点间状态归并。
- 图编译、图验证和图结构检查。

Afra 当前流程主要写在 `AgentLoop` 和各工具的实现中。这样做对“通用基础设施 Agent”很直接，但当流程从单 Agent 循环扩展为“调查 → 并行取证 → 汇总 → 风险审批 → 执行 → 验证 → 回滚”时，控制流会继续堆积到 AgentLoop、Tool 和 TaskManager 中，难以像 LangGraph 一样按节点拆分和复用。

### 6.2 缺少类型化 State、Reducer 和 Channel

Afra 有 Task、Run、Message、Plan、Checkpoint 等类型，但它们是产品实体，不是可由用户自由声明的工作流状态。当前没有类似以下能力：

```text
State = {
  target_clusters: []
  evidence: []
  risk_level: string
  approval: ApprovalState
  execution_result: Result
}
```

也没有统一的 Reducer 语义来处理多个并行节点同时更新同一字段，例如：

- 列表追加而不是覆盖。
- 数值求和或取最大值。
- 按 key 合并对象。
- 冲突检测。
- 版本化状态更新。

当前状态主要分布在消息历史、工具返回值、Run 字段、事件和外部存储中，缺乏一个面向工作流作者的统一状态契约。

### 6.3 Checkpoint 不是完整的图状态检查点

LangGraph Checkpointer 通常记录某个 thread 在某一个执行步骤的完整图状态，并带有 checkpoint id、父 checkpoint、下一步节点、metadata 和 pending writes，因此可以支持恢复、历史查看、重放、分支和时间旅行。

Afra 当前更接近“执行日志 + 恢复信息”的组合：

- Run Log 保存消息、Tool Call、Tool Result 和摘要。
- Compactor 保存压缩摘要和文件清单。
- TaskManager 另写 JSON checkpoint 文件。
- SQLite 也存在 Checkpoint 相关存储和查询入口。

这套机制能够支撑基本恢复，但还不是单一、可寻址、可分支的完整执行状态模型。目前没有统一暴露：

- `checkpoint_id`。
- `parent_checkpoint_id`。
- 当前 `next` 节点或待执行任务。
- checkpoint metadata。
- `get_state`。
- `get_state_history`。
- `update_state`。
- 从任意历史点 replay、fork、time travel。
- 节点失败后不丢失的 pending writes。

### 6.4 缺少 pending writes 语义

LangGraph 的 pending writes 机制允许同一 super-step 中某些节点已经完成的写入在另一节点失败时保留下来，重试时无需重复执行已经成功的节点。

Afra 当前恢复主要依靠 Run Log 和消息重建。对于多个工具、多个并行分支或未来的图节点来说，尚未形成“哪些状态写入已经成功、哪些节点仍需重试”的统一模型，因而更容易出现重复执行或只能从较粗粒度重新开始的问题。

需要注意，LangGraph 的 Checkpoint 也不能自动回滚已经发生的外部副作用，例如数据库写入、扩容、发布或删除操作。无论采用哪种框架，外部动作仍需要幂等键、补偿操作、事务或显式回滚设计。

### 6.5 缺少节点级 RetryPolicy、Timeout 和 Error Handler

Afra 有 Tool 级风险和执行错误处理，也有 Run 级恢复，但当前没有面向任意流程节点的统一策略：

- 最大重试次数。
- 指数退避。
- 抖动。
- 单节点超时。
- 可重试错误分类。
- 节点失败后的 fallback 节点。
- 节点错误转换为 State 更新。
- 节点级重试而非整个 Run 重启。

TaskManager 的启动和执行协作位于 [`core/engine/task_manager.go`](/Users/zhangqi.huang/GolandProjects/afra-agent/core/engine/task_manager.go:404)，当前重点是 Run 生命周期和恢复，而不是通用节点调度策略。

### 6.6 缺少真正的图级流式执行

当前 `llm.Provider` 的核心抽象是同步 `Chat`：

[`core/llm/provider.go`](/Users/zhangqi.huang/GolandProjects/afra-agent/core/llm/provider.go:8)

因此 Afra 可以在关键阶段写事件，但没有统一抽象来实时输出：

- LLM token。
- 当前节点开始/结束。
- 节点状态更新。
- Tool Call 参数增量。
- Tool Result 增量。
- checkpoint 变化。
- 调试级执行信息。
- 子图和子 Run 的嵌套流。

LangGraph 的 streaming 机制可以按 messages、updates、values、custom、debug 等模式消费执行过程。Afra 如果要支持更强的实时 UI、远程任务进度和长时间基础设施操作，需要在 Provider、AgentLoop、EventStore 和 REST/SSE 层形成端到端流式链路。

### 6.7 中断能力还不是通用 interrupt

Afra 目前有明确的两类等待：

- `ask_user`：Agent 主动向用户提问。
- Tool Approval：高风险或非幂等工具等待审批。

对应代码位于：

- [`core/engine/agent_loop.go`](/Users/zhangqi.huang/GolandProjects/afra-agent/core/engine/agent_loop.go:717)
- [`core/engine/agent_loop.go`](/Users/zhangqi.huang/GolandProjects/afra-agent/core/engine/agent_loop.go:770)

这满足当前 Agent 产品需求，但与 LangGraph 的任意节点 `interrupt()` 仍有差异：

- 任意业务节点都可以暂停。
- 一个节点中可以有多个中断点。
- 中断值是结构化 payload，而不是固定的询问/审批类型。
- 通过 `Command(resume=...)` 将恢复值回填到原节点。
- 支持对工具参数进行 edit 后继续。
- 中断状态自然落到 checkpoint 中。

Afra 后续可把 `ask_user` 和审批统一建模成 `Interrupt`，再在产品层保留问答和审批两种 UI 语义。

### 6.8 长期记忆缺少标准 namespace 和语义检索

Afra Memory 当前使用 SQLite 存储，查询主要是关键词匹配，相关实现见：

[`store/memory_store.go`](/Users/zhangqi.huang/GolandProjects/afra-agent/store/memory_store.go:47)

它能满足基本的记忆保存和读取，但与 LangGraph Store 的 namespace 语义相比，当前缺少更明确的：

- 用户级、Workspace 级、Agent 级、Task 级 namespace。
- 跨会话稳定的记忆生命周期。
- 语义检索或向量索引扩展点。
- 记忆版本、来源和可信度。
- 记忆过期、冲突和删除策略。

### 6.9 缺少图版本、图级测试和缓存

当前 Core 没有通用的 Graph Definition，因此也没有对应的：

- 图版本和迁移策略。
- 图结构校验。
- 从任意节点开始的局部测试。
- 节点输入/输出契约测试。
- 节点结果缓存。
- 图执行结果复用。

这些不是单 Agent Loop 的必需能力，但在 Agent 流程变复杂后会直接影响可维护性和验证效率。

## 7. Afra 相比 LangGraph 多了什么

LangGraph 本身是图执行基础设施，很多产品能力需要由 LangChain、LangGraph Platform 或业务系统补充。Afra 当前已经实现了不少 LangGraph Core 不直接覆盖的能力。

### 7.1 产品级 Task/Run/Workspace 生命周期

Afra 原生区分 Task 和 Run，并以 Run 作为用户可见的一轮执行单元，支持：

- 一个 Task 多轮继续。
- Run 状态：pending、running、waiting_for_input、waiting_for_approval、completed、failed、cancelled。
- Run 级事件和工作区时间线。
- 子 Run。
- 任务取消、恢复和归档。
- 附件、计划、审批、用量和效率数据。

LangGraph 的 thread/checkpoint 可以承载一部分这些信息，但不会自动提供完整的产品实体、UI 事件模型和用户任务生命周期。

### 7.2 更强的安全、审批和副作用控制

Afra 的 SafetyEngine 不只是“节点失败后如何恢复”，还会在执行前判断工具的安全属性：

- 风险等级。
- 是否幂等。
- 是否有外部副作用。
- 是否必须审批。
- 是否允许访问目标路径。
- 是否属于危险命令。
- 是否需要在沙箱中执行。
- 是否需要过滤环境变量和凭据。

核心安全策略见 [`core/engine/safety.go`](/Users/zhangqi.huang/GolandProjects/afra-agent/core/engine/safety.go:48)，沙箱入口见 [`core/engine/sandbox/sandbox.go`](/Users/zhangqi.huang/GolandProjects/afra-agent/core/engine/sandbox/sandbox.go:1)。

这类能力是基础设施 Agent 的关键。LangGraph 的 interrupt/HITL 可以实现“暂停等待决策”，但不等价于 Afra 面向操作系统、Shell 和敏感凭据的安全控制。

### 7.3 面向基础设施工作的工具集

Afra 默认提供文件、Shell、Git、Web、MCP、外部 Agent 和计划等工具，并围绕基础设施操作定义了风险和权限语义。这使它更像一个可以直接执行生产调查和运维操作的 Worker Runtime，而不是一个等待业务系统注入工具的图框架。

### 7.4 Agent、Skill、MCP、Provider、Model 管理目录

Afra 有独立的 admin 层，用于管理：

- Agent Catalog。
- Skill Catalog。
- MCP Server Catalog。
- LLM Provider Catalog。
- Model Catalog。

这些目录可以被 AgentCore、MessageBuilder、ToolSelector 和运行时解析使用，形成了面向产品部署的配置和能力管理。LangGraph Core 没有对应的统一管理域模型。

### 7.5 产品级子 Run 委派和外部 Agent 协作

Afra 的 `delegate` 不只是调用一个 Python 子图，而是创建一个真正的 Child Run，可以跟踪：

- 父子关系。
- 委派深度。
- 子任务数量限制。
- 子 Run 状态。
- 等待和取消。
- 子 Run 的事件。
- 子 Run 的结果回传。

本地委派的执行路径位于 [`core/engine/agent_loop.go`](/Users/zhangqi.huang/GolandProjects/afra-agent/core/engine/agent_loop.go:1348)。此外，Afra 还支持远程/外部 Agent 的发送、轮询、等待和取消，这是单纯图子程序通常不会直接解决的产品协作问题。

### 7.6 LLM Provider 和运行时能力适配

Afra 有 OpenAI、Anthropic 等 Provider 适配，并把 Provider、Model、Reasoning、Vision、Usage 等信息纳入运行时选择。它不是只假设一个固定模型，而是将模型配置视为可管理的数据域。

### 7.7 面向 Agent 上下文的压缩策略

Afra Compactor 不只是简单截断消息，而是围绕 Agent 工作场景设计：

- 两阶段压缩。
- 保存任务目标和计划。
- 保留非幂等工具结果。
- 保存文件清单和工作区信息。
- 生成摘要以支撑后续继续执行。

实现位于 [`core/engine/compactor.go`](/Users/zhangqi.huang/GolandProjects/afra-agent/core/engine/compactor.go:83)。这比 LangGraph 的原始 State 持久化更贴近“长时间基础设施工作中如何控制上下文窗口”的产品问题。

### 7.8 独立的事件、用量和效率投影

Afra 有自己的 EventStore、Usage 和 Efficiency 数据，用于产品界面、任务时间线、审计、运营和成本分析。LangGraph 可以通过 streaming 和 LangSmith 做可观测性，但 Afra 的投影模型更贴近其产品实体。

## 8. 同类功能的实现方式差异

### 8.1 对话记忆与执行状态

Afra：


```text
Task / Run
  → MessageStore / JSONL Run Log
  → Compactor 生成摘要、计划和文件清单
  → 恢复时重建消息上下文
```

LangGraph：

```text
thread_id
  → 每个 super-step 的 State Snapshot
  → checkpoint_id / parent checkpoint
  → 从指定 checkpoint 恢复、重放或分支
```

差异在于：Afra 的持久化以“Agent 会话和产品 Run”为中心，LangGraph 的持久化以“图状态和图执行步骤”为中心。Afra 对用户会话语义更完整；LangGraph 对流程状态的精确定位和时间旅行更完整。

### 8.2 Tool Loop 与 Graph Node

Afra 的工具是显式接口，工具带有名称、描述、参数 Schema、风险、幂等性和执行函数。AgentLoop 调用 LLM 后解析 Tool Calls，并在循环中执行工具。

LangGraph 中，工具可以被包成一个 Node，也可以放进 ToolNode；模型节点、工具节点、审批节点和聚合节点之间通过 Edge 连接。工具执行的位置由图定义决定，而不是隐含在一个固定循环内。

因此：

- Afra 的 Tool 元数据更适合安全策略和产品审批。
- LangGraph 的 Node/Edge 更适合组合任意业务流程。
- Afra 当前不能简单地把任意 Tool 当作一个完整图节点，因为 Tool 的执行前后还依赖 AgentLoop 内部的消息、审批和恢复逻辑。

### 8.3 路由和分支

Afra 的主要路由来源是：

- LLM 是否返回 Tool Call。
- 工具是否要求审批。
- 工具是否触发等待用户输入。
- `delegate` 是否创建子 Run。
- AgentLoop 是否达到最终响应或失败条件。

LangGraph 的主要路由来源是：

- 普通 Edge。
- 条件 Edge。
- 节点返回的 Command。
- 动态 Send。
- State 中的业务字段。

Afra 的路由更灵活地交给模型，但可预测性和静态分析弱；LangGraph 的路由更容易测试、可视化和验证，但需要开发者显式设计流程。

### 8.4 并行执行

Afra 当前 AgentLoop 对一个响应中的多个 Tool Calls 默认按序处理。这种方式有两个优点：安全判断简单，工具结果顺序稳定；缺点是多个只读调查任务无法自然并行。

LangGraph 会将同一 super-step 中可执行的多个节点并行调度，并通过 Reducer 归并结果；`Send` 还能动态产生多个相同节点实例。

对于基础设施场景，这会影响：

- 多集群指标查询。
- 多主机日志读取。
- 多服务健康检查。
- 多个只读数据源并行取证。

Afra 后续应该先增加“只读、无副作用 Tool 的并行组”，再考虑任意工具并行。非幂等写操作不应因为追求图并行而默认并发。

### 8.5 子 Agent / 子图

Afra：Child Run 是可审计的产品实体，有父子 Run 关系、深度/数量限制、状态和取消。委派可以是同步等待，也可以成为独立的异步运行单元。

LangGraph：Subgraph 是图组合机制，可以按 per-invocation、per-thread 或 stateless 方式持久化，并在父图中作为节点调用。它更关注状态命名空间、图组合和执行边界。

两者并非完全替代关系：

- Afra Child Run 解决“谁委派了谁、谁负责、如何审计和取消”。
- LangGraph Subgraph 解决“如何把一个可复用流程嵌入另一个图”。

### 8.6 审批和人工介入

Afra 的流程大致是：

```text
Tool Metadata
  → SafetyEngine 判定风险/幂等性/权限
  → 创建 Approval 记录
  → Run 进入 waiting_for_approval
  → 用户批准或拒绝
  → 恢复 AgentLoop
```

LangGraph 的流程大致是：

```text
Node / Tool 执行到 interrupt()
  → Checkpoint 保存状态
  → 外部 UI 展示中断 payload
  → Command(resume=value)
  → 从中断位置继续节点
```

Afra 的审批更接近“安全策略驱动的产品审批”；LangGraph 的 interrupt 更接近“通用的可暂停程序”。Afra 若引入统一 Interrupt，应该保留 SafetyEngine 作为其中一个触发源，而不是用通用中断替代安全判定。

### 8.7 上下文压缩

Afra 的 Compactor 有明确的 Agent 语义，关心哪些工具结果不可重复、哪些文件和计划必须保留，并通过摘要缩短消息上下文。

LangGraph 更偏向保存完整 State；如果要做对话摘要、删除消息或压缩历史，通常由应用层在 State 更新或节点中实现。

因此 Afra 在“长对话 Agent 上下文管理”方面更开箱即用，但 LangGraph 的 State 机制更适合把摘要作为一个显式节点纳入图流程。

### 8.8 故障恢复

Afra 当前恢复思路是：

```text
读取 Run / JSONL Log
  → 找到最后完成的消息与工具结果
  → 识别未完成或 unresolved Tool Call
  → 重建上下文
  → 继续或重跑 AgentLoop
```

LangGraph 当前恢复思路是：

```text
读取 thread 的最新 checkpoint
  → 恢复 State、next、metadata、pending writes
  → 只重试失败的节点或从指定节点继续
```

Afra 的恢复更像会话级恢复；LangGraph 的恢复更像图执行级恢复。前者实现简单、符合当前 Agent 产品模型，后者更适合复杂 DAG、并行和长流程。

### 8.9 可观测性

Afra 通过 EventStore 记录产品事件和 Run 事件，前端可按 Run 和 Workspace 聚合展示，并可以叠加用量、效率和审批数据。

LangGraph 通过 stream mode 暴露节点更新、消息、值、调试信息，并可接入 LangSmith 做 trace、状态和运行分析。

Afra 更适合产品 UI 和审计；LangGraph 更适合图级调试和节点级追踪。若 Afra 引入 Graph，事件中需要额外增加 `graph_id`、`graph_version`、`node_id`、`step`、`checkpoint_id` 等字段，而不能只依赖当前的 Run 事件。

## 9. 当前实现中值得优先修复的内部问题

下面这些不只是“与 LangGraph 的差异”，而是当前 Afra 自身已经暴露出的架构一致性风险。

### 9.1 Checkpoint 写入和读取存在分裂

当前 `checkpoint` 工具的执行逻辑只返回“checkpoint created”类结果，并没有真正调用 CheckpointStore：

[`core/engine/tool/checkpoint.go`](/Users/zhangqi.huang/GolandProjects/afra-agent/core/engine/tool/checkpoint.go:42)

同时，TaskManager 的自动 checkpoint 又写入 RunLog 对应的 JSON 文件：

[`core/engine/task_manager.go`](/Users/zhangqi.huang/GolandProjects/afra-agent/core/engine/task_manager.go:536)

而 Facade 的 `GetCheckpoints` 查询的是 SQLite CheckpointStore：

[`core/facade/agent_core.go`](/Users/zhangqi.huang/GolandProjects/afra-agent/core/facade/agent_core.go:843)

这意味着“工具返回 checkpoint 已创建”“自动 checkpoint 文件存在”“API 查询到 checkpoint”可能不是同一条持久化链路。建议优先统一 checkpoint 的唯一写入协议，并明确：

- 工具手动 checkpoint 是否写 SQLite。
- 自动 checkpoint 是否也写同一 Store。
- JSONL 是否只是恢复日志，而不是第二个 checkpoint 真相源。
- UI/API 查询能否看到所有 checkpoint。

这是当前最值得优先确认和修复的正确性问题。

### 9.2 `update_plan` 不是独立的持久化计划实体

`update_plan` 工具当前主要返回“plan updated”结果：

[`core/engine/tool/plan.go`](/Users/zhangqi.huang/GolandProjects/afra-agent/core/engine/tool/plan.go:54)

计划内容更多依赖消息、日志、压缩上下文或 checkpoint 中的内容，而不是独立的 PlanStore/Task Plan 状态。这样会带来：

- UI 读取计划需要从执行记录中推断。
- 恢复时计划可能与当前 Run 状态不一致。
- 多个 Run 修改同一 Task 计划时缺少明确的版本语义。
- 计划更新无法像图 State 一样产生结构化状态变更事件。

如果产品需要持续展示和恢复计划，建议将 Plan 作为 Task 级实体或至少作为带版本的 Run 状态来持久化。

### 9.3 `Planner` 目前是接口存在，但未形成实际规划链路

[`core/engine/planner.go`](/Users/zhangqi.huang/GolandProjects/afra-agent/core/engine/planner.go:5)

当前 Planner 更像扩展点，尚未成为默认执行路径中的可观察节点。这会导致“规划”这一概念同时存在于：

- `update_plan` 工具。
- Compactor 的计划保留。
- prompt 对 Agent 的要求。
- Planner 接口。

但它们之间缺少统一生命周期。如果未来引入 Graph，Planner 可以自然成为显式节点；在此之前也应明确其接口是否保留、由谁实现、生成的 Plan 保存在哪里。

### 9.4 Agent 级 Memory Scope 实际可能退化为 Run 级

Memory 工具有 scope 解析逻辑：

[`core/engine/tool/memory.go`](/Users/zhangqi.huang/GolandProjects/afra-agent/core/engine/tool/memory.go:269)

其中 `agent` scope 当前需要重点核对是否使用稳定的 AgentID。如果实际回退为当前 RunID，那么名义上的 Agent 记忆会变成一次 Run 内记忆，无法跨 Task/Run 复用。

建议明确以下 scope：

```text
user:{user_id}
workspace:{workspace_id}
agent:{agent_id}
task:{task_id}
run:{run_id}
```

并在数据结构中保存 scope 类型、scope id、来源 Run、更新时间和置信度。

### 9.5 `TriggerSource` 已存在，但触发器运行时尚未闭环

类型层存在触发来源概念，但 `CreateTaskWithOptions` 当前仍将来源硬编码为 `manual`：

[`core/facade/agent_core.go`](/Users/zhangqi.huang/GolandProjects/afra-agent/core/facade/agent_core.go:371)

这表明 Automation 的产品模型已经在设计中，但 scheduler、webhook、IM、告警和事件触发到 Task/Run 的实际连接还没有在当前 Core 中闭环。需要将其与 LangGraph 对比时区分：

- LangGraph 也不是完整的 Automation 平台。
- Afra 的 Automation 是产品目标，但当前 Core 还没有完成触发入口。

## 10. 建议的演进方案

### 10.1 保留 Afra 产品层，增加可选 Graph 层

推荐的目标分层：

```text
产品层
  Task / Run / Workspace / Approval / Attachment / Event / Usage
       │
运行时层
  AgentLoop / TaskManager / SafetyEngine / ToolSelector / Compactor
       │
编排层（新增，可选）
  Graph / State / Node / Edge / Reducer / Interrupt / Retry / Stream
       │
叶子层
  LLM Provider / Tool / MCP / External Agent / Store
```

默认 Agent 仍然可以使用当前固定循环，但它在内部表达为一个系统图：

```text
build_context
  → call_model
      ├── final_response → finish
      ├── ask_user → interrupt
      ├── approval_required → approval_interrupt
      ├── delegate → child_run
      └── tool_calls → execute_tools → call_model
```

这样既能保持现有产品行为，又能让复杂基础设施流程以显式图的方式扩展。

### 10.2 P0：优先补齐执行正确性和图基础

建议优先级如下：

1. 统一 Checkpoint：单一 Store、唯一 ID、父子关系、当前 next、metadata、恢复协议。
2. 建立最小 Graph State：Typed State、State Update、Reducer、Node、Edge。
3. 支持顺序图和条件图，先不引入全部高级特性。
4. 增加节点级 RetryPolicy、Timeout 和错误分类。
5. 将 `ask_user` 和 Approval 统一到 Interrupt/Resume 协议。
6. 将 LLM token、Tool Call、Tool Result、Node Update 接入统一流式事件。
7. 为多节点只读调查增加受控并行和结果聚合。

### 10.3 P1：增强长期可维护性

1. Memory namespace 和语义检索扩展点。
2. Graph Definition、Version 和迁移策略。
3. 节点级缓存和幂等执行键。
4. `get_state`、`get_state_history`、`update_state`、replay、fork、time travel API。
5. Graph/Node 的局部测试和状态契约测试。
6. 事件中补充 graph/node/checkpoint/step 维度。
7. 将 Plan 从 Tool Result 提升为结构化、可版本化的 Task 状态。

### 10.4 不建议的方向

不建议直接把 Afra 的 Task/Run 替换为 LangGraph Thread，也不建议让 LangGraph 的 Graph State 取代 Approval、SafetyEngine、Workspace、EventStore 和 Child Run。原因是：

- Thread 不是完整的产品 Task。
- Checkpoint 不是审批、审计和安全策略。
- Graph Node 不是具有风险和幂等语义的 Tool。
- 图执行器不会自动提供基础设施操作的回滚和安全边界。
- Afra 的产品域需求已经超出通用图运行时的职责。

正确的组合方式是把 LangGraph 中值得借鉴的执行能力吸收到 Afra 的编排层，而不是替换 Afra 的产品运行时。

## 11. 最终判断

### Afra 当前更强的地方

- 面向基础设施工作的产品化执行闭环。
- Task/Run/Workspace 生命周期。
- Tool 风险、幂等性、审批和沙箱。
- 文件、Shell、Git、Web、MCP、外部 Agent 等开箱工具。
- Agent、Skill、MCP、Provider、Model 管理。
- Child Run、委派配额、取消和审计。
- 面向长上下文 Agent 的压缩和工作区保留。
- 产品事件、用量、效率和前端时间线。

### LangGraph 当前更强的地方

- 通用 Graph/Node/Edge 编排。
- Typed State、Reducer、条件路由。
- 动态 Send 和图级并行。
- 精确 checkpoint、pending writes 和状态恢复。
- 时间旅行、重放、分支和状态修改。
- 任意节点 interrupt/resume。
- 节点级 retry、timeout 和错误处理。
- 图级 streaming、debug 和状态更新。
- 子图组合和工作流复用。

### 结论

Afra 当前不是“缺少一个 LangGraph 包装层”，而是“产品运行时已经完成一部分，但通用编排层还不完整”。如果目标是基础设施 Agent 产品，Afra 现有安全、审批、Task/Run 和工具体系应继续保留；如果目标是支持复杂、可复用、可并行、可回放的 Agent 工作流，则需要补充 Graph State、Node/Edge、精确 Checkpoint、Interrupt、Retry 和 Streaming。

最合理的架构定位是：

> Afra = 面向基础设施工作的产品级 Agent Runtime；
> Agent Graph = Afra Runtime 内可选的通用流程编排内核。

## 12. Claude Code `queryEngine` 的真实实现

### 12.1 分析口径

Claude Code 源码中没有一个必须单独命名为 `queryEngine` 的类；本报告将以下代码组合视为 queryEngine：

- [`src/query.ts`](/Users/zhangqi.huang/GolandProjects/cc-haha/src/query.ts:219)：`query()`、`queryLoop()` 和主循环状态。
- [`src/query/`](/Users/zhangqi.huang/GolandProjects/cc-haha/src/query)：Query 配置、依赖、停止 Hook、预算和状态转换辅助逻辑。
- [`src/services/tools/StreamingToolExecutor.ts`](/Users/zhangqi.huang/GolandProjects/cc-haha/src/services/tools/StreamingToolExecutor.ts:40)：流式 Tool 执行器。
- [`src/services/tools/toolOrchestration.ts`](/Users/zhangqi.huang/GolandProjects/cc-haha/src/services/tools/toolOrchestration.ts:16)：工具批次划分、只读并发和写操作串行调度。
- [`src/services/tools/toolExecution.ts`](/Users/zhangqi.huang/GolandProjects/cc-haha/src/services/tools/toolExecution.ts:337)：单个 Tool 的参数校验、权限、Hook、执行和结果流。

因此，Claude Code 的 queryEngine 是“查询循环 + Tool 执行管线 + Context 管理 + Session/Permission 周边”的组合，而不是单个函数文件。

### 12.2 主循环：AsyncGenerator 驱动的状态机

Claude Code 的主入口是异步生成器：

```text
query(params)
  └── queryLoop(params)
      └── while (true)
          ├── 读取本轮 State
          ├── 预处理消息和上下文
          ├── 流式调用 Claude API
          ├── 发现 tool_use 后即时进入 Tool Executor
          ├── 流式产出 Tool Result
          ├── 处理 fallback / abort / compact / stop hook
          └── 有 tool_use：继续下一轮；无 tool_use：结束
```

`queryLoop` 维护一个显式的循环 State，包含：

- 当前 `messages`。
- `toolUseContext`。
- 自动压缩跟踪。
- 最大输出 token 恢复次数。
- Reactive Compact 是否已经尝试。
- 当前 turn count。
- 待生成的 Tool Use Summary。
- 当前 transition/recovery 原因。

主循环位于 [`src/query.ts`](/Users/zhangqi.huang/GolandProjects/cc-haha/src/query.ts:241)，`while (true)` 位于 [`src/query.ts`](/Users/zhangqi.huang/GolandProjects/cc-haha/src/query.ts:307)。这比 Afra 当前把一部分状态分散到 Run、MessageStore、RunLog、Event 和工具上下文中更集中，但仍然是固定循环 State，不是可声明的 Graph State。

### 12.3 Claude API 流式输出与 Tool Use 的紧耦合

Claude Code 调用的是流式模型接口 `queryModelWithStreaming`。模型消息尚未完全结束时，只要流中出现 `tool_use` block，就会把 Tool 加入 `StreamingToolExecutor`：

```text
Claude streaming response
  ├── text / thinking block → 立即向 UI 产出
  ├── tool_use block → 加入 StreamingToolExecutor
  └── Tool Result 完成 → 立即产出 user/tool_result message
```

相关路径见 [`src/query.ts`](/Users/zhangqi.huang/GolandProjects/cc-haha/src/query.ts:555) 和 [`src/query.ts`](/Users/zhangqi.huang/GolandProjects/cc-haha/src/query.ts:830)。这带来两个特点：

1. Tool 执行不必等整段模型响应完全结束。
2. UI 可以同时看到模型流、Tool 进度和 Tool Result。

Afra 当前 `llm.Provider` 的核心是同步 `Chat`，AgentLoop 通常在模型调用完成后再处理 Tool Calls。因此在端到端实时性上，Claude Code queryEngine 明显领先于 Afra 当前实现。

### 12.4 Tool 执行：基于安全属性的受控并发

Claude Code 并不是简单地把所有 Tool Calls 串行执行，也不是把所有 Tool Calls 无条件并行执行。它先根据 Tool 的 `isConcurrencySafe(input)` 判断，把连续 Tool Calls 划分为批次：

```text
只读/并发安全 Tool 1 ─┐
只读/并发安全 Tool 2 ─┼─ 并发执行，受最大并发数限制
只读/并发安全 Tool 3 ─┘

写操作 Tool A → 串行执行
写操作 Tool B → 串行执行
```

核心实现位于 [`src/services/tools/toolOrchestration.ts`](/Users/zhangqi.huang/GolandProjects/cc-haha/src/services/tools/toolOrchestration.ts:64)。默认最大 Tool 并发数来自 `CLAUDE_CODE_MAX_TOOL_USE_CONCURRENCY`，默认值为 10。

在流式模式下，[`StreamingToolExecutor`](/Users/zhangqi.huang/GolandProjects/cc-haha/src/services/tools/StreamingToolExecutor.ts:40) 还负责：

- Tool 到达时立即排队和启动。
- 非并发安全 Tool 独占执行。
- 结果按 Tool 接收顺序向外发出，避免 UI 和 transcript 顺序漂移。
- Tool 进度单独缓冲并及时产出。
- 用户中断时按 Tool 的 `interruptBehavior` 决定取消还是阻塞。
- Bash Tool 出错时取消同批次的兄弟 Tool。
- 中断、fallback 或兄弟错误时生成 synthetic `tool_result`，保持 API 消息配对完整。

这是一种“Tool 级调度器”，不是 LangGraph 的“节点级调度器”。它解决的是同一模型响应内的工具执行效率和副作用隔离，而不是任意业务节点的 fan-out/fan-in。

### 12.5 Tool 结果不是普通字符串，而是完整消息协议

Claude Code 非常重视 Anthropic Tool Use 消息的结构合法性：

- `tool_use` 与 `tool_result` 必须通过 `tool_use_id` 配对。
- thinking block、tool_use block 和后续 tool_result 的顺序不能随意改写。
- 模型 fallback 时要丢弃旧请求产生的 orphan Tool Result。
- 运行时错误、用户中断和取消也要生成合规的 synthetic Tool Result。
- 工具结果可能包含图片、文档、进度和内容替换记录。

这使 queryEngine 更像“协议驱动的消息状态机”。Afra 也会保存 Tool Call/Tool Result，但当前重点是 Run 恢复和产品事件；尚未在 Provider 层建立同等严格的流式消息配对和 fallback 重放协议。

### 12.6 Query 级恢复和错误处理

Claude Code 的 queryEngine 包含多层恢复：

| 场景 | 当前处理方式 |
|---|---|
| 模型主请求失败 | 可切换 fallback model，清理失败请求产生的 assistant/tool 消息 |
| thinking 签名与 fallback 模型不兼容 | 在重试前移除不兼容的 signature block |
| max output tokens | 升级输出上限或注入 continuation，避免直接终止 |
| prompt too long | 先尝试 context collapse，再 reactive compact，再暴露错误 |
| 媒体过大 | 触发媒体恢复/剥离后重试 |
| 用户中断 | 取消可取消 Tool，并为剩余 Tool 生成 synthetic result |
| Bash 兄弟 Tool 失败 | 取消同批次剩余 Tool，避免继续执行隐含依赖链 |
| Tool 返回错误 | 把错误回填给模型，由下一轮决定是否继续 |

这些逻辑集中在 `query.ts` 的状态转换和 `StreamingToolExecutor` 的 abort 传播中。Afra 当前有 Run 级恢复、存储错误重试和安全拒绝，但还没有这么完整的“模型请求失败 → 清理消息 → fallback → 继续同一轮”的协议化路径。

### 12.7 Subagent：复用同一 query loop，而不是另一种执行引擎

Claude Code 的 AgentTool 会选择一个 Agent Definition，然后通过 `runAgent()` 创建子 Agent 的 `ToolUseContext`，最后再次调用同一个 `query()`：

```text
主 query()
  → Agent Tool
      → AgentTool 选择 Agent Definition
      → runAgent()
          → 创建 child ToolUseContext
          → 配置 child tools / prompt / permission / cwd
          → 再次 query()
```

`runAgent()` 调用 query 的位置见 [`src/tools/AgentTool/runAgent.ts`](/Users/zhangqi.huang/GolandProjects/cc-haha/src/tools/AgentTool/runAgent.ts:748)，入口选择 Fork 或显式 Agent Definition 的逻辑见 [`src/tools/AgentTool/AgentTool.tsx`](/Users/zhangqi.huang/GolandProjects/cc-haha/src/tools/AgentTool/AgentTool.tsx:318)。

Claude Code 至少区分两类子 Agent：

- Fresh/显式 Agent：使用自己的 prompt、工具、模型和权限模式，默认不继承完整主对话。
- Fork Agent：复用父对话消息、父 system prompt、精确 Tool 集和 thinking 配置，以保持 prompt cache 前缀一致。

此外还有：

- 同步子 Agent。
- 后台/异步子 Agent。
- worktree 隔离。
- resume 子 Agent。
- teammate / mailbox 协作路径。

这与 Afra Child Run 的差异是：Claude Code 的子 Agent 仍主要是同一查询引擎的上下文派生；Afra 的 Child Run 是 Task/Run 产品实体，强调父子生命周期、事件、配额、取消和审计。

### 12.8 Session Resume、Rewind 与 File Checkpoint

Claude Code 没有 LangGraph 那种通用 graph checkpoint，但有成熟的 Session/Transcript 恢复体系：

- Session transcript 保存消息和运行元数据。
- `--resume`、`--continue` 和 `/resume` 可以重新加载会话。
- 恢复时重新装载 Agent、工作目录、worktree、Todo、文件历史和 attribution。
- Session Rewind 按用户轮次选择目标，并可预览对话和文件变化。
- File History 保存文件备份，用于将代码恢复到指定轮次。

Session 状态恢复入口见 [`src/utils/sessionRestore.ts`](/Users/zhangqi.huang/GolandProjects/cc-haha/src/utils/sessionRestore.ts:96)，按轮次列出可恢复检查点见 [`src/server/services/sessionRewindService.ts`](/Users/zhangqi.huang/GolandProjects/cc-haha/src/server/services/sessionRewindService.ts:916)。

这比 Afra 当前的“Run Log + JSON checkpoint + SQLite CheckpointStore 分裂”更加完整地解决了编码会话恢复，但语义仍然不同：

- Claude Code 的 checkpoint 主要是“会话轮次 + 文件快照 + transcript rewind”。
- LangGraph 的 checkpoint 是“图执行步骤 + State + next + pending writes”。
- Afra 当前目标是“Run 恢复 + 事件审计”，但 checkpoint 真相源仍需统一。

### 12.9 上下文压缩和文件/计划恢复

Claude Code 的上下文工程比单纯的消息截断复杂，当前至少包含：

- Tool Result microcompact：优先清理可重新获取的旧工具结果。
- Full compact：使用专门的 summary agent 生成摘要。
- Partial compact：只压缩指定历史区段。
- Reactive compact：API 报 prompt too long 后再恢复。
- Context collapse：在不立即丢失全部细节的情况下逐级折叠上下文。
- Compaction boundary message：明确摘要覆盖的历史范围。
- 最近读取文件的恢复附件。
- Plan 文件恢复附件。
- Skill 和 plan mode 指令恢复。
- Session memory 摘要恢复。

说明：当前 `cc-haha` checkout 中的 `contextCollapse` 相关文件包含由扫描工具生成的 `__stubMissing` 占位实现，因此本报告能直接确认的是 `query.ts` 中的 feature gate、调用位置和恢复分支；context collapse 的完整算法实现不应仅依据这些占位文件判定为当前仓库已完整提供。

Full compact 主入口位于 [`src/services/compact/compact.ts`](/Users/zhangqi.huang/GolandProjects/cc-haha/src/services/compact/compact.ts:387)，文件恢复逻辑位于同文件的 [`createPostCompactFileAttachments`](/Users/zhangqi.huang/GolandProjects/cc-haha/src/services/compact/compact.ts:1399)，计划恢复逻辑位于 [`createPlanAttachmentIfNeeded`](/Users/zhangqi.huang/GolandProjects/cc-haha/src/services/compact/compact.ts:1467)。

Afra 的 Compactor 已经具备两阶段摘要、计划和文件清单保留，设计方向相近；Claude Code 的差异在于它把压缩、缓存编辑、API 错误恢复、消息协议修复和 session 文件恢复组合成了完整的交互式编码会话策略。

### 12.10 Permission Hook 和 Tool-specific 安全判断

Claude Code 的权限不是一个简单的全局 allow/deny 开关，而是多层组合：

- Tool permission mode：例如 plan、acceptEdits、dontAsk、auto 等。
- 允许、拒绝、询问规则。
- Tool-specific 参数校验。
- Bash 命令和路径的安全分类。
- `PermissionRequest` Hook。
- 交互式 permission dialog。
- headless/async Agent 的 fail-closed 处理。
- 通过权限更新把本次决策持久化成规则。

`PermissionContext` 负责将 Hook、交互队列和 allow/deny/ask 决策组合起来，见 [`src/hooks/toolPermission/PermissionContext.ts`](/Users/zhangqi.huang/GolandProjects/cc-haha/src/hooks/toolPermission/PermissionContext.ts:96)；实际 Tool 执行前的权限检查位于 [`src/services/tools/toolExecution.ts`](/Users/zhangqi.huang/GolandProjects/cc-haha/src/services/tools/toolExecution.ts:916)。

Afra 的 SafetyEngine 更强调风险等级、幂等性、外部副作用、ApprovalStore 和 OS 沙箱；Claude Code 更强调交互式 CLI 的权限规则、Hook、路径检查和 Tool-specific 安全策略。两者都强于 LangGraph Core，但安全边界的承载方式不同。

## 13. Afra、Claude Code queryEngine、LangGraph 三方矩阵

| 维度 | Afra Agent Core | Claude Code queryEngine | LangGraph |
|---|---|---|---|
| 顶层定位 | 基础设施 Agent 产品 Runtime | 交互式编码 Agent 的查询引擎 | 通用有向图执行框架 |
| 主入口 | AgentCore / TaskManager / AgentLoop | `query()` → `queryLoop()` | `StateGraph.compile()` 后 invoke/stream |
| 主循环 | Run 级固定 model-tool loop | AsyncGenerator + `while(true)` | 由 Node/Edge 调度，不要求固定 loop |
| 控制流 | LLM Tool Call、审批、问答、委派 | LLM Tool Use、stop hook、compact、fallback | Edge、conditional edge、Command、Send |
| 状态载体 | Task、Run、Message、ToolUseContext、Store | `queryLoop` State、messages、ToolUseContext、session state | 类型化 State、Reducer、Checkpoint |
| 状态更新 | 工具结果、消息、Run/Event 持久化 | context modifier、message/tool_result、session 文件 | 节点返回 State update，Reducer 归并 |
| Tool 调度 | 当前主要顺序执行 | 只读并发，写操作串行；支持流式到达 | Tool 常被建模为 Node，可图级并行 |
| 并发边界 | Task/Child Run 级编排，Tool 默认保守 | `isConcurrencySafe(input)` + 最大并发数 | super-step 节点并行、Send fan-out |
| 流式 | Provider 当前同步 Chat，事件投影为主 | 模型、Tool、进度、结果全链路流式 | messages、updates、values、custom、debug 等 stream mode |
| Tool 协议 | Tool interface + Tool Result | Anthropic 原生 `tool_use/tool_result` 严格配对 | 由应用节点和消息 State 决定 |
| Tool 错误 | 反馈到 AgentLoop，Run 级恢复 | synthetic result、兄弟取消、fallback 清理 | 节点错误、RetryPolicy、错误处理节点 |
| 模型 fallback | Provider/Model 选择，但 query 级 fallback 较弱 | query 内清理旧响应后切换模型重试 | 通常由节点或应用策略实现 |
| 人工介入 | `ask_user`、ApprovalStore、waiting 状态 | permission dialog、Hook、abort、Tool interrupt behavior | 任意节点 `interrupt()` + `Command(resume)` |
| 审批编辑 | 风险审批主要批准/拒绝 | Permission Rule/Hook，可修改规则和部分 Tool 输入 | 应用/HITL 层可实现 approve/edit/reject |
| 子 Agent | Child Run，父子事件、配额、取消 | Fresh/Fork/Async/Worktree/Teammate，复用同一 query loop | Subgraph、Send、Command、handoff |
| Session 恢复 | Run Log、JSONL、Checkpoint、ContinueRun | transcript resume、file checkpoint、turn rewind、worktree restore | thread checkpoint、state history、replay/fork |
| Checkpoint | 当前存在 SQLite 与 JSON 文件两条路径，需统一 | session/turn/file checkpoint，不是 graph checkpoint | 图状态快照，带 next、metadata、pending writes |
| 时间旅行 | 当前不完整 | 支持会话轮次 rewind 和文件恢复 | 原生 checkpoint history/time travel |
| 上下文压缩 | 两阶段 summary、计划/文件清单保留 | microcompact、full/partial/reactive compact、collapse、缓存编辑 | 通常由应用节点实现摘要或裁剪 |
| 长期记忆 | SQLite Key/Value，当前主要关键词检索 | CLAUDE.md、session memory、agent memory 文件 | Store namespace，可接语义检索 |
| 权限/安全 | SafetyEngine、风险、幂等性、Approval、沙箱、凭据过滤 | Permission mode/rules/hooks、Bash/path validation、sandbox/worktree | Core 不等价提供 OS 安全边界 |
| 产品实体 | Task、Run、Workspace、Event、Usage、Agent Catalog | Session、Agent Definition、Task、Transcript、CLI/UI State | Thread/Run 及平台外围能力 |
| 管理能力 | Agent、Skill、MCP、Provider、Model Catalog | Agent、Skill、MCP、settings、permission rules | 主要依赖应用或 LangGraph Platform |
| 适合场景 | 长时间基础设施调查、执行、审批、审计 | 本地/远程代码库交互式开发 | 可复用、可回放、可并行的复杂工作流 |

### 13.1 三者的相对关系

```text
                         通用流程编排能力
                                ↑
                                │ LangGraph
                                │
            Claude Code         │        Afra
        流式查询/Tool 调度       │    产品生命周期/安全
                                │
                                └──────────────→ 产品化运行时能力
```

这不是严格的能力评分图，而是设计中心示意：

- LangGraph 最靠近通用流程编排。
- Claude Code 最靠近交互式、流式、工具驱动的编码 Agent。
- Afra 最靠近基础设施工作的产品级任务运行时。

Claude Code 与 Afra 的 AgentLoop 形态比它们与 LangGraph 更接近；Claude Code 在查询循环的实时流、Tool 调度和会话恢复上更成熟，Afra 在后端产品实体、安全审批、Workspace、审计和跨入口运行上更完整。

## 14. 同类功能的三方实现差异

### 14.1 Model → Tool → Model

Afra：

```text
AgentLoop.Run(Run)
  → Provider.Chat
  → 解析 Tool Calls
  → SafetyEngine / Approval
  → Tool.Execute
  → 写 Message/Event
  → 下一次 Chat
```

Claude Code：

```text
queryLoop(State)
  → queryModelWithStreaming
  → 流中发现 tool_use
  → StreamingToolExecutor.addTool
  → Tool Result 以消息形式流出
  → while(true) 下一轮 API 请求
```

LangGraph：

```text
call_model Node
  ├── no tool call → END
  └── tool call → tool_node
                    → conditional edge
                    → call_model / approval / aggregate
```

结论：Afra 和 Claude Code 都是模型驱动的固定循环，Claude Code 更实时、更强调消息协议和并发；LangGraph 把循环拆成可组合节点，控制流可编程性最高。

### 14.2 并发执行

Claude Code 的并发已经落在 Tool 执行层：只读工具可以并发，写工具独占，Bash 错误会触发兄弟取消，并保持结果顺序。

Afra 当前多 Tool Calls 默认顺序执行，安全语义更简单，但在只读调查场景会损失吞吐。Afra 的 Child Run 可以做任务级并行，但它不是同一个模型响应内 Tool Calls 的高效调度器。

LangGraph 的并发是图节点调度层能力：多个可执行节点进入同一 super-step，结果通过 Reducer 合并；动态 fan-out 通过 Send 实现。

三者的层级不同：

- Claude Code：Tool-level concurrency。
- Afra 当前：Run/Child Run-level orchestration，Tool-level 保守串行。
- LangGraph：Node/super-step-level concurrency。

Afra 最适合借鉴 Claude Code 的第一步，而不是直接照搬 LangGraph 的任意节点并行：先给 Tool 增加 `ConcurrencySafe(input)` 和 `InterruptBehavior()`，对只读、无外部副作用操作做受控并发；写操作仍交由 SafetyEngine 和 Approval 串行保护。

### 14.3 中断、权限与审批

Claude Code 的中断多数发生在 Tool 执行或 Permission 阶段：用户按键、权限拒绝、Hook 决策、工具自身的 interrupt behavior 会影响当前 Tool 是否取消，并通过 synthetic `tool_result` 告知模型。

Afra 的中断更多表现为 Run 状态变化：`waiting_for_input` 或 `waiting_for_approval`，之后通过 Continue/Resume 继续 AgentLoop。这个模型更适合后端持久化和跨设备审批，但需要把中断 payload、恢复点和待执行动作做得更结构化。

LangGraph 的 interrupt 是通用程序级暂停：节点执行到任意位置可以把结构化值交给外部，恢复时由 `Command(resume)` 回填。

推荐的组合方式：

```text
SafetyEngine 判定高风险
  → 生成统一 Interrupt(kind=approval, payload=tool/input/risk)
  → ApprovalStore 持久化
  → Run waiting_for_approval
  → 外部批准/拒绝/编辑
  → Resume Command
  → 继续当前 Tool/Node
```

这里应吸收 Claude Code 的 Tool-specific permission 和 Hook，也应吸收 LangGraph 的通用 Interrupt/Resume，但不应丢掉 Afra 的 ApprovalStore 和审计语义。

### 14.4 子 Agent 与上下文隔离

Claude Code 的 Fresh/Fork 区分很有价值：

- Fresh 子 Agent 只获得目标 prompt 和自己的 system/tools，适合隔离上下文和控制 token 成本。
- Fork 子 Agent 继承父消息、system prompt、Tool 集和 thinking 配置，适合缓存命中和需要上下文的分支。

Afra 当前 `delegate` 以 Child Run 为中心，具有更清晰的父子任务、事件、深度和取消语义，但还没有把“Fresh Context / Fork Context / Cache-preserving Context”作为显式委派策略暴露出来。

LangGraph Subgraph 则重点解决子图的状态 namespace、持久化模式和父图组合。三者对应关系是：

| 问题 | Afra | Claude Code | LangGraph |
|---|---|---|---|
| 谁创建了子执行 | Child Run | AgentTool / Task / Teammate | Parent graph node / Send |
| 上下文隔离 | Run/Agent 配置 | Fresh/Fork、消息和 Tool 克隆 | Subgraph state namespace |
| 执行引擎 | AgentLoop | 同一个 `query()` | 子图执行器 |
| 取消/审计 | 产品级父子 Run | abort、任务状态、mailbox | 图状态和应用层任务管理 |
| 缓存优化 | 当前未形成专门 Fork cache 语义 | Fork 保持 prompt prefix 和 Tool defs | 由应用/模型调用层处理 |

### 14.5 Context Compaction

Afra 和 Claude Code 都已经超越了简单的“截断最早消息”：

- Afra 强调保留任务目标、计划、文件清单和不可重复的非幂等结果。
- Claude Code 强调 Tool Result microcompact、full/partial/reactive compact、context collapse、prompt cache 编辑、最近文件恢复和 plan/session memory 附件。

LangGraph 的原生定位是保存 State，不替应用决定如何压缩对话或工具结果。要实现同等效果，通常需要在图中显式添加 summarizer、message deletion 或 context manager 节点。

Claude Code 对 Afra 的直接借鉴点是把压缩从 Compactor 单体能力进一步拆为可组合阶段：

```text
Tool result budget
  → microcompact
  → context collapse
  → full summary
  → post-compact file/plan/skill restore
  → API retry
```

### 14.6 恢复和“Checkpoint”语义

三个系统都使用了“恢复”或“checkpoint”相关概念，但不能混为一谈：

| 系统 | 恢复对象 | 恢复粒度 | 是否是通用图状态 |
|---|---|---|---|
| Afra | Run 消息、工具结果、计划、日志和部分 checkpoint | Run/执行轮次 | 否，当前尚未统一 |
| Claude Code | Session transcript、用户轮次、文件快照、worktree | Session turn / 文件历史 | 否 |
| LangGraph | State、next、metadata、pending writes、父 checkpoint | Graph super-step | 是 |

Claude Code 的 Session Rewind 在编码体验上比当前 Afra 更完整，因为它把 transcript 和文件历史联系起来；但它不等于 LangGraph 的 `get_state_history`，也不能直接恢复任意业务节点的结构化 State。

Afra 当前最紧迫的问题仍是第 9.1 节的 checkpoint 写入/读取分裂；Claude Code 的实现说明，用户可见的“恢复点”必须同时覆盖对话、工具结果和外部文件状态，而不能只写一条标记事件。

## 15. Afra 可以直接借鉴 Claude Code queryEngine 的能力

在不改变 Afra 产品定位的前提下，以下能力比完整引入 LangGraph 更适合优先吸收：

### P0：实时 Tool 执行和消息协议

1. 将 `llm.Provider.Chat` 扩展为可选 Streaming API，同时保留同步适配器。
2. 在 AgentLoop 中流式识别 Tool Call，支持 Tool 进度事件。
3. 为 Tool Result 建立稳定的 `tool_call_id` 配对和 synthetic result 协议。
4. 在 fallback、cancel、approval reject、tool error 时保证消息序列合法。
5. 将模型 token、Tool Call、Tool Result、Approval 和 Run 状态统一投影到事件流。

### P0：只读并发、写操作串行

1. 为 Tool 增加基于输入的并发安全判定。
2. 只允许明确无副作用的读操作进入并发批次。
3. 非幂等写操作、审批中的操作和可能修改工作区的 Shell 保持独占。
4. 增加最大并发数、兄弟错误取消和可配置的中断行为。
5. 结果按调用顺序归并，避免前端时间线和模型消息乱序。

### P1：模型 fallback 和上下文恢复

1. 失败请求生成可识别的 tombstone/synthetic result。
2. 切换模型时清理模型绑定的 thinking/signature 数据。
3. 对 max output token、prompt too long、媒体过大等错误提供分阶段恢复。
4. 把 Compactor 拆分成 microcompact、summary、post-compact restore 和 retry 几个可验证阶段。
5. 在恢复时补充最近文件、Plan 和等待中的 Child Run 状态。

### P1：Fresh/Fork 委派模式

在现有 Child Run 上增加显式的上下文策略：

```text
delegate(mode=fresh)
  → 只传目标、必要能力和最小上下文

delegate(mode=fork)
  → 继承父 Run 的消息、system prompt、工具和关键上下文

delegate(mode=background)
  → 独立生命周期、持久化状态、异步通知和可恢复结果
```

这可以结合 Afra 已有的委派深度、数量、取消和事件审计，而不必把 Child Run 改成 LangGraph Subgraph。

## 16. 三方最终判断

### Afra 与 Claude Code 的相同点

- 都是模型原生 Tool Calling 驱动的广义 ReAct loop，而不是教学式 `Thought/Action/Observation` 文本协议。
- 都把 Tool Result 回填到消息，再触发下一轮模型调用。
- 都支持多轮工具执行、上下文压缩、权限控制和子 Agent。
- 默认路径都不是通用 Graph，没有用户可声明的 Node/Edge/Reducer 体系。

### Claude Code 相比 Afra 更强的地方

- API、模型输出和 Tool 执行的全链路流式化。
- 只读 Tool 并发、写操作串行和兄弟错误取消。
- query 内模型 fallback、max output recovery 和消息清理。
- Anthropic `tool_use/tool_result` 协议约束更严密。
- 交互式 Permission Hook、规则持久化和 Tool-specific Bash/path 安全。
- Session resume、turn rewind、file checkpoint 和 worktree 恢复更成熟。
- Fresh/Fork 子 Agent 上下文策略和 prompt cache 优化更细。
- microcompact、reactive compact、context collapse 和 post-compact restore 更完整。

### Afra 相比 Claude Code 更强的地方

- Task/Run/Workspace 是后端持久化产品实体，不依赖单机 CLI 会话。
- Approval、SafetyEngine、风险、幂等性、外部副作用和审批记忆是独立领域模型。
- EventStore、Usage、Efficiency 和 Workspace 时间线面向跨客户端产品审计。
- Agent、Skill、MCP、Provider、Model Catalog 是统一的管理域。
- Child Run 是可跨轮次、可持久化、可取消、可追踪的任务实体。
- REST、CLI、TUI、桌面端可以复用同一 Core，而不是围绕单一交互式 CLI 状态组织。
- 更明确地面向基础设施调查、执行、验证、回滚和审计闭环。

### LangGraph 相比两者更强的地方

- Graph/Node/Edge 是显式的一等抽象。
- State、Reducer、Command、Send 和 super-step 提供通用编排能力。
- Checkpoint 是图状态真相源，可支持历史、重放、分支和 pending writes。
- 节点级 RetryPolicy、Timeout、Interrupt 和图级 Streaming 更容易组合。
- 子图是流程复用的正式机制，而不是仅通过递归调用同一个 Agent Loop。

### 最终定位

三者不是简单的替代关系：

```text
Claude Code queryEngine：成熟的交互式 Tool-calling 查询循环
Afra Agent Core：面向基础设施工作的产品级 Agent Runtime
LangGraph：通用的 State Graph 编排和恢复内核
```

对 Afra 最合适的路线仍然是：

1. 从 Claude Code 借鉴流式 Tool 执行、受控并发、fallback、权限 Hook 和 session 恢复细节。
2. 从 LangGraph 借鉴 Graph State、Node/Edge、Reducer、Interrupt/Resume、节点级 Retry 和精确 Checkpoint。
3. 保留 Afra 自己的 Task、Run、Workspace、Approval、SafetyEngine、EventStore、Child Run 和管理目录。

换句话说，Afra 不应变成 Claude Code 的 CLI 会话，也不应简单包一层 LangGraph；它应该把两者中适合基础设施场景的执行能力，沉淀到自己的产品级 Agent Runtime 中。
