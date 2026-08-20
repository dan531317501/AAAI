# Agent 开发调研报告 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 基于截至 2026-08-14 可核验的官方资料，产出一份中文 Agent 开发调研报告，覆盖主流开源框架、Hermes/OpenCode/claude-code-sourcemap 三个项目，以及生产级 Agent 的核心能力、风险和落地方案。

**Architecture:** 报告采用“结论前置 + 统一评价维度 + 证据链接 + 方案矩阵”的结构。先定义 Agent、工作流和框架层次，再分别分析框架与项目，最后将通用能力映射到控制面、执行面、知识面、安全面和运营面，避免把产品特色误写成框架能力。

**Tech Stack:** Markdown、官方项目文档/GitHub 源码、MCP/A2A/NIST/OWASP 等公开规范与指南。

## Global Constraints

- 全文使用简体中文，关键 API、项目名、协议名和源码目录保留英文原名。
- 资料截点固定为 2026-08-14；会变化的版本、维护状态、功能和项目目录必须附官方链接。
- 三个指定项目按“产品定位、运行时、工具/扩展、记忆/上下文、多 Agent、交互/部署、安全、工程成熟度”统一比较。
- 对 `claude-code-sourcemap` 明确区分“源码还原研究仓库”和“可独立部署的 Agent 产品”，不把二者混为一谈。
- 保留当前工作区已有未提交改动；本任务只新增调研计划、报告，并在需要时增加 README 索引，不清理无关文件。
- 不采用 TDD；本任务不修改 Go/Python/TypeScript 业务代码，校验以 Markdown 结构、链接、来源完整性和工作区变更边界为主。

---

### Task 1: 建立资料与评价维度

**Files:**
- Create: `docs/superpowers/plans/2026-08-14-agent-development-research-report.md`
- Create: `docs/agent-framework-research-sources.md`（如需要保留独立证据表）

**Interfaces:**
- Consumes: 用户给出的三个 GitHub 仓库、主流框架名称和“核心能力/便利性/差异/通用方案”要求。
- Produces: 统一的比较维度、资料截点、官方来源清单和事实/判断边界，供后续报告章节复用。

- [ ] **Step 1: 明确评价维度**

  固定使用：抽象层次、模型适配、工具调用、工作流/状态、持久化与恢复、Human-in-the-loop、记忆与上下文、Multi-agent、扩展协议、观测评测、安全隔离、部署形态、生态与生命周期。

- [ ] **Step 2: 完成官方资料清单**

  至少覆盖 AutoGen、LangChain、LangGraph、LlamaIndex、Haystack、Semantic Kernel、CrewAI、PydanticAI 的官方文档；覆盖 Hermes、OpenCode、claude-code-sourcemap 的 README/文档/源码入口；覆盖 Anthropic、OpenAI、MCP、A2A、NIST、OWASP、OpenInference 的原始资料。

- [ ] **Step 3: 标注事实与推论**

  项目当前状态、功能、目录、许可证和维护状态只按官方资料陈述；“更适合什么场景”作为架构判断，明确写出依据和限制。

### Task 2: 编写主流 Agent 框架能力章节

**Files:**
- Create: `docs/agent-development-research-report.zh-CN.md`

**Interfaces:**
- Consumes: Task 1 的维度与来源。
- Produces: 框架定位、核心功能、开发者便利、边界、选型建议和横向矩阵。

- [ ] **Step 1: 先给 Agent、Workflow、Framework、Runtime、Platform 的定义**
- [ ] **Step 2: 分析 AutoGen 与维护状态风险**
- [ ] **Step 3: 分析 LangChain 与 LangGraph 的分层关系**
- [ ] **Step 4: 分析 LlamaIndex、Haystack、Semantic Kernel、CrewAI、PydanticAI 的差异化价值**
- [ ] **Step 5: 输出按场景的选型决策树**

### Task 3: 对比三个开源 Agent 实现

**Files:**
- Modify: `docs/agent-development-research-report.zh-CN.md`

**Interfaces:**
- Consumes: 三个仓库的官方 README、文档和公开目录/源码事实。
- Produces: 单项目画像、统一对比矩阵、差异解释、适用场景与风险。

- [ ] **Step 1: 说明 Hermes 的 self-hosted、gateway、skills、memory、cron、subagent、sandbox 特色**
- [ ] **Step 2: 说明 OpenCode 的 coding-agent、TUI/desktop/IDE、工具权限、MCP、LSP、skills、plugins、server/SDK 特色**
- [ ] **Step 3: 明确 claude-code-sourcemap 是非官方 source-map 还原研究仓库，而不是完整独立产品**
- [ ] **Step 4: 按运行时、上下文、工具、安全、扩展、交互、工程成熟度做对比**
- [ ] **Step 5: 给出“复用设计思想”和“不可直接复制”的边界**

### Task 4: 编写 Agent 通用核心能力与解决方案

**Files:**
- Modify: `docs/agent-development-research-report.zh-CN.md`

**Interfaces:**
- Consumes: 前两章的框架与项目事实，以及 Anthropic/OpenAI/MCP/A2A/NIST/OWASP/OpenInference 等公开资料。
- Produces: 从 PoC 到生产的能力清单、参考架构、关键数据模型、风险控制、评测指标、分阶段落地路线和验收门槛。

- [ ] **Step 1: 建立执行闭环：模型 → 结构化输出 → 工具 → 观察 → 状态 → 终止条件**
- [ ] **Step 2: 设计工具契约、权限、幂等、超时、重试、补偿与审计**
- [ ] **Step 3: 设计上下文工程、短期/长期记忆、RAG、引用和上下文压缩**
- [ ] **Step 4: 设计工作流、多 Agent、MCP/A2A、异步任务、checkpoint、人工审批与恢复**
- [ ] **Step 5: 设计安全纵深：身份、租户 ACL、沙箱、网络出口、密钥、Prompt Injection、防数据外泄**
- [ ] **Step 6: 设计评测、可观测性、成本/延迟治理、回放和灰度发布**
- [ ] **Step 7: 给出 0-30/30-90/90+ 天的落地路线和验收清单**

### Task 5: 报告校验与索引同步

**Files:**
- Modify: `README.md`
- Verify: `docs/agent-development-research-report.zh-CN.md`

**Interfaces:**
- Consumes: 完整报告和当前 Git 状态。
- Produces: 可访问的 README 索引、无断链/无占位符/无自相矛盾的最终交付物。

- [ ] **Step 1: 检查章节覆盖用户三项要求**
- [ ] **Step 2: 检查每个会变化的关键事实都有官方链接**
- [ ] **Step 3: 检查内部链接、外部链接、表格和 Mermaid/代码块语法**
- [ ] **Step 4: 检查 `git diff --stat` 和 `git status --short`，确认没有覆盖用户既有改动**
- [ ] **Step 5: 向用户交付报告路径、核心结论、资料截点和校验结果**
