# Stock Analysis Debate Skill 优化思路与失败复盘

## 1. 背景

本轮优化起因是对一份 AMD 分析报告的质量审查。报告暴露出若干分析质量问题：

- 证据来源层级不清，新闻、分析师观点和一手披露混用。
- 社交情绪数据缺失时仍可能生成看似精确的统计结论。
- Forward EPS、Forward PE、目标价等指标存在期间或 GAAP / Non-GAAP 口径不明的问题。
- 辩论中的多方一致容易被误当成独立证据。
- 仓位、止损、Kelly、VaR 等计算缺少统一的确定性验算。
- 证据不足时仍倾向于强制输出方向性评级。

优化目标原本是提高最终报告的证据质量、计算可靠性和决策边界，同时保留原有七个 Phase、工具路径、Prompt 和文件产物。

## 2. 本轮采用的修改思路

本轮修改主要包含以下方向：

1. 在 Phase 1 与 Phase 2 之间增加证据质量闸门，生成 `evidence_ledger.md`。
2. 要求分析师区分已验证事实、推断和假设，禁止合成不存在的社交数据。
3. 将 Phase 2 调整为“四个基础分析师完成并落盘后，再调用 Segment Analyst”。
4. 强化 `phase2_analyst_reports.md` 的写入、回读和章节完整性校验。
5. 给 Research Manager、Trader、Risk Debate 和最终报告增加证据充分性与确定性计算规则。
6. 增加 `Not Rated`，用于关键证据缺失、过期、语义不明或相互冲突的情况。
7. 将最终报告改成更简洁的决策报告，并把完整辩论保留在独立 artifact 中。

这些方向本身针对的是报告质量问题，但实施时错误地把“分析质量增强”和“编排协议重构”放在了同一次修改中。

## 3. 为什么修改后流程跑不下去

### 3.1 修改范围过大

`SKILL.md` 既是分析规范，也是运行时编排协议。本轮同时改变了：

- Phase 之间的依赖关系；
- Agent 的并行与串行方式；
- 主会话与 sub-agent 的文件读写职责；
- 新增文件及其前置校验；
- 各阶段的输入上下文；
- 最终评级和报告结构。

任何一处解释偏差都可能阻塞后续 Phase。把这些变化一次性加入自然语言工作流，缺少足够的隔离与回归验证。

### 3.2 Phase 2 的运行协议被改写

原流程强调在单个消息中并行创建分析师，并在分析师返回后写入 `phase2_analyst_reports.md`。本轮先把 Segment Analyst 从并行调用中拆出，又增加了：

1. 收集四个 Agent 的完整返回；
2. 主会话写文件；
3. 主会话回读文件；
4. 校验四个标题；
5. 失败时重试；
6. 再创建 Segment Analyst；
7. 再次读、重写和校验文件。

这使 Phase 2 从一个较短的并行阶段变成了多次工具调用与状态判断组成的事务。自然语言 Agent 对“Agent 返回值、文件写入结果、回读结果、下一次 Agent 调用”的状态保持并不稳定，因此补充更多强制规则并没有修复根因，反而增加了阻塞点。

### 3.3 新增的证据闸门成为全流程硬依赖

`evidence_ledger.md` 被加入几乎所有后续 Agent 的必需输入，但 Skill 没有一个确定性程序负责创建和校验它。只要主会话没有生成该文件、字段不完整，或外部检索无法完成，后续阶段就可能无法继续。

### 3.4 指令密度和局部冲突上升

同一份 Skill 中同时存在“减少主会话读取”“主会话必须回读校验”“Agent 自己处理文件”“主会话拥有文件”等不同职责描述。即使每条规则单独看合理，组合后仍会增加模型选择错误执行路径的概率。

### 3.5 缺少编排级测试

现有测试主要覆盖数据抓取和预处理工具，不能验证：

- 七个 Phase 是否按约定顺序执行；
- 哪些 Agent 应并行，哪些必须串行；
- Agent 调用参数是否包含正确的 Prompt 和数据路径；
- `phase2_analyst_reports.md` 是否在 Phase 3 前写入；
- 文件写入失败时是否阻止错误地进入下一阶段；
- Segment Analyst 的调用时点是否正确。

因此，静态 Skill 校验和工具单测都通过，仍无法发现真实运行时的编排回归。

## 4. 本次回滚范围

本次回滚恢复以下文件到本轮优化之前的版本：

- `skills/stock-analysis-debate/SKILL.md`
- 项目根目录 `README.md`

本复盘文档作为唯一新增产物保留。本次不修改 Prompt、数据抓取工具、分析产物或其他用户文件。

需要注意：回滚只恢复原有行为，不代表原流程不存在潜在问题。原版 Phase 2 中 Segment Analyst 的数据依赖与并行描述仍值得后续单独验证，但不应在没有编排测试的情况下直接重写。

## 5. 后续更安全的优化顺序

### 第一步：冻结现有工作流

先把当前七个 Phase、Agent 数量、并行边界、输入文件、输出文件和职责归属整理成可执行契约。在测试建立前，不改变 Phase 顺序和主会话 / sub-agent 的文件职责。

### 第二步：增加编排 Trace 校验

测试执行器记录所有关键事件，例如：

```text
tool.fetch_data
file.read:data_quality.json
agent.market
agent.news
agent.social
agent.fundamentals
file.write:phase2_analyst_reports.md
agent.bull:round_1
agent.bear:round_1
...
file.write:analysis_report.md
```

校验器应验证“偏序关系”，而不是强制所有事件完全顺序一致。例如四个基础分析师可以任意顺序完成，但必须全部发生在 `phase2_analyst_reports.md` 写入之前；Phase 3 必须发生在该文件写入之后。

### 第三步：校验工具和 Agent 调用参数

对每类调用定义最小参数契约：

- Prompt 文件必须是预期绝对路径；
- 数据文件必须与角色匹配；
- ticker、market、currency、current price 必须存在；
- Bull / Bear 必须包含 round、role、total rounds 和历史文件路径；
- Risk Agent 必须包含 trader plan、分析师报告和风险历史路径；
- Segment Analyst 必须取得约定的分部数据与 News 上下文；
- 文件写入目标必须是当前 ticker/date 目录。

测试中使用 fake tool、fake agent 和 fake file store 记录调用，不触发真实行情、网络或模型调用。

### 第四步：增加真实 Skill 的集成 Eval

单元测试只能保证确定性校验器和模拟编排器正确，不能保证模型每次都遵循 Markdown。还需要在隔离目录中运行真实 Skill，保存 JSONL Trace，并重复运行若干次统计成功率。

集成 Eval 至少覆盖：

1. US 多分部正常路径；
2. CN 跳过分部路径；
3. 分部数据抓取失败的降级路径；
4. 某个基础分析师返回空内容；
5. Phase 2 文件写入失败；
6. Phase 2 文件缺少某个分析师章节；
7. 中间 Agent 调用失败；
8. 最终报告未写入。

### 第五步：只做单点质量优化

测试可以捕获流程回归后，再逐项优化：

1. 先修复一个明确问题；
2. 保持 Phase 顺序、Agent 调用方式和文件协议不变；
3. 运行静态契约测试、Trace 单测和集成 Eval；
4. 验证稳定后再处理下一个问题。

证据质量、社交数据降级、估值口径和确定性计算更适合优先放入各角色 Prompt 或最终检查阶段，而不是先增加一个所有阶段都依赖的新 Phase。

## 6. 建议的最小测试结构

```text
skills/stock-analysis-debate/
├── SKILL.md
└── tools/
    ├── workflow_trace_validator.py
    └── tests/
        ├── fixtures/
        │   ├── us_multi_segment_success.jsonl
        │   ├── cn_success.jsonl
        │   └── phase2_missing_write.jsonl
        ├── test_skill_contract.py
        └── test_workflow_trace.py
```

- `test_skill_contract.py`：检查 Phase、Prompt、关键文件名和不可丢失的强制规则。
- `test_workflow_trace.py`：检查事件偏序、调用入参、输出文件和失败阻断。
- `workflow_trace_validator.py`：纯函数实现，不访问网络，不调用真实 Agent。

## 7. 后续修改的验收标准

任何再次修改该 Skill 的变更，至少应满足：

- 原有七个 Phase 没有被意外增加、删除或重排；
- 基础分析师和辩论 Agent 的调用数量符合预期；
- Phase 2 的完整报告在 Phase 3 前已写入；
- Agent 的 Prompt、数据路径和轮次参数正确；
- 任一关键文件缺失时产生明确失败，而不是静默跳阶段；
- CN、HK/US、多分部和降级分支都有覆盖；
- 静态校验、工具单测、Trace 单测全部通过；
- 至少一次隔离环境的真实 Skill smoke Eval 能完整生成 `analysis_report.md`。

## 8. 结论

本轮优化失败的根因不是“Phase 2 再多写一条落盘规则就能解决”，而是没有先建立编排可观测性和回归测试，就同时改动了分析规范与运行协议。正确的后续方向应是：

> 先冻结并测试原流程，再以最小原位改动逐项提高分析质量；质量规则尽量下沉到角色 Prompt 或最终校验，不随意改变 Phase 编排。
