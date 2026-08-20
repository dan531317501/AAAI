# Forward P/E 目标价实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task with verification checkpoints.

**Goal:** 将 stock-analysis-debate 的目标价改为“下一财年共识 EPS × 可比公司 Forward P/E P25/P50/P75”，并强制纳入最新网络估值证据、ADR/ADS 口径和 60 天新闻窗口。

**Architecture:** 主会话在数据抓取前通过网络搜索写入结构化 `valuation_consensus` 证据；Python 工具只负责校验证据、筛选统一口径的 peer 倍数和计算三档目标价。`data_validation` 将结果接入独立 Forward P/E gate，与 TTM/Trailing P/E gate 解耦；Skill/Prompt/README 负责约束搜索来源、报告展示和失败降级。

**Tech Stack:** Python 3.10+、pandas、yfinance、现有 TOON/JSON structured IO、pytest、Markdown Skill 文档。

## Global Constraints

- 始终使用中文向用户说明；运行目录中的机器生成 artifact 和 Phase 2-6 报告继续遵守现有英文中间产物规则。
- 不基于 TDD 编写代码；测试按实际业务语义覆盖有效、过期、期间冲突、ADR 口径冲突和新闻超窗场景。
- Forward P/E 目标价不读取或推导 TTM EPS/P/E；TTM 只服务现有 Trailing P/E。
- 目标 P/E 只接受可审计来源，不能由 LLM 自行填数字或从目标价反推。
- 新闻只允许分析日前 60 个自然日且有可解析发布时间的证据。
- 修改 Python 后同步 `README.md`，并完成测试和编译/导入验证。

---

### Task 1: 新增 Forward P/E 估值确定性模块

**Files:**
- Create: `skills/stock-analysis-debate/tools/forward_pe_valuation.py`
- Create: `skills/stock-analysis-debate/tools/tests/test_forward_pe_valuation.py`

**Interfaces:**
- `validate_valuation_consensus(payload: dict, analysis_date: str, max_age_days: int = 60) -> dict`
- `calculate_forward_pe_scenarios(forward_eps: dict, peers: list[dict], evidence: dict, analysis_date: str) -> dict`
- `build_forward_pe_valuation(forward_eps: dict | None, valuation_consensus: dict | None, analysis_date: str, analysis_mode: str = "current_research") -> dict`

- [x] 实现 payload schema 校验：网络来源必须有 `source_url`、`source_name`、`published_at` 或 `updated_at`、`forecast_period`、`basis`；peer 必须有正 `forward_pe`、来源、as-of、期间、币种和 `share_basis`。
- [x] 实现 60 天新鲜度和 historical replay fail-closed；过期/缺字段记录稳定 blocking reason，不抛出可被上层误认为成功的异常。
- [x] 只接受 `next_fiscal_year` 目标 EPS，要求正值、分析师数量大于 0、币种和股份口径可确认。
- [x] 过滤不匹配 peer，要求至少 3 条有效 peer；以线性插值计算 P25/P50/P75，并输出 Bear/Base/Bull 的 EPS、倍数、目标价和算术链。
- [x] 输出 peer 排除清单、网络共识证据、时间周期、币种/股份口径和 gate blocking reasons，便于 `Evidence Handoff` 逐项引用。
- [x] 编写语义测试：3 个 peer 得到正确 P25/P50/P75；负数/零倍数、过期来源、期间不一致、币种不一致、ADR 口径未知、少于 3 个 peer、历史回放全部关闭；不因普通股数比值字段存在而误伤已明确 `USD/ADR` 的 EPS。
- [x] 运行 `PYTHONPATH=skills/stock-analysis-debate/tools python -m pytest skills/stock-analysis-debate/tools/tests/test_forward_pe_valuation.py -q`。

### Task 2: 接入数据抓取与验证 gate

**Files:**
- Modify: `skills/stock-analysis-debate/tools/data_validation.py`
- Modify: `skills/stock-analysis-debate/tools/fetch_data.py`
- Modify: `skills/stock-analysis-debate/tools/tests/test_data_validation.py`
- Modify: `skills/stock-analysis-debate/tools/tests/test_fetch_data.py`

**Interfaces:**
- `build_validated_metrics(..., valuation_consensus: dict | None = None, ...)` consumes Task 1 output inputs and exposes `forward_pe_valuation` plus a dedicated gate.
- `fetch_data.py --valuation-consensus-file <path>` reads the pre-search artifact before building `validated_metrics`.

- [x] 将 `_select_target_consensus` 收紧为 `+1y`（下一财年），保留 provider period、currency 和 analyst count；不再用 `0y` 作为目标价 EPS 的替代。
- [x] 在 `fetch_data.py` 中读取可选 `valuation_consensus`，缺失时写结构化 unavailable artifact；生成 `forward_pe_valuation.toon` 并把路径放入 summary/results。
- [x] 将 `allow_target_price` 改为 `forward_eps_x_peer_forward_pe_percentiles`，只依赖 Task 1 的结果和当前研究时间状态，不依赖 TTM、当前 P/E、TTM reconciliation 或 share-count conflict。
- [x] 保持 `allow_exact_pe`、`allow_exact_pb`、`allow_exact_ev_to_ebitda` 原语义不变，避免改变其他估值方法。
- [x] 在 validation report 中展示 Forward EPS、P25/P50/P75、三档目标价、来源新鲜度和阻断原因；报告目标价必须是三档，不允许把单点 `Price Target` 误当成结果。
- [x] 更新现有 data-validation 测试：`0y` 只允许 expectation analysis、不允许目标价；明确 ADR share basis 的有效 fixture 可放行，即使 audit 里存在 ordinary/diluted share ratio 差异；缺网络证据时目标价关闭。
- [x] 运行 data-validation、fetch-data 相关测试，并用 `python -m py_compile` 验证新旧模块可编译。

### Task 3: 强制网络估值证据与最新新闻窗口

**Files:**
- Create: `skills/stock-analysis-debate/prompts/valuation_consensus_research.md`
- Modify: `skills/stock-analysis-debate/SKILL.md`
- Modify: `skills/stock-analysis-debate/prompts/data_policy.md`
- Modify: `skills/stock-analysis-debate/prompts/fundamentals_analyst.md`
- Modify: `skills/stock-analysis-debate/prompts/news_analyst.md`
- Modify: `skills/stock-analysis-debate/tools/fetch_data.py`
- Modify: `skills/stock-analysis-debate/tools/news_filter.py`
- Modify: `skills/stock-analysis-debate/tools/tests/test_news_filter.py`

- [x] 在 Skill Phase 1 中增加网络估值证据步骤和 `valuation_consensus.toon` schema：搜索股票/行业合理 Forward P/E、可比公司、来源 URL、依据、发布日期/更新时间、访问时间、预测期间、币种和股份口径；历史回放不使用当前搜索。
- [x] 明确网络来源质量和冲突处理：文章只有目标价没有明确 EPS/口径时不可反推 PE；定性“便宜/昂贵”不可转数字；peer 倍数按来源逐条记录。
- [x] 将 `NEWS_LOOKBACK_DAYS` 改为 60；在数据层过滤超窗或无法解析发布时间的新闻，审计 `news_start/news_end`、超窗数、日期缺失数和最新发布时间；更新 CN 历史高信号窗口说明为 8-60 天。
- [x] 在 News Analyst prompt 中要求只使用窗口内 `[Nxxx]`，对旧新闻和无法验证时间的新闻标记 Not Rated。
- [x] 在 Fundamentals Analyst 和 data policy 中加入固定报告字段：
  `Forward EPS: ...`, `Target P/E: ... / ... / ...`, `Price Target: ... / ... / ...`，并强制保留来源、依据和 forecast period。
- [x] 编写新闻测试：61 天旧新闻被丢弃、无日期新闻不进入当前证据、60 天边界保留、审计窗口与最终数量一致；运行新闻相关测试。

### Task 4: 同步 README 与最终报告模板

**Files:**
- Modify: `README.md`
- Modify: `skills/stock-analysis-debate/SKILL.md`
- Modify: `skills/stock-analysis-debate/prompts/portfolio_manager.md`

- [x] 更新数据产物表、工具表和运行说明，声明 `valuation_consensus.toon`、`forward_pe_valuation.toon` 和新的目标价 gate。
- [x] 更新 Final Decision 的 `Investment Thesis` 和 `Price Target` 规则：只有三档 Forward P/E 结果可写数字，格式严格展示 EPS/倍数/目标价；未授权则 `Not Rated`。
- [x] 保留其他章节和此前 Final Decision 五字段结构，不删除新闻、归因、辩论、投资计划和风险章节。
- [x] 检查 README 与 SKILL 中不存在“目标价依赖 TTM/当前 P/E”或“30 天新闻窗口”的残留描述。

### Task 5: 集成验证

**Files:**
- No new source files; inspect all changed files and current worktree.

- [x] 运行完整 Python 测试：`PYTHONPATH=skills/stock-analysis-debate/tools python -m pytest skills/stock-analysis-debate/tools/tests/ -q`（254 passed）。
- [x] 运行 `python -m compileall` 或等价的 `py_compile` 覆盖 `skills/stock-analysis-debate/tools`，确认模块导入和语法正常。
- [x] 用内存 fixture 验证示例格式会得到三档结果，但不把 `32.14/4.8/6.1/8.0` 写死；确认 gate 缺证据时为 false。
- [x] 检查 `git diff --check`、`git status` 和 staged scope，确保只包含本次 Forward P/E/新闻/文档改动，保留用户既有未提交修改。
