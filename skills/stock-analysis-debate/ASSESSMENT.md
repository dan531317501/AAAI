# `stock-analysis-debate` Skill 专业评估报告

**评估日期**: 2026-08-05
**评估视角**: 股票研究方法论（卖方/买方）+ 数据工程可靠性
**评估范围**: `SKILL.md`(445行) / `prompts/`(16个) / `tools/`(18个 Python 模块, 9588行) / 3份真实产出报告(01810.HK, BABA, 601138.SH)
**验证方式**: 静态阅读 + 数字复算 + 单测执行(148 passed) + 契约与产出交叉核对 + **真实网络调用实测**(2026-08-05/06, AAPL / 00700.HK / 600519.SH / 00005.HK)

---

## 0. 总体结论

| 维度 | 评分 | 说明 |
|---|---|---|
| 方法论设计 | **A-** | 归因分析框架（预期基线→触发→放大器→异常收益→基本面锚→条件展望）是本项目最大亮点，达到专业卖方事件研究水准；证据分级 A/B/C/Rejected/Not Rated 设计正确 |
| 反幻觉机制设计 | **A** | fail-closed 契约 + gate + evidence ID + Not Rated 边界 + 点时护栏，设计意图为同类项目中最严谨 |
| 反幻觉机制**落地** | **D** | 设计与执行严重脱节：3份真实报告中**每一份**都存在绕过契约的硬违规（详见 §1） |
| 数据覆盖 | **C-** | 缺失整个现金流量表分析、杠杆比率、股东回报、资金流（南向/融券/龙虎榜）、同业可比；且**大量数据已抓到手却从未读取**（short interest、财报日历、16个FRED序列、beta） |
| 估值口径正确性 | **C+** | P/B 口径正确；EV 漏少数股东权益/优先股；跨币种 P/E 对账逻辑会污染正确值 |
| 数据管道正确性 | **C** | A股成交量混「手」与「股」（100倍污染 VWMA/MFI）；两个基准符号实测失效；350天 lookback 不足以支撑 200SMA 趋势判断 |
| 辩论机制 | **A-** | 双轮 Bull/Bear + 三方风险辩论，实测有真实立场修正与收敛（17处），非表演性辩论 |
| 工程质量 | **B-** | 148 单测全过、降级架构严谨、重试分类正确；但有 1 处单点崩溃、零缓存、零限速、价格数据抓两次、`_EVENTS` 全局态非线程安全 |
| 上下文工程 | **A** | 直写文件 + 只返回确认 + 按需读取，是本项目第二大亮点，主会话上下文控制得很好 |

**一句话判断**：这是一个**方法论设计水平远超其执行保障水平**的系统。契约层写得极好，但没有任何机制阻止 LLM 无视它 —— 而实测显示 LLM 确实无视了它。

**两个最高优先级**：(1) 让已有的 gate 真正生效（补 Phase 7.5 确定性校验器）；(2) **用好已经拿到但从未读取的数据** —— P0 五项修复全是 1 行到数行的改动，却能消除全 pipeline 崩溃风险、100 倍成交量污染、以及两个市场基准的永久失效。

---

## 1. 严重：契约在真实运行中被系统性绕过

这是本次评估最重要的发现。`data_policy.md` 与 `SKILL.md` rule 10 规定"`validated_metrics` 是唯一授权数值源，被 gate 阻止的声明必须输出 N/A"。实测三份报告全部违规。

### 1.1 小米(01810.HK)：4处硬违规，全部指向货币错配

契约状态：`allow_exact_pe: false`、`statement_ttm_diluted_eps: unavailable`、`point_in_time_pe: unavailable`

`analysis_report.md` 实际输出（逐个复算验证）：

| 报告中的数字 | 契约状态 | 复算结果 | 判定 |
|---|---|---|---|
| "statement-derived TTM P/E **18.5x**" (L15,L62) | `point_in_time_pe: unavailable`，`allow_exact_pe: false` | `27.96 HKD ÷ 1.51 CNY = 18.52` —— **HKD 价格除以 CNY EPS，未做 FX 换算**。正确应为 `27.96×0.8601÷1.51 = 15.93` | 违反 gate + 跨币种混算（`data_policy.md` 第6条明令禁止） |
| "TTM EPS **1.51**" (L62,L111) | `unavailable`（`non_contiguous_quarters`） | `0.18+0.46+0.45+0.42 = 1.51` —— LLM **手工相加了 income_stmt.csv 的四列**，而这四列是 `2026-03-31, 2025-09-30, 2025-06-30, 2025-03-31`，**缺 2025-12-31**，工具正因此判定不连续 | LLM 手工重建了工具明确拒绝提供的指标 |
| "P/B **2.87**" (L15,L27) | 契约值 `2.472041` (verified) | `27.96 ÷ 9.7282 = 2.874` —— 同样漏 FX | 有可用的正确契约值却用了自算的错值 |
| "EV/EBITDA **19.2x**" (L15) | 契约值 `16.228` (verified) | `(718392655872 HKD + 34690134000 CNY − 112119065000 CNY) ÷ 33688143872 CNY = 19.03` —— **HKD 市值与 CNY 债务/现金直接相加** | 契约值可用却用了混币种自算值 |

**次级违规**：

- "provider 一致预期盈利同比 **-58.1%**"（L11,L15,L25,L36,L52，全文出现 ≥6 次，是整个 HOLD 评级的核心论据）—— 该值 metric_id 为 `latest_quarter_earnings_growth_yoy`，`quality_flags: historical_actual_not_consensus`，`allowed_uses: [historical_growth]`。这是**已披露的最新季实际同比**，不是分析师一致预期。`data_policy.md` 第4条专门禁止这个误读，`expectations.txt` 里也专门标注了 "actual YoY, not analyst forecasts"。**LLM 读到了这行标注，仍然误读，并把它作为评级主证据。**
- "共识 Target **39.73**"（L70,L110,L141）—— 数据中实际值为 `39.15`（`expectations.txt:21`）。**39.73 在整个数据目录中不存在。** 这是一个凭空产生的数字，并被用于"共识目标与 -58.1% 盈利预期内部矛盾"的论证。

### 1.2 BABA：把已知错误数字当论据反复引用

契约标记 `TTM Valuation Reconciliation Status: mismatch`（provider 6.50 vs 报表推导 43.04，差 84.9%），但 `financial_audit.py` 仍将 `Preferred TTM EPS = 43.04 / P/E = 2.9577` 输出为"首选"。

根因：BABA 财报 Diluted EPS 以 **ADS**（1 ADS = 8 普通股）计价，而股数用的是 `Ordinary Shares: 18,580,374,278`（普通股）。分子分母口径不一致，43.04 是错误的 8 倍级放大值。

报告（L16,L21,L44,L118）识别出了这是"股数口径伪影" —— **识别是对的**，但随后把 2.97 作为"多方论据"在辩论、裁决、Data Caveats 中反复引用 4 次。工具输出了一个已知错误的"Preferred"值，LLM 只能被动打补丁，而不是拿到 N/A。

`financial_audit.py` 未处理 ADR/ADS 比例，这是覆盖美股中概股必需的能力。

### 1.3 601138.SH：只有1个季度却仍开放估值

`TTM EPS Statement Periods: 2026-03-31`（仅1列），`Statement-Derived TTM: N/A`。报告用 `Forward P/E 16.48` 作为估值锚 —— 这是 provider 未审计共识快照，`fundamentals.txt:78` 明确写 "the forecast itself is not independently audited"。缺少 TTM 锚时以未审计 forward 值定锚，且未在 Data Caveats 中把"估值锚不可审计"列为一级风险。

### 1.4 根因诊断（关键）

三份报告的违规模式一致，指向同一个结构性缺陷：

```
data_validation.py 计算 gate 时读的是 raw audit_metrics dict，
而 metric 的 status 是另一套独立逻辑。两者从不校验一致性。
```

于是产生了自相矛盾的契约：`allow_exact_pe: false` 与 `allow_target_price: false`（对小米正确关闭了），但同时 `allow_exact_valuation: true`、`allow_exact_pb: true`、`allow_exact_ev_to_ebitda: true` 全开。LLM 看到"估值总闸门开着"，就把关闭的 P/E 也自己补上了。

更关键的是：**契约完全没有强制执行层**。`gates` 只是文件里的一行文字，没有任何代码检查最终报告是否遵守。LLM 是唯一的执行者，而 LLM 在"提示词要求我做完整估值"和"gate 禁止我做 P/E"之间选择了前者 —— 这是可预期的行为，不是意外。

**修复方向**（按优先级）：

1. **gate 必须从 metric status 反推**，不能读 raw dict：
   ```python
   by_id = {m["metric_id"]: m for m in metrics}
   ok = lambda mid: by_id.get(mid, {}).get("status") in ("verified", "single_source")
   exact_pe_ready = currency_ready and ok("point_in_time_pe") and ok("statement_ttm_diluted_eps")
   ```
2. **新增 Phase 7.5 确定性报告校验器**（Python，非 LLM）：正则扫描 `analysis_report.md` 中的所有数字，与 `validated_metrics` 交叉比对；发现契约中不存在或被 gate 阻止的数字则报错并要求重写。这是唯一能真正闭环的机制。当前 `SKILL.md:309` 主动删掉了 LLM 验证器（"do not launch an LLM verifier"，方向正确），但**没有用确定性验证器替代它，只是留了个空洞**。
3. **`fundamentals.txt` 不应输出已知错误的 "Preferred" 值**。mismatch 时输出 `N/A + 冲突原因`，让 LLM 拿不到错值。
4. **`financial_audit.py` 处理 ADS 比例**（`info.sharesOutstanding` vs 财报股数比值检测，>2x 时判定口径不一致并置 N/A）。
5. **把"手工从 income_stmt.csv 相加重建 TTM"列为 `data_policy.md` 显式禁令** —— 当前政策禁止"copy raw provider value"，但没禁止"用原始 CSV 自己算一个被工具拒绝的指标"，LLM 钻了这个空子。

---

## 2. 严重：`allow_segment_growth` 永久 False 与分部分析师提示词直接冲突

`data_validation.py:428` 硬编码 `"allow_segment_growth": False`，无任何分支能置 True。

而 `prompts/segment_analyst.md:26-28` 的核心任务是"对每个分部比较最新季 YoY 与前期 YoY，识别加速/减速拐点"、"指出集团主要增长/下滑驱动"，并要求以 `PRIMARY DRIVER: <segment>` 结尾。

`SKILL.md:162` 规定 "A false gate **prohibits** that output"。

**结果**：分部分析师的全部核心任务被永久禁止，但提示词仍然要求它执行。实测（01810.HK `segment_analyst.md`）分析师选择了服从提示词、无视 gate，输出了 `Smart EV +13%`、`IoT -19.2%`、`PRIMARY DRIVER`，并且这些数字进入了最终报告的核心论据（L38, L123）。

这是**制度性诱导越界**：系统同时下达两条互斥指令，无论 LLM 怎么选都在违规。

**修复**：二择一，不能都留。
- (A) 当 Longbridge 提供原始记账币种 + dated FX 时开放该 gate；
- (B) 把 `segment_analyst.md` 改为只做**结构占比(mix)** 不做增长率，并在 `SKILL.md` 参数表中说明该 gate 为何永久 False。

---

## 3. 严重：`allow_strong_rating` 的冲突检测是死代码

`data_validation.py:384`: `conflicts = [m for m in metrics if m["status"] == "conflict"]`

全代码库**没有任何一处给 metric 赋 `status="conflict"`**（`_metric` 只降级为 `unavailable`；`financial_audit.py:399` 的 conflict 是整体 result status，从未映射到单个 metric）。实测 01810.HK 的 `conflicting_metrics[0]:` 为空，尽管 `TTM Valuation Reconciliation Status: provider_only`。

同时，`_sec_official_metrics` 生成的 5 个 `official_*` metric 标注 `allowed_uses: [official_fundamental_cross_check]`，但**代码中没有任何地方将它们与 yfinance 值比对**。官方披露交叉校验只是声明，未实现。

**影响**：`allow_strong_rating` 退化为 `exact_pe_ready and consensus_ready`；宣称的冲突防护从未启用；`official_filings` 通道对任何 gate 都无影响，是纯装饰性的（HKEX 抓到3份 PDF，`llm_extraction_allowed: false`，然后什么也不做）。

**修复**：实现 official vs provider 比对（`official_diluted_eps` vs `statement_ttm_diluted_eps` 对应季、`official_stockholders_equity` vs `common_stock_equity`），超阈值时双方标 `conflict`。

---

## 4. 严重：EV 口径漏项 + 金融业不适用未拦截

`financial_audit.py:240-246`:
```
enterprise_value = market_cap + total_debt − cash_and_investments
```

**漏 4 项**：

1. **少数股东权益 (NCI)** —— 实测 01810.HK 的 `balance_sheet.csv` **已包含** `Minority Interest: 386,989,000`，但代码未读取。小米此处占比小，但港股/A股综合企业、地产、SOE 的 NCI 常占权益 10-30%，会**系统性低估 EV，进而低估 EV/EBITDA，制造"便宜"假信号**。分母 EBITDA 是含 NCI 的合并数，分子不含，口径不匹配。
2. **优先股 / 永续债** —— A股与港股大量发行永续债（会计上计入权益，经济上是类债务）。
3. **租赁负债 (IFRS 16)** —— 零售/电信/航空的租赁负债可与有息负债同级，`Total Debt` 是否含它随公司变化，代码无判定无披露。
4. **受限现金未扣**（保守方向，可接受但未披露）。

**行业适用性缺失**：`SKILL.md` 举的示例标的就是 601988.SH（中国银行）。银行的"现金"是经营性资产、"总债务"含存款/同业负债，**该公式对金融业产出无意义数字**；且银行不披露 EBITDA。但 `exact_ev_ready` 无任何行业门槛，会照样开放 `allow_exact_ev_to_ebitda`。

**EBITDA 为负时未拦截**：`financial_audit.py:247-251` 只判 `not in (None, 0)`，负 EBITDA 会产出负倍数并通过 gate。

**修复**：

```
EV = 市值 + 总债务 + 少数股东权益 + 优先股/永续债 − 现金及等价物
```

读取 `Minority Interest` / `Preferred Stock Equity` / `Capital Lease Obligations`；任一缺失记 `quality_flags` 而非静默按0；`provider_ttm_ebitda > 0` 才计算；按 sector 对金融业强制关闭该 gate。

---

## 5. 严重：TTM 连续性判定锁死半年报公司（直接命中 HK/CN 目标市场）

`financial_audit.py:103-115` 要求恰好 4 期且相邻间隔 60-120 天。

港股与 A 股大量公司只披露**年报 + 中报**，间隔约 182 天，全部落在窗口外，导致 `statement_ttm_eps = None`，进而 `ttm_ready = False`，最终 **`allow_exact_pe`、`allow_target_price`、`allow_strong_rating` 三项永久 False**。

拒绝相加在算术上是正确的（4个半年列=2年，会双计），但结果是对 SKILL 明确支持的两个市场的一大类标的，"精确 P/E + 目标价 + 强评级"能力**结构性失效**，且给出的理由（"四个连续季度不可用"）不会让使用者意识到这是报告频率问题。

**修复**：识别报告频率 —— 2 个间隔约 182 天的半年列即构成完整 TTM，此时求和并标 `quality_flags: [semiannual_reporter_ttm]`；4 个半年列时取最近 2 个。

**同一函数的时区脆弱性**：`strptime(period, "%Y-%m-%d")` + `except ValueError: return False`。yfinance 财报索引当前 tz-naive（输出 `2025-12-31`，可解析），但若上游改为 tz-aware（输出 `2025-12-31 00:00:00+00:00`），**所有标的 TTM 静默失效**，只表现为"gate 全关"，无任何诊断信息。改用 `pd.to_datetime(errors="coerce")` 并在失败时写 warning。

---

## 6. 严重：`financial_currency` 推断 fallback 会"自信地算错"

`data_validation.py:91-93`:
```python
financial_currency = info.get("financialCurrency") or (
    estimate_currencies[0] if len(estimate_currencies) == 1 else None)
```

分析师预期表的币种是**卖方建模币种**，与财报记账币种不必然相同。中概 ADR 的一致预期常以 USD 发布而财报是 CNY。

一旦推断错，`fetch_fx_rate` 会拿到一个"verified"的错误汇率，使 `currency_ready = True`，于是**全部估值 gate 打开，全部数字系统性错误，且契约声称 `status: verified`**。

这比 fail-closed 失效更危险：从"数据缺失"退化为"数据自信地错"。

**修复**：删掉该 fallback。`info.financialCurrency` 缺失就是 `None`，让 gate 关闭。

---

## 7. 严重：`currency_metadata_missing` 时静默假设 FX=1.0 并标 status "complete"

`financial_audit.py:214-218`：缺币种元数据时 `effective_fx_rate = 1.0`，`valuation_currency_status = "currency_metadata_missing"`。

`:415` 的 warning 只在 `== "unavailable"` 时触发，该状态**不产生任何 warning**；`:388-401` 的 `base_complete` 判定不含该状态，于是 **status 是 "complete"**。

而 **CLI 入口 `main()`（`:552-569`）从不传币种**，必然走这条路。对港股直接跑 `python financial_audit.py` 会把 FX=1.0 的错误 P/B、市值、EV 以 "complete" 状态写进 `fundamentals.txt` —— 而 `fundamentals.txt` 是分析师的授权阅读文件（`SKILL.md:218`）。`data_validation.py:329` 的 `== "verified"` 拦截只保护 `validated_metrics`，拦不住分析师直接读 `fundamentals.txt`。

**修复**：该状态下 `effective_fx_rate = None`（与 `unavailable` 同处理），且 `main()` 要求币种参数或拒绝执行。

---

## 8. 严重：A股 Longbridge 回补的成交量单位不一致，同一列混「手」与「股」

- **位置**：`longbridge_fetcher.py:90`（`"Volume": float(item.get("amount", 0) or 0)`），消费点 `fetch_data.py:291`
- **实测证据**：600519 长桥 `amount=42689`，yfinance `Volume=4268859`，**比值精确为 100.0** —— 长桥 A 股用「手」(1手=100股)，yfinance 用「股」。港股实测比值=1（长桥用股）。
- **问题**：`fetch_data.py:291` 把长桥缺失日 `concat` 进 yfinance 数据后，A股同一 Volume 列里前 231 天是「股」、最后 1 天是「手」。
- **专业影响**：直接污染 **VWMA 与 MFI**（两者都由成交量加权），并让「放量/缩量」判断在**最新一个交易日出现 100 倍级假萎缩** —— 而最新交易日恰是归因分析师最关注的那天。`price_context.daily_series[].target_volume`（`price_attribution_data.py:218`）同样受污染，直接喂给量能异常判定。实测三份报告中 01810.HK 是港股（比值1，未暴露），但 601138.SH 是 A股，其报告中的成交量论证存在此风险。
- **修复**：CN 市场 `amount × 100`；或用 `balance / amount` 自动判别单位（实测 600519 得 131195 ≈ 均价×100，00700 得 491.8 ≈ 均价×1）。更稳妥：长桥回补行只补 OHLC，Volume 写 `NaN` 并在 `data_quality` 标注，绝不让两种单位共存于一列。

---

## 9. 严重：`prediction_markets` 的 ValueError 逃出降级路径，直接崩掉整个 pipeline

- **位置**：`prediction_markets.py:120`（`raise direct_exc from proxy_exc`）→ `:208`（只捕 `requests.RequestException`）
- **实测复现**：Gamma 直连返回非 JSON（`response.json()` 抛 `ValueError`）且 Jina 代理也失败时，`_request` 重抛 `ValueError`，但 `search_topic:208` 的 `except` 只写了 `requests.RequestException`。异常穿透 `fetch_prediction_markets` 冒泡到 `fetch_data.py:1450`（**无 try 包裹**），**整个数据抓取进程终止，此前 14 步产物全部作废**。
- **专业影响**：Polymarket 三个宏观话题对个股分析边际价值极低（见 §15.2），却被赋予让全流程崩溃的权力 —— 风险收益完全倒挂。上游返回 HTML 错误页/Cloudflare 挑战页是常态而非罕见事件。
- **修复**：`:208` 改为 `except (requests.RequestException, ValueError)`；`fetch_data.py:1450` 加 try/except 兜底。**对照：`macro_data.py:232` 的写法是正确的（已捕 `ValueError`）**，可见这是遗漏而非设计。

---

## 10. 严重：350 天 lookback 不足以支撑 200SMA，实测已在临界线上

- **位置**：`fetch_data.py:73`（注释声称「~230+ trading days, comfortable margin for 200 SMA」）
- **实测**：350 日历日 → US 241 个交易日、CN 232 个、HK 235 个。`close_200_sma` 是 rolling(200)，因此**可输出的 200SMA 序列只有 41 个点（CN 32 个）**，而 `fetch_indicators` 默认只渲染最近 30 天（`:328` `lookback_days=30`），刚好在边缘。
- **专业影响**：(a) **无法判断 200SMA 的斜率/趋势方向**（只有 41 个点）；(b) **无法做 YoY 价格对比**（需 >252 交易日 + 前一年基期）；(c) 一旦遇长假密集年份、停牌、或港股叠加数据源缺日，`trading_days` 掉到 200 以下，`warning_no_200_sma=True`，牛熊分界线整个变 N/A。
- **修复**：`PRICE_LOOKBACK_DAYS` 提到 **≥550**（约 380 交易日，覆盖 200SMA 满序列 + 完整 YoY 基期 + 52周高低位）。成本仅单次 history 调用的数据量，**无额外请求**。

---

## 11. 中等：异常收益未做 beta 调整

`price_context.toon` 的 `target_excess_return_pct` 是**简单差值**（`21.039 − 10.027 = 11.012`），无 beta 调整，无回归窗口，无 t 统计。

**专业影响**：这不是学术意义上的 abnormal return。小米 beta 0.722（`fundamentals.txt:13`，已抓取但未用）。恒指 +10% 时，beta 调整后的期望收益是 `+7.2%`，超额应为 `+13.8%` 而非 `+11.0%`。对高 beta 成长股（很多科技股 beta 1.3-1.8），简单差值会**系统性高估**其超额收益，进而系统性夸大"个股专属驱动"的强度 —— 归因分析师会把 beta 暴露误认为 alpha。

这是归因框架（本项目最强的部分）的一个实质性方法论缺口。

**修复**：用已抓取的 `price_context` 60 日对齐序列做 OLS 估 beta（数据已在手），输出 `beta_adjusted_excess_return` 与 `raw_excess_return` 两列，附 `beta` 与 `r_squared`；`r_squared < 0.1` 时标注 beta 调整不可靠。

**同类问题（已实测确认符号错误）**：

- **HK sector proxy `^HSTECH` 在 Yahoo 上不存在** —— `price_attribution_data.py:59`。**实测 404**：`Quote not found for symbol: ^HSTECH`，返回 0 行。而 HK 的 Technology / Communication Services / Consumer Cyclical 三个 sector 都只配了这一个 proxy。后果：**腾讯/美团/阿里等港股科技龙头（正是本 Skill 最可能分析的标的）永远拿不到行业超额收益**，归因只能对着恒指做，无法区分「个股问题」与「科技板块整体回调」—— 这恰是港股归因中最需要区分的一对。实测 01810.HK 报告 L109 的「行业代理 HSTECH 全程 Not Rated」就是这个 bug，不是数据源问题。**实测可用替代：`3033.HK`（南方恒生科技 ETF，22行完整）、`^HSCE`（恒生中国企业指数，23行）**。HK 的 Financial Services / Real Estate 等 sector 目前无任何 proxy。
- **CSI 300 符号覆盖有洞，A股标准基准大面积失效** —— `price_attribution_data.py:24` 用 `000300.SS`。**实测**：600519 有 232 个交易日，`000300.SS` 只有 220 天，**缺 12 天**（7月只到 4529 就直接跳 8月）。而 `:187` 要求 comparator 在窗口两端点都有精确收盘价，否则整格 `not_rated`。实跑 `fetch_attribution_context` 结果：**1d/5d/20d 三个窗口的 broad_market 全部 `not_rated`，只剩上证综指可用**。沪深300 是 A股标准基准（也是提示词 `:77` 要求的 broad market），上证综指含大量小盘股与非流通权重，专业性远逊。**修复：改用 `510300.SS`（华泰柏瑞沪深300 ETF，实测22行完整）**；或放宽端点匹配为前向填充 + 标注实际使用日期（后者引入轻微前视，需权衡）。

---

## 12. 中等：数据覆盖的专业缺口

### 12.1 现金流量表完全未被分析（最严重的覆盖缺口）

`cashflow.csv` 已抓取，但 `financial_audit.py` 与 `data_validation.py` 对它**零引用**（grep `cashflow|Operating Cash|Free Cash|Capital Expenditure` 在两文件中 0 命中）。且实测 01810.HK 的 `cashflow.csv` 内容是 `# No cashflow data found`（抓取失败但无任何 gate 反应）。

缺失指标族：

- **经营现金流 OCF、资本开支、自由现金流 FCF、FCF yield**
- **OCF ÷ 净利润** —— 识别应收虚增、渠道压货的第一道防线，A股/港股尤其必要
- OCF ÷ 流动负债

对一个要判断 Buy/Sell 的系统来说，**不看现金流是重大方法论缺陷**。BABA 报告里出现的 "TTM FCF -50.7B" 是 LLM 从 `cashflow.csv` 自己算的，未进契约、未验证。

### 12.2 杠杆与资本回报（分量都在手，未做差）

- **净负债** = 总债务 − 现金（`financial_audit.py:340-341` 两个分量都有，未相减）
- **净负债/EBITDA**、**利息覆盖倍数 (EBIT÷利息费用)** —— 两个都算不出来，但分量都在
- **ROIC** —— 只有 provider 的 `returnOnEquity` 留在 `fundamentals.txt`，未进契约

### 12.3 资金流与筹码结构（对 HK/CN 尤其关键）

系统在 3 份报告的 Data Caveats 中反复承认"融券/margin/南向资金/机构持仓全部无数据，逼空/强制平仓/买方身份全部 Not Rated"（01810.HK L109）。这是诚实的，但也意味着**归因框架的第3步"Transmission/Amplifier"在 HK/CN 市场基本是空的** —— 而这恰恰是解释短期大幅波动的核心环节。

缺失：

- **港股通/沪深股通南北向资金**（HKEX/沪深交易所每日披露，免费）
- **融资融券余额**（沪深交易所每日披露，免费）
- **卖空比例/借券成本**（HKEX 每日卖空数据，免费）
- **龙虎榜/大宗交易**（A股，免费）
- **股东增减持公告、解禁时间表**（对 A股/港股是一级催化）
- 13F 机构持仓（美股）、ETF 持仓、指数纳入/剔除

其中**南向资金 + 融券余额 + 卖空比例三项对 HK/CN 是免费公开数据**，投入产出比极高。

### 12.4 yfinance 已提供、实测可取、但代码从未调用（近乎零成本）

这一组是**最高杠杆**的修复 —— 无需新数据源、无新依赖、改动 <50 行：

| 端点 | 实测返回 | 解锁什么 |
|---|---|---|
| `info["sharesShort"]` / `shortRatio` / `shortPercentOfFloat` / `dateShortInterest` | AAPL 实测 `sharesShort=146547784`, `shortRatio=2.28` | **直接解锁 `price_action_attribution_analyst.md:52`「No short squeeze without short evidence」这条空转的硬规则**。零额外请求（`info` 已在调用） |
| `Ticker.calendar` | AAPL 实测 **下次财报日 2026-10-30** + 下期 consensus (`Earnings Average=1.97643`, `Revenue Average=113256580210`) + `Ex-Dividend Date=2026-08-10` | 当前 `expectations.txt` **完全没有「下次财报何时、市场预期多少」** —— 而这是持仓期限决策的第一要素。三份报告都把"Q2财报"作为验证节点却无日期 |
| `Ticker.dividends` / `Ticker.splits` | AAPL 实测分红 0.26→0.27、拆股 2005/2014/2020 | 分红连续性/增长率/是否刚除权。当前只有 `info["dividendYield"]` 一个静态数字 |
| `Ticker.institutional_holders` | 实测返回 BlackRock/Vanguard/State Street 及 **`pctChange` 环比变动** | 13F 的轻量替代 |
| `info["floatShares"]` / `impliedSharesOutstanding` / `heldPercentInstitutions` / `heldPercentInsiders` | 实测可得 | 自由流通盘、稀释口径、持股结构。**换手率必须用 `floatShares` 才算得对** |

### 12.5 提示词已明文依赖但无数据源，导致硬规则永久空转

| 缺失数据 | 提示词依赖点 | 后果 |
|---|---|---|
| 融资融券余额 | `price_action_attribution_analyst.md:53`「No forced-liquidation claim without leverage evidence」 | 强制平仓假设**永远** Not Rated。akshare 已装，`stock_margin_detail_sse/szse`、`stock_margin_account_info` 可用 |
| 北向/南向资金 | `:43` 明列 "foreign flows" 为可补缺口 | A股/港股最重要的边际增量资金无法量化。akshare `stock_hsgt_individual_em`、`stock_hsgt_hold_stock_em` 可用 |
| 同业可比估值表 | `:78` 要求「up to three economically comparable peers」 | peer 比较永远 Not Rated，或更糟 —— **LLM 凭记忆编造 peer set**（提示词自己警告了这个风险却不给数据）。实测三份报告全部 Not Rated（这次分析师守规则了，但这是运气） |
| 盈利预测修正**序列** | `:125` "estimate revisions" 列为 A 级证据要件 | 当前 `eps_revisions` 只有 `upLast7days/upLast30days` 计数快照（实测），**无时间序列**，无法计算 revision momentum 的方向与加速度 |
| 大宗交易 / 龙虎榜 | — | A股异动的**唯一**可获得的席位级资金证据。akshare `stock_lhb_stock_detail_em` |
| 股东增减持 / 解禁时间表 | — | `insider.txt` 只覆盖董监高个人交易（**实测港股仅返回独董持股**），不含大股东增减持与限售解禁 —— 后者才是港股/A股最主要的供给冲击来源 |

### 12.6 其他缺口

- **同业可比估值表 (peer comps)** —— 见 §12.5。可从 sector + 市值区间自动构建候选池，或允许 `segments.yaml` 式的手工 peer 清单。
- **股息率/分红派息记录/回购** —— `dividendYield` 已抓取未进契约；回购完全缺失。`Ticker.dividends` 可直接取（§12.4）。
- **股本变动历史** —— 只取单期 `Ordinary Shares Number`，无跨期序列，无法计算稀释率/SBC 摊薄。
- **流通市值 vs 总市值** —— 用总股本算市值。对 A股（限售/国有股）和港股（大股东锁仓）会显著高估可交易市值，也让"日均成交额÷流通市值"类流动性判断无法做。`info["floatShares"]` 实测可得（§12.4）。
- **已实现波动率、最大回撤** —— OHLCV 已在手，纯计算。

### 12.7 技术指标（13个）的缺口

现有 13 个中，`close_50_sma / close_200_sma / close_10_ema / boll / boll_ub / boll_lb / vwma` 共 **7 个都是价格均线族**（信息高度重叠），`macd/macds/macdh` 是同一指标的三个分量。真正独立的信息维度只有 4 个：趋势(SMA)、动量(MACD/RSI)、波动(ATR/BOLL)、资金流(MFI)。

**完全缺失**：

- **OBV / CMF** —— 量价背离的核心。MFI 是振荡器（有界、易饱和），OBV 是累积量（无界、可看趋势），**两者不可互替**
- **ADX** —— 判断「趋势市 vs 震荡市」的唯一标准工具。**没有它，MACD 金叉在震荡市的假信号无法过滤**
- **52 周高低位置** `(close − low52) / (high52 − low52)` —— 动量因子经典代理。`info` 里已有 `fiftyTwoWeekHigh/Low`（`fetch_data.py:521-522` **已抓但只作为孤立数字打印，未计算相对位置**）
- **相对强弱 RS**（个股/基准比价曲线）—— 与超额收益互补：超额收益是点对点，RS 曲线是连续的强弱演化
- **换手率** —— A股/港股情绪第一指标，需 `floatShares`（见 §12.4）
- **成交量分布 / 筹码峰** —— 支撑阻力的量化依据

**专业影响**：当前指标集能回答「趋势方向」和「是否超买」，但**无法回答「量能是否配合」和「现在是趋势市还是震荡市」** —— 而后两者恰好决定前两个信号能不能用。

**修复**：stockstats 原生支持 `adx`、`dma`、`trix`、`cr`、`wr`、`kdjk`。OBV/CMF 需手写（各 3 行 pandas）。建议增补 `adx`、`obv`、`52w_position`、`rs_vs_benchmark`，并可把 `boll_ub/boll_lb` 折叠为 `%B` 单值以控制 token。

### 12.8 复权口径未声明（已实测，比预想的好但仍需修）

- `fetch_data.py:258-264` 的 yfinance `history()` 未传 `auto_adjust`，而 yfinance 1.2.2 默认为 `True`（已核对源码），返回**后向复权**价且移除 `Adj Close` 列。**实测 AAPL 返回列为 `['Open','High','Low','Close','Volume','Dividends','Stock Splits']`，确认无 `Adj Close`** —— 因此 `fetch_data.py:312` 的 `for col in [..., "Adj Close"]` 和 `:348-352` 的列映射**都是死代码**。
- **好消息（实测）**：长桥 `adjust_type=1` 与 yfinance 后向复权口径一致 —— AAPL 一年期最大偏差 **0.00039%**（窗口内含 4 次分红）。**所以 §8 的成交量问题不存在于价格列**。但这个一致性是「碰巧」而非「保证」，`adjust_type=1` 的语义未在代码或文档中记录，长桥若改默认口径不会有任何告警。
- **仍存在的实际影响**：(a) `ohlcv.csv` 的价格不等于任何一天的真实市场价，与 `fundamentals.txt` 里 `info` 提供的**未复权** `fiftyTwoWeekHigh/Low`、`targetMeanPrice` **口径不一致**，跨文件比价会出错；(b) `financial_audit.compute_point_in_time_metrics` 用 ohlcv 的 Close 算 P/B、EV/EBITDA，**用复权价算估值会随历史分红累积而系统性偏低**。
- **修复**：`ohlcv.csv` 头部（`:318`）显式写 `# Adjustment: back-adjusted (yfinance auto_adjust=True; Longbridge adjust_type=1)`；清理 `:312/:348-352` 死代码；`data_quality` 加「估值指标须用未复权价」约束，或改 `auto_adjust=False` 保留双列（指标用 Adj Close，估值用 Close）。

### 12.9 其他缺口

- **A+H 折溢价** —— SKILL 同时覆盖 HK 与 CN，但契约无跨市场同一发行人的价格对照。对 601988.SH/0988.HK 这类标的，缺了最关键的相对价值锚。
- **指数纳入/剔除、ETF 持仓变动** —— `price_action_attribution_analyst.md:43` 明列 "ETF rebalancing" 为可补缺口，但无数据源。
- **行业量价数据**（面板价/锂价/运价/猪价）—— 周期股的领先指标，比财报早 1-2 季度。小米报告提到"存储涨价"作为利空，但无任何量化数据支撑。
- **可转债/期权行权稀释** —— 影响每股口径，`sharesOutstanding` vs `impliedSharesOutstanding` 可部分替代。

---

## 13. 中等：期权流数据不可解读（缺历史分位）

`options.txt`（BABA 实测）给出 ATM IV 50.5%、skew -5.6pp、PCR 0.19。

**问题：IV 绝对值无历史分位则无法解读。** 50.5% 对某些标的是极低（历史 20 分位），对另一些是极高（90 分位）。同理 skew 与 PCR 都需要相对自身历史的位置。当前分析师只能说"skew 为负 = 看涨期权更贵"，无法说"这是否异常"。

**这比 Not Rated 更危险**：数据**存在**（不是 placeholder），却因缺少历史基准而**不可解读**，LLM 会对着 50.5% 这个绝对值编造「IV 偏高，市场预期波动」的叙述。`price_action_attribution_analyst.md:8` 只规定了「No options attribution from placeholders」，管不到这种情况。

其他缺口（AAPL 实测数据）：

- **只取最近 2 个到期日，而实测 AAPL 有 22 个**（`options_flow.py:370` `expiry_count=2`），且是**顺序取前 2 个**而非跨期限选取。实测拿到 DTE 2 与 DTE 5，ATM IV 从 29.0% 降到 24.6% —— 这个 -4.4pp 斜率完全被事件日噪声主导，**无法反映真实期限结构**。而「近月 IV 高于远月」正是事件驱动定价的关键特征，需覆盖到次月/季月才能识别。
- **2 个样本不足以形成判断**：实测两个到期日的 PCR 差异显著（volume PCR 0.26 vs 0.34，**OI PCR 0.60 vs 0.21**），说明单一到期日读数极不稳定。
- **无 gamma exposure / max pain** —— `clean_chain` 已拿到全部 strike 的 OI（实测 call OI 182784、put OI 108959），算 GEX 与 max pain 只需在**现有数据上做加权求和，零额外请求**。这两个指标是解释「为什么价格在某个整数关口被钉住」的核心机制。
- **skew 数值极小无法判断异常** —— 实测 AAPL `iv_skew_pp` 为 +0.3pp / +0.5pp，无历史分位则无法区分「异常平坦」与「正常」。
- **无 IV vs 已实现波动率对比**（判断期权贵贱）。
- BABA 的 **3-DTE 期权**被用于推导"隐含区间 $121-135"并作为战术参考带（`analysis_report.md` L16）—— 3 天期权的隐含区间用于 **6-12 个月视野**的仓位决策，期限严重错配。
- **`_days_to_expiry` 用日历日而非交易日**（`options_flow.py:82-89`）。周五分析、下周一到期显示 DTE 3，实际只剩 1 个交易日的 theta/gamma 暴露。

**修复**：(a) `expiry_count` 提到 4-6 并**跨期限选取**（近月 + 次月 + 季月），而非顺序取前 2；(b) 用现有 chain 数据补算 max pain 与 GEX（纯计算，无成本）；(c) IV rank 需历史 IV，yfinance 无历史期权数据 —— **可行的最小方案是用标的 252 日已实现波动率(HV)作参照，输出 IV/HV 比值**，用现有 ohlcv 就能算；(d) 无历史分位时明确在 artifact 标注「IV 绝对值不可单独解读，仅可用于同日跨期限/跨行权价比较」；(e) DTE 改交易日或同时输出两者。

**另**：`fetch_data.py:1394-1397` 对非美市场写 `<options data unavailable ... Options Flow not rated>`。港股实际有活跃的股票期权与窝轮/牛熊证市场（HKEX 数据），CN 有 50ETF/300ETF 期权。当前措辞暗示「这些市场没有期权数据」，实际是「本工具未接入」—— 建议改措辞，避免分析师误以为该市场缺乏衍生品定价信息。

---

## 14. 中等：新闻层的结构性缺口

### 14.1 官方公告未进入新闻流

`official_filings.py` 抓到了 HKEX 的 3 份 PDF（业绩公告、年报），但 `llm_extraction_allowed: false` 且这些**公告标题没有进入 `news.txt` 的证据体系**。结果：分析师看不到"5月26日发布Q1业绩公告"这一事件本身，只能依赖 yfinance 新闻流。

实测后果（01810.HK 归因报告 L45,L158）：归因分析师判定"07-16后无小米专属盈利/指引事件"，把"单点意外触发"整体标为 Not Rated。但如果 HKEX 公告标题进入事件时间线，至少能确认披露事件的确切时点。

**修复**：把 official_filings 的标题 + 日期作为 `[Fxxx]` 类证据注入 `news.txt` 的事件时间线（仅标题 + 日期，不做 PDF 数值提取，不违反第8条政策）。

### 14.2 语言与来源覆盖失衡

实测：

- 01810.HK（港股）22条新闻，来源**全部英文**（IBD、WSJ、TechCrunch、Simply Wall St、GuruFocus 等），**零中文财经媒体**。一家中国公司的港股，主要信息流在中文（财新、21财经、证券时报、雪球），全部缺失。
- 601138.SH（A股）158条，全部 Sina Finance —— 单一来源，无交叉验证，且转载率极高（大量近重复）。
- 第一条新闻 `[N001]` 是"Tesla Rival BYD..."，与小米的相关性靠 LLM 打分过滤，数据层未做实体消歧。

**"Content Level: summary" 占比 22/22 = 100%**（01810.HK），说明有摘要，这点不错。但 summary 通常只有 1-2 句，`news_analyst.md` 的 evidence 规则严格限制"summary 只支持标题和所给摘要"，导致大量新闻实际只能做方向性打标，无法支撑深度论证。

### 14.3 HK 降级到新浪后 772 条噪声全量透传（实测）

`fetch_hk_news_raw` 在 yfinance 返回 <5 条时降级到新浪（`fetch_data.py:924`）。而 `process_and_write_news:1035-1039` 的逻辑是「HK/US 走 yfinance，质量高，跳过 `split_recent_and_history` 分层过滤」—— **这个前提在降级路径下已不成立，注释与实际行为脱节**。

**实测强制降级 00700.HK**：新浪返回 795 条，经 `filter_noise + dedup` 后**仍保留 772 条，写出 186KB 的 news.txt**。772 条标题级新闻会淹没 LLM 上下文，真正的关键公告被稀释。

配套问题：

- **噪声黑名单是硬编码个案补丁** —— `_NOISE_KEYWORDS` 里是「霍尔木兹」「周文强」「迪拜拟建新港口」这类针对特定历史批次的关键词；`_NOISE_PROVIDERS = ["某情感号","某社会号"]` 更是**占位符**（真实来源名不会长这样）。对新出现的噪声零覆盖。
- **`is_high_signal` 英文子串匹配导致大量假阳性**（`news_filter.py:191`）—— 实测 `"China detail campaign"` → True、`"Explain the rain"` → True（**"rain"/"detail" 内含 "ai"**）；反向地 `"贵州茅台召开股东大会"` → False（股东大会是重要公司行动却不在关键词表）。该函数只在 CN 的 8-30 天窗口生效，影响面有限，但方向是错的。
- **去重本身是安全的** —— `dedup_by_title` 是标题**完全一致**才去重（`news_filter.py:31`，实测保留最早一条）。**风险在噪声未删，而非关键项被误删。** 但其实现用 `seen[key] is art` 做**对象身份比较**（`:46-47`）—— 若上游传入等值的不同对象副本（如 yfinance + Sina 合并后做过 dict 拷贝），身份比较会失配导致整组被丢弃。改为记录索引集合更稳健。
- **`SEC_USER_AGENT` 缺失时静默 unavailable**（`official_filings.py:251`）—— 美股 8-K 通道整个失效但只在 artifact 里留一行文本，用户看不出是环境配置问题。

**修复**：(a) 让降级标志传递到 `process_and_write_news`，走新浪来源时**强制启用** `split_recent_and_history`（不论 market）；(b) news.txt 加条数上限（如 80 条）并按信号强度排序，超出部分只保留标题清单；(c) `is_high_signal` 英文匹配改词边界正则 `\bAI\b`；(d) HK 补智通财经/格隆汇（港股专业媒体）；(e) `SEC_USER_AGENT` 缺失时在 `data_quality` 升级为显式告警。

### 14.4 社交情绪始终 Not Rated

三份报告全部 `Social Data Available: false`。这个角色（Social Media Analyst）在所有实测中都只输出"Not Rated + 新闻叙事观察"，**实际贡献接近于零**，但仍占一个完整 Agent 调用（约 5-8k tokens）。

**建议**：要么接入真实社交数据源（雪球/StockTwits/Reddit/微博财经），要么把该角色合并进 News Analyst 作为一个 section，省下一次 Agent 调用。当前形态是纯开销。

---

## 15. 中等：宏观与预测市场的相关性问题

### 15.1 抓 6 个序列，但字典里已定义 22 个 —— 16 个从未取（实测确认）

`macro_data.py:85-92` 的 `DEFAULT_INDICATORS` 只取 6 个（联邦基金利率、10Y、期限差、CPI、核心CPI、失业率），**全部是美国数据**。而 `MACRO_SERIES` 字典里定义了 22 个，**16 个已定义的序列从未被抓取**：

`VIXCLS`(VIX)、`DTWEXBGS`(美元指数)、`M2SL`、`T10YIE`(通胀预期)、`PAYEMS`(非农)、`ICSA`(初请)、`PCEPILFE`(核心PCE)、`DGS2`(2年期)、`INDPRO`、`UMCSENT`、`RSAFS`、`HOUST`、`GDP/GDPC1`、`DGS30`。

**VIX 和美元指数是最不该缺的**：
- VIX 是全市场风险偏好的单一最优代理。`price_action_attribution_analyst.md:101` 明确要求判断 "broad risk-on/risk-off moves" —— 没有 VIX 就只能靠指数涨跌猜。而 01810.HK 报告的主归因恰恰是「系统性 co-risk-on」（B级 Medium），**有 VIX 本可以把这个归因从 B 级升到 A 级**。
- 美元指数直接驱动港股/新兴市场资金流向。

两者都已在字典里，**加进 `DEFAULT_INDICATORS` 是一行改动**。

**完全未定义的重要缺口**：信用利差（`BAMLH0A0HYM2` 高收益债利差 —— 衰退与信用紧缩的领先指标）、PMI（FRED 有 `NAPM` 系列）。

**中国宏观几乎空白**：A股/港股需要社融、信贷脉冲、M2 同比、中国 PMI，FRED 覆盖极差。当前 CN 只有 `fetch_cn_global_news` 抓百度经济日历（`fetch_data.py:1093`），是**事件日历而非时间序列**，无法做趋势判断。

实测 01810.HK 报告用 "10Y 收益率 4.75% 高位" 论证折现率压力（L83）—— 对一家港股中国公司，中国 10Y 国债与港元 HIBOR 的相关性远高于美债。

**修复**：(a) `DEFAULT_INDICATORS` 立即加 `vix`、`dollar_index`、`core_pce`、`2y_treasury`（**字典已有，零成本**）；(b) 补 `BAMLH0A0HYM2` 信用利差；(c) 按 market 分流 —— CN/HK 标的额外抓中国宏观（akshare `macro_china_*` 已可用）。

**FRED_API_KEY 缺失时整体降级为 Not Rated** 的设计是对的。

### 15.2 Polymarket 三个固定话题近乎零价值，风险却是全流程崩溃

`prediction_markets.py:51-55` 的 `DEFAULT_TOPICS = ["Fed rate cut", "recession", "US election"]` 全是美国宏观/政治，与个股基本面无因果链条。"US election" 在非选举年更是纯噪声。而 FRED 的利率序列已把「降息预期」表达得更精确（市场定价 vs 预测市场定价，前者深度高几个数量级）。

实测三份报告中，预测市场数据基本未影响任何结论 —— 但它占用 token 预算、产生「看起来量化」的伪信息（LLM 容易把 76% 的降息概率写进论证链），**同时（结合 §9）承担让整个 pipeline 崩溃的风险**。风险收益完全倒挂。

**修复**：修完 §9 后降级为可选（默认关闭），或按标的行业动态生成话题（半导体股查「chip export controls」、药企查「FDA approval」）。若保留，必须在 artifact 标注「宏观话题，与个股无直接因果关系，不得作为个股论证的支撑证据」。

### 15.3 Longbridge Sankey 的 `translated_only` 影响面比标注更广

`longbridge_fetcher.py:374-386` 老实声明了 `status: "translated_only"`、`prohibited_uses: ["official_operating_growth", "cross_currency_valuation"]` —— **这个诚实度是好的**。但实测影响被低估：

**实测 00700.HK：`info.currency=HKD` 而 `info.financialCurrency=CNY`** —— 腾讯报表以 CNY 计价、股价以 HKD 计价。长桥 Sankey 给的是「presentation currency」但**不说明是哪个、也不给汇率**。于是 `normalize_revenue_sankey` 计算的 `qoq`/`yoy`（`:324-331`）是在**未知币种**上做的同比 —— 如果长桥在不同期间用了不同换算汇率（常见于按当期汇率折算的展示口径），这个「增长率」里**混入了汇率变动，不是真实经营增长**。

**语义冲突**：元数据 `prohibited_uses` 写了 `official_operating_growth`，但 `quarterly_growth_semantics` 又把 qoq/yoy 描述为「locally calculated」，看起来像是可信的 —— 两处自相矛盾。

`gross_segment_mix_percent`（占比）不受影响（同期同币种相除），这部分安全。

**专业影响**：分部增速是分部分析的核心输出。当前提供了一个「看起来精确到 6 位小数」但可能含汇率噪声的数字。对腾讯这类 CNY 报表/HKD 股价的标的，**季度汇率波动 1-2% 会直接进入分部增速**。01810.HK 报告中的 `Smart EV +133%→+13%` 正是这类数字，且被用作评级核心论据。

另：`_SEGMENT_ALIASES`（`:510-523`）只硬编码了阿里/腾讯两家的分部别名，其他标的的新闻-业务线匹配无法工作。

**修复**：每个 `qoq`/`yoy` 字段旁加 `currency_confidence: "translated_only"` 标记，`judgment_basis` 明确「分部增速含潜在汇率折算噪声，量级判断可用、精确数值不可引用」；理想方案是从 `official_filings`（HKEX 原始财报）交叉校验一个季度的分部收入以确认口径。

---

## 16. 中等：工程可靠性

### 16.1 零缓存 + 重复抓取 + 零并发（均已实测/核对）

**零缓存**：`official_filings.py` 每次运行重新下载 `company_tickers.json`(约1MB)、`submissions`、**`companyfacts`(大型申报人 50-150MB)**；`data_validation.py:48-82` 每次重拉 5 张分析师表 + info + history_metadata。同一 ticker 反复分析（调试、重跑）无任何复用。

更严重的是 **SEC companyfacts 全量 TOON 往返校验**：`structured_io.py:51-60` 会 `json.dumps → json.loads → encode → decode(strict) → 完整深度比较`，峰值内存约原始体积 4-6 倍。100MB 输入即数 GB。

**价格数据被完整抓两次**：`fetch_ohlcv:308` 和 `fetch_indicators:337` 各自调用 `fetch_price_data`，参数几乎相同（`price_start`→`curr_date`）。**同一份数据抓取两遍，包括可能的 Longbridge 回补**。改为抓一次传参即可省掉一整轮网络往返。

**`yf.Ticker(...).info` 被调用 4-6 次**：`fetch_data.py:149`（HK 变体解析，最多 5 次）、`:500/:503`（fundamentals）、`data_validation.py:53`、`price_attribution_data.py:440`。`info` 是最重的 yfinance 端点，**无任何缓存层**。

**零并发**：15 个抓取步骤严格串行（`fetch_data.py:1327-1604`）。其中 `fetch_global_news`（`:441-453`）内部 4 个 yfinance Search 顺序执行；`_sina_fetch_all_pages` 最多翻 20 页顺序请求（实测 00700.HK 抓到 795 条，说明真的翻了很多页）。这些之间**无任何依赖，完全可并发**。news / macro / prediction / options / segments 五组可完全并行。

**HK 变体重试成本高**：`_hk_ticker_variants('00005.HK')` 实测生成 5 个变体，`resolve_hk_ticker` 对每个都调 `info`，`_yf_hk_call` 也对每个变体重试 —— **最坏 5 变体 × 4 重试 = 20 次调用**。实测 00005.HK 时 `005.HK`/`05.HK`/`5.HK` 全部 404（三次无谓的完整重试）。

**重试延迟放大**：`RetryPolicy()` 默认 4 次尝试、1s 起指数退避，**单个必然失败的调用要睡满 7 秒**。串行 × 多个失败点 → 断网场景下整个 pipeline 会挂很久才降级完成。且 yfinance 的 `history()` **无 timeout 参数**（已核对签名），底层依赖 requests 默认（**无限等待**）。

**修复**：(a) `ThreadPoolExecutor` 并行化互不依赖的 5 组步骤；(b) `fetch_price_data` 结果复用，消除重复抓取；(c) `Ticker.info` 加进程内 memo cache（key = 已解析 symbol）；(d) `resolve_hk_ticker` 一旦某变体 404 就跳过其余更短变体（前置零剥离到 404 说明方向错了）；(e) 重试策略按重要性分级 —— news/prediction 用 `max_attempts=2`，price/financials 保持 4；(f) 按 `(provider, operation, analysis_date)` 做文件级 TTL 缓存（SEC facts 与 ticker map 可缓存 24h）；(g) SEC facts 在 `_sec_filings` 里就地裁剪到实际使用的 5 个概念后再返回。

**做得对的**：`is_retryable` 能正确识别 yfinance 的 `YFRateLimitError`（实测返回 True）；每步独立 try/except、产物各自退化的降级架构比多数生产系统严谨 —— **§9 是这套架构唯一的破口**。

### 16.2 零限速

`provider_runtime.py` 只有失败退避，**无任何 QPS 控制**。

- **SEC**：Fair Access 上限 10 req/s。`SEC_USER_AGENT` 作为硬前置（`official_filings.py:251-260`）做得对，但无速率限制。单标的 3 请求尚安全，批量跑多标的会触发封禁。
- **HKEXnews**：HTML 抓取，无 robots.txt 检查、无 QPS、无 `Retry-After` 处理，UA 半伪装（`Mozilla/5.0 stock-analysis-debate/1.0`）反而更可疑。HKEX 无公开授权抓取 API，属合规灰区。
- **CNINFO**：直接 POST 未公开内部接口 `/new/hisAnnouncement/query`，带 `X-Requested-With` 伪装 AJAX，无限速。巨潮有反爬且该接口非公开授权。

**修复**：per-provider 令牌桶（SEC 5/s、HKEX/CNINFO 1/s）；支持 429 的 `Retry-After` 头（当前识别 429 但忽略该头）；README 明示 HKEX/CNINFO 抓取的合规责任。

### 16.3 CNINFO orgId 构造是猜测，深交所标的大概率失败

`official_filings.py:194`: `org_id = ("gssh" if is_shanghai else "gssz") + code.zfill(7)`

上交所侧大致成立（601988 → `gssh0601988`）。**深交所侧不成立** —— 巨潮的 szse orgId 非机械拼接，大量标的用历史遗留独立 ID。构造错误时接口返回**空 announcements 而非报错**，于是返回 `status="partial"`，**看起来像"该公司无公告"，实际是查询参数错了**。

同类问题：HKEX 的 validator 只检查 `"titleSearchResultPanel" in value`，**空结果面板也含该字符串**，于是通过校验但 records 为空，同样伪装成"无公告"。且 `records[:12]` 依赖 HTML 行序为时间倒序（未排序）、未去重（同一公告多附件链接会挤占配额）。

**"partial 伪装成无数据"是本项目最隐蔽的一类失败**：它不触发任何 gate，不产生 warning，下游看到的是"这家公司没有官方公告"。

### 16.4 `_EVENTS` 全局可变态非线程安全

`provider_runtime.py:22`: `_EVENTS: list[dict] = []`，无锁，无上限。当前全流程串行所以侥幸正确。但 **30+ 个独立网络调用完全串行**（最坏每个 4 次重试 + 最多 8s 退避）是显然的下一步优化，一旦并发化立即产生事件交错与竞态。

### 16.5 交易日历只跳周末 + 最新一根 K 线可能是盘中未完成 bar

`fetch_data.py:223-228` 的 `_latest_expected_weekday` **不含交易所节假日**（春节、国庆、圣诞、感恩节），三个市场假期完全不同。假期后首个交易日 `data_fresh=False` 并写 WARNING（`:1215`），但数据其实是完整的 —— 假日误报会让分析师对正常数据产生不必要的怀疑。周末逻辑本身是正确的（`test_kline_fallback.py:203` 已覆盖 2026-08-02 周日 → 期望 07-31）。

**更隐蔽的问题：盘中未完成 bar 无任何标记（实测）**。美东 2026-08-05 12:05（盘中）实测：yfinance 返回 `2026-08-05 Close=308.795 Volume=20622479`，而收盘后长桥同日 `Volume=19190844` —— **这是一根盘中 bar**。两次连续调用的 Close 还在变（308.070 → 308.795 → 307.930）。`fetch_data.py:285` 的过滤条件是 `fallback.index <= end`（包含分析日当天），所以**盘中运行时最新 bar 一定是未完成的**。而 `data_quality` 只判断日期是否匹配（`:1177`），**不判断 bar 是否完整**。

影响：盘中运行时 1 日收益率、最新指标值都基于未完成数据；实测成交量差异约 7%，尾盘前差异会更大。建议 `data_quality` 加 `latest_bar_intraday: bool`（用「市场是否已收盘」+「成交量是否显著低于 20 日均量」双重判断）。

**同类时点问题**：`financial_audit.py` 的 `price_date`（OHLCV 最大日期）与 `data_validation.py` 的 FX `rate_date` **从不比较**，且 FX 的 stale 阈值是 7 个日历日，于是**最多 7 天的价格/汇率错配都会被标为 verified**。汇率跳动日（CNY 中间价调整、HKD 触及弱方保证）会直接污染 P/B、EV、市值。修复：`abs(price_date − rate_date) <= 1 交易日` 才允许 `currency_ready = True`。

### 16.6 其他

- `structured_io.py:31-35` 的 `default=str` 会把 `np.int64(5)` 静默变成字符串 `"5"` —— 在"类型化契约"里是严重类型污染。（`allow_nan=False` 对 NaN 抛错这点是真 fail-closed，做得对。）
- `structured_io.py:83-98` 格式回退可能读到**上一轮遗留的旧文件**，无 mtime/analysis_date staleness 校验。实测 BABA 目录同时存在 `revenue_sankey.csv`(01:45) 与 `revenue_sankey.json`(10:25)，相差 8.7 小时 —— 这正是该风险的实例。
- 重试分类依赖错误消息子串匹配（`"rate limit"` 等），会对永久性错误重试 4 轮；yfinance 吞掉 HTTP 错误后返回空 dict，走 `ResponseValidationError`(恒 retryable)，于是**对已退市/无效 ticker 也重试 4 次退避约 15 秒**，多调用叠加使无效 ticker 耗时数分钟。
- **`akshare` 未声明为依赖** —— `fetch_data.py:1091/1112` 直接 `import akshare as ak`，但 `requirements.txt` **无 akshare**（已核对）。本机恰好装了 1.18.55 所以能跑，**干净环境下 CN 宏观新闻会静默降级**为 `# Note: CN economic calendar unavailable: No module named 'akshare'`（`:1108`）—— 错误被吞进产物文本，用户看不出是环境问题还是数据源问题。且 §12.5 建议的 akshare 数据源都依赖它。
- **三个新闻函数是完全死代码（约 200 行）** —— `fetch_data.py:388` `fetch_news`、`:635` `fetch_cn_news`、`:766` `fetch_hk_news`，全库检索确认**除定义处外零引用**（`main` 走的是 `*_raw` + `process_and_write_news` 链路）。与 `_raw` 版本逻辑重复（同样的新浪正则、同样的东财 API），维护时容易改错分支。**（按项目规范仅提示，不建议我方擅自删除。）**
- **`fetch_global_news` 的 4 个查询实际只用第 1 个** —— `:441-462` 循环内 `if len(all_news) >= limit: break`，而 `limit=10` 且每个 query 用 `news_count=limit` —— **第一个查询就凑满 10 条，后 3 个 query（"Federal Reserve interest rates"、"inflation economic outlook"、"global markets trading"）通常永远不执行**。宏观新闻的话题覆盖实际只有 "stock market economy" 一个，比代码看起来窄得多。
- `_yf_news_to_list` 内部 `pd = datetime.fromisoformat(...)`（`:1005`）**遮蔽了模块级 `import pandas as pd`**（`:43`）。当前函数体内不再用 pandas 所以不崩，但极易在后续修改中引入 `AttributeError`。改名 `pub_dt`。
- `data_validation.py:74` 抓取 `growth_estimates` 但从未使用 —— 一次白费的网络调用（含最多 4 次重试）。
- `data_validation.py` 三处 `except Exception: <空值>` 效果上是 fail-closed，但**契约中不留错误痕迹**，无法区分"provider 挂了"与"该标的确实无此元数据"。
- 5% 调节容差（`RECONCILIATION_TOLERANCE`）对 EPS 过松 —— 5% 的 EPS 偏差足以改变估值结论。建议 EPS 用 1-2%。

---

## 17. 中等：Prompt 层问题

### 17.1 未填充的占位符会原样进入 LLM 输入

`prompts/` 中有 30 个 `{placeholder}`（`{market_research_report}`、`{past_memory_str}`、`{history}`、`{trader_decision}` 等）。

`SKILL.md:440` 规定 "Prompt files contain the exact prompts. Do NOT paraphrase or improve them. **Pass verbatim**"，而 `SKILL.md` 全文**没有任何地方说明这些占位符如何填充** —— 按 rule 13（上下文卫生）设计，子代理是自己读文件的，所以这些占位符**永远不会被替换**。

LLM 实际会读到字面的 `Market research report: {market_research_report}`，这是从原 TradingAgents 框架（Python 用 `.format()` 填充）继承下来的死代码。轻则浪费 tokens 与制造困惑，重则 LLM 尝试"寻找"一个不存在的变量。

`{past_memory_str}` 尤其明显 —— 本项目**没有 memory/reflection 机制**（目录中无 memory 相关文件），但 `bull_researcher.md`、`trader.md`、`research_manager.md`、`portfolio_manager.md` 全都要求"应用过往经验教训"。

**修复**：删除全部占位符块，改为"从 {REPORT_DIR} 读取你需要的报告"。若要保留 memory 机制，需真正实现（跨运行的 reflection 文件）。

### 17.2 `market_analyst.md` 描述的是不存在的工具

该提示词说 "please make sure to call **get_stock_data** first... Then use **get_indicators**"、"When you tool call, please use the exact name of the indicators... otherwise your call will fail"。

**这些工具不存在**。本 Skill 的架构是 Phase 1 预先生成 `indicators.txt`，分析师用 Read 读文件。提示词还要求分析师"从列表中选择最多 8 个指标" —— 但 13 个指标已经全部算好写在文件里了，无从选择。

这同样是从 TradingAgents 框架继承的未适配残留。会导致分析师尝试调用不存在的工具、或对自己的角色边界产生误解。

### 17.3 `fundamentals_analyst.md` 也引用不存在的工具

"Use the available tools: `get_fundamentals`... `get_balance_sheet`, `get_cashflow`, `get_income_statement`" —— 同样不存在。

### 17.4 `data_policy.md` 缺关键禁令

当前 10 条政策禁止"copy a blocked/raw provider value"，但**没有禁止"从原始 CSV/statement 自己算出一个工具已判定 unavailable 的指标"**。§1.1 的小米 TTM EPS=1.51 正是钻了这个空子。

建议新增：

> 11. 若某 metric 在契约中 status 为 unavailable，禁止用任何原始文件（income_stmt.csv 等）自行重建该指标。工具拒绝提供即为最终结论。
> 12. 任何跨币种运算必须使用契约的 dated FX rate 并显示该 rate 与日期。若契约中已有该比率的成品值（如 point_in_time_pb），必须使用契约值，不得自算。

---

## 18. 做得好的部分（应保留）

1. **归因分析框架**（`price_action_attribution_analyst.md`）—— 六步模型 + 12 条硬证据规则 + A/B/C/Rejected/Not Rated 分级 + 强制至少一个备选假说 + 事件日与发布日分离 + "超卖是状态非催化"。这是专业事件研究的标准做法，实测输出质量高（01810.HK 归因报告正确识别"加速段无公司新闻"、正确把逼空标为 Plausible/Not Rated、正确拒绝凭熟悉感自造 peer set）。**这是本项目最有价值的资产。**

2. **上下文工程**（rule 13 + On-Demand Read Protocol）—— 每个分析师直写文件只返回一行确认、下游按需读取、禁止把文件内容粘进 prompt、禁止重读已在上下文的文件。实测 3 份完整分析（每份含 11 个 Agent 调用、约 200KB 中间产出）能在单会话跑完，这个设计是关键。

3. **辩论机制的真实性** —— 实测 `debate_history.md` 与 `risk_debate_history.md` 中有 17 处真实立场修正（Aggressive Round 2 把"现价 9%"改为"回踩 27.48 企稳后 9%"；Conservative 承认"中性派双向通道优于单边 15%，我认它的一半"）。这不是表演性辩论，双方确实在互相校验数据口径（多方指出"EPS 崩塌是数据源串口"、空方反驳"GAAP 11.59% 是一年前单季"）。**Bull/Bear 的口径互查实际上抓出了工具层的真实 bug**，这个机制的价值被低估了。

4. **仓位算术完整性约束** —— 五个角色（research_manager / trader / 三个 risk debator / portfolio_manager）全部要求输出 Stage/Trigger/增量/累计 表格、要求累计=增量之和≤最大仓位、要求"达到上限后不得再有档位"、要求"资金未知则 Capital/Shares 输出 N/A 不得虚构"。实测 01810.HK 的算术验证声明（L103）完整正确。这类约束很少见但极有必要。

5. **Not Rated 的诚实披露** —— 三份报告的 Data Caveats 都实事求是地列出了缺失证据（社交、期权、南向资金、同业、事件前共识）。系统不假装自己知道它不知道的东西，这在同类项目中罕见。

6. **点时护栏 (Point-in-Time Guardrail)** —— `expectations.txt` 明确标注"检索时点快照不能证明事件前预期，历史分析日下为 Not Rated"。这是防止事后归因的关键设计，且实测辩论中被正确引用（多方的 Target 39.x 论据被以此降级）。

7. **失败降级的粒度** —— `segments_fetch_failed.flag`、per-topic 预测市场降级、per-series FRED 降级、comparator 独立降级。ONE-RETRY 政策（rule 14，最小粒度重试一次、失败即停）比无限重试或整体重跑都更合理。

8. **148 个单测全部通过**，`structured_io` 有 schema_version，TOON/JSON 双格式且禁止混用。

---

## 19. 优先修复顺序（按投入产出比）

### P0 — 单点崩溃与数据污染（最小改动，最大风险消除）

| # | 修复 | 文件 | 改动量 |
|---|---|---|---|
| 0a | **`except` 加 `ValueError`**，消除全 pipeline 崩溃（§9） | `prediction_markets.py:208` + `fetch_data.py:1450` | **1 行** |
| 0b | **A股成交量单位归一化** `amount × 100`，消除 VWMA/MFI 100 倍污染（§8） | `longbridge_fetcher.py:90` | 数行 |
| 0c | **`PRICE_LOOKBACK_DAYS` → ≥550**，恢复 200SMA 趋势判断与 YoY 基期（§10） | `fetch_data.py:73` | **1 行** |
| 0d | **HK sector proxy 换 `3033.HK`**（`^HSTECH` 实测 404），恢复港股科技行业超额（§11） | `price_attribution_data.py:59` | **1 行** |
| 0e | **CSI300 换 `510300.SS`**（`000300.SS` 实测缺 12 天），恢复 A股标准基准（§11） | `price_attribution_data.py:24` | **1 行** |

### P1 — 让契约真正生效（不做这些，其他优化都是在错误数字上做优化）

| # | 修复 | 文件 | 影响 |
|---|---|---|---|
| 1 | **gate 从 metric status 反推**，不读 raw dict | `data_validation.py:372-382` | 单点修复，消除 3 个 fail-open |
| 2 | **新增确定性报告校验器**（Phase 7.5，Python）：扫描 `analysis_report.md` 数字 vs 契约，违规则拒绝 | 新文件 + `SKILL.md` | 唯一能闭环的强制执行层 |
| 3 | **`data_policy.md` 补 2 条禁令**（禁止重建 unavailable 指标 / 强制使用契约成品值） | `prompts/data_policy.md` | 堵住 §1.1 的具体漏洞 |
| 4 | **删除 `financial_currency` 的 estimate fallback** | `data_validation.py:91-93` | 消除"自信地算错" |
| 5 | **`currency_metadata_missing` 不得为 "complete"**，`main()` 要求币种 | `financial_audit.py:214-218, 388-401, 552` | 消除 FX=1.0 的 complete 报告 |
| 6 | **mismatch 时不输出 "Preferred" 错值**，改 N/A + 原因 | `financial_audit.py` | BABA 类问题的根治 |
| 7 | **`allow_segment_growth` 与 `segment_analyst.md` 二者取一** | 两处 | 消除制度性诱导越界 |

### P2 — 修正估值口径（影响所有数字的正确性）

| # | 修复 | 文件 |
|---|---|---|
| 8 | EV 加回少数股东权益/优先股/永续债，租赁负债披露；`EBITDA > 0` 才算；**金融业强制关闭 EV/EBITDA gate** | `financial_audit.py:240-251` |
| 9 | TTM 支持半年报频率（恢复 HK/CN 大量标的能力）；期间解析改 `pd.to_datetime` | `financial_audit.py:103-115` |
| 10 | **ADR/ADS 比例检测**（股数口径不一致 >2x 时置 N/A） | `financial_audit.py` |
| 11 | price_date 与 fx rate_date 一致性校验（≤1 交易日） | `data_validation.py:130-161` |
| 12 | 跨币种时 `ttm_pe_difference` 不参与 mismatch 判定（避免污染正确值） | `financial_audit.py:276` |
| 13 | 补齐已算但未进契约的 13 个 metric（市值/BVPS/净债务/EV/GAAP营业利润率/forward EPS 等） | `data_validation.py:290-346` |
| 14 | 复权口径显式声明；清理 `Adj Close` 死代码；`data_quality` 加「估值须用未复权价」约束 | `fetch_data.py:312/318/348-352` |

### P3 — 用好"已经拿到但没用"的数据（最高杠杆，改动 <50 行，零新依赖）

| # | 数据 | 现状 | 解锁什么 |
|---|---|---|---|
| 15 | **现金流量表指标族**（OCF/CapEx/FCF/**OCF÷净利润**） | `cashflow.csv` 已抓，两个分析模块**零引用** | 盈利质量的第一道防线 |
| 16 | **short interest**（`info.sharesShort`/`shortRatio`/`shortPercentOfFloat`） | `info` 已在调用，**从未读取** | **直接解锁"No short squeeze without short evidence"这条空转的硬规则** |
| 17 | **`Ticker.calendar`**（下次财报日 + 下期 consensus + 除息日） | 从未调用 | 报告反复引用"Q2财报"却无日期；持仓期限决策的第一要素 |
| 18 | **VIX + 美元指数 + 核心PCE + 2Y**（`macro_data.py` 字典已定义） | 22 个序列定义，只取 6 个 | **有 VIX 可把「系统性 co-risk-on」归因从 B 级升到 A 级** |
| 19 | **beta 调整的异常收益** | `info.beta` 已抓，`price_context` 60日序列已在手 | 修正归因框架的实质方法论缺口 |
| 20 | **max pain + GEX** | `clean_chain` 已有全部 strike 的 OI | 解释"价格被钉在整数关口"的核心机制，纯计算 |
| 21 | **杠杆比率**（净债务、净债务/EBITDA、利息覆盖） | 所有分量都在 `financial_audit` 里 | 只需做减法和除法 |
| 22 | **换手率 + 52周位置 + ADX + OBV** | `floatShares`/`52w High/Low` 已抓未用；OHLCV 在手 | 回答"量能是否配合"和"趋势市 vs 震荡市" |
| 23 | **`Ticker.dividends`/`splits`/`institutional_holders`** | 从未调用 | 分红连续性、股本变动、13F 轻量替代 |
| 24 | **官方公告标题注入事件时间线**（`[Fxxx]`，仅标题+日期） | HKEX 已抓 3 份 PDF，完全未用 | 不违反第8条政策 |

### P4 — 需新数据源（按 ROI 排序，多为免费公开数据）

| # | 数据 | 理由 |
|---|---|---|
| 25 | **港股通南北向资金 + 融资融券余额 + 卖空比例**（akshare 已装） | 免费日频；直接填补归因框架"Amplifier"环节在 HK/CN 的空洞；解锁"No forced-liquidation without leverage evidence" |
| 26 | **同业可比估值表** | 三份报告全部 Not Rated；相对估值是基本工具；不给数据则 LLM 有编造 peer set 的风险 |
| 27 | **中国宏观序列**（PMI/社融/M2/LPR，akshare `macro_china_*`）+ 信用利差 `BAMLH0A0HYM2` | 现有 6 个美国序列对 HK/CN 标的解释力弱 |
| 28 | **大宗交易/龙虎榜**（akshare）、**股东增减持/解禁时间表** | A股席位级资金证据；港股/A股最主要的供给冲击来源 |
| 29 | **行业量价数据**（面板价/锂价/运价） | 周期股领先指标，比财报早 1-2 季度 |
| 30 | **中文财经媒体源**（智通财经/格隆汇/财新） | 港股/A股的主要信息流在中文，当前全缺 |

### P5 — Prompt 清理与工程加固

| # | 修复 |
|---|---|
| 31 | 删除 30 个未填充占位符；删除 `market_analyst.md`/`fundamentals_analyst.md` 中不存在的工具调用指令 |
| 32 | 决定 memory/reflection：真正实现，或从 4 个 prompt 中删除 `{past_memory_str}` 相关要求 |
| 33 | Social Media Analyst：接入真实数据源，或合并进 News Analyst（省一次 Agent 调用） |
| 34 | HK 降级到新浪时**强制启用分层过滤**；news.txt 加条数上限；`is_high_signal` 改词边界正则 `\bAI\b` |
| 35 | 实现 official vs provider 交叉校验并真正赋 `status="conflict"`（当前是死代码） |
| 36 | `fetch_price_data` 结果复用（消除重复抓取）；`Ticker.info` 加 memo cache；5 组步骤并行化 |
| 37 | per-provider 令牌桶限速 + 429 `Retry-After` + 文件级 TTL 缓存；重试次数按数据重要性分级 |
| 38 | SEC companyfacts 就地裁剪后再落盘（避免 GB 级 TOON 往返） |
| 39 | CNINFO orgId 先查 topSearch 再用；HKEX validator 改为检查结果行存在、按日期排序、按 URL 去重 |
| 40 | 交易所交易日历（`pandas_market_calendars`）；`data_quality` 加 `latest_bar_intraday`；`structured_io` 格式回退加 staleness 校验 |
| 41 | `_EVENTS` 改 thread-local + `deque(maxlen)`；`structured_io` 的 `default=str` 改显式白名单 |
| 42 | 期权：`expiry_count` → 4-6 且跨期限选取；加 IV/HV 比值；DTE 改交易日；禁止 DTE<7 隐含区间用作中长期参考带 |
| 43 | `akshare` 加入 requirements.txt；`_yf_news_to_list` 的 `pd` 改名；`RECONCILIATION_TOLERANCE` 对 EPS 收紧到 1-2%；删除未使用的 `growth_estimates` 抓取；`fetch_global_news` 的 4 个 query 各取 `limit//4` |
| 44 | 提示三个死代码新闻函数（约 200 行，`fetch_data.py:388/635/766`）—— 建议确认后删除 |

---

## 20. 三点结构性建议

### 20.1 契约层与执行层之间缺一个验证层

当前架构的根本张力是：**契约层是确定性的（Python），执行层是概率性的（LLM），中间没有验证层。**

`SKILL.md:309` 主动删除了 LLM 验证器，理由正确（"Numeric validation has already completed deterministically in Phase 1"）—— 但 Phase 1 验证的是**输入数据**，没人验证**输出报告**。LLM 可以拿到完美的契约然后写出违反它的报告，而这正是实测发生的事。

建议补上闭环：

```
Phase 1:   确定性数据验证  → validated_metrics + gates
Phase 2-6: LLM 分析与辩论
Phase 7:   LLM 综合 → analysis_report.md
Phase 7.5: 确定性报告校验  ← 缺失的一环
           - 提取报告中所有数字（正则）
           - 每个数字必须能在 validated_metrics 中找到，或是契约值的简单算术结果
           - 任何 gate=false 对应的声明类型出现 → 拒绝
           - 违规则输出 violations.md 并要求 Phase 7 重写（一次）
```

这个校验器不需要理解语义，只需做数字集合的包含关系检查 + 关键词匹配（"目标价"/"P/E"/"target price"），就能抓住本次评估发现的全部 §1 违规。约 200-300 行 Python。

**没有这一层，所有契约设计都只是建议，而不是约束。**

### 20.2 artifact 需要区分三态，而非两态

当前 artifact 只有 `available` / `not_rated` 两态。但实测暴露了第三种状态，且它最危险：

| 状态 | 例子 | LLM 的实际行为 |
|---|---|---|
| `available` | 契约里的 `point_in_time_pb: 2.472 (verified)` | 正确使用 |
| `not_rated` | `options.txt` 的 HK 占位符 | 正确标 Not Rated |
| **`available_but_uninterpretable`**（缺失的一态） | **未 beta 调整的超额收益**（§11）、**无历史分位的 IV 绝对值 50.5%**（§13）、**含汇率噪声的分部增速**（§15.3） | **当成硬事实使用并编造解读** |

第三类数据「存在」（不是 placeholder，通过了所有 gate），但口径有偏或不可解读。`price_action_attribution_analyst.md:8` 只规定「No options attribution from **placeholders**」—— 管不到这种情况。

建议在 artifact 层面显式增加这一态，并在 `data_policy.md` 规定：`available_but_uninterpretable` 的数据只能用于同日跨期限/跨行权价的**相对**比较，不得作为绝对水平的判断依据。

### 20.3 提示词的严谨性目前反而放大了数据缺口的伤害

`price_action_attribution_analyst.md` 写了 12 条硬证据规则（无基准不谈超额、无空头数据不谈挤压、无杠杆数据不谈强平）—— 这些规则本身很专业。但抓取端不提供 short interest / margin / peer comps，导致这些规则**只能永远输出 Not Rated，形同虚设**。

而 §12.4 的实测证明：**`info.sharesShort`、`shortRatio`、`shortPercentOfFloat` 全部已在返回的 `info` 里，零额外请求，但代码从未读取。** 一条被写得很严谨的硬规则，因为漏读一个已到手的字段而永久空转。

这指向一个模式：**本项目的最高杠杆修复不是接新数据源，而是「用好已经拿到的数据」**。P0 五项全是 1 行到数行的改动，P3 十项全部零新依赖。这些加起来能覆盖大部分专业缺口，改动量远小于接入新数据源。

---

*本评估未修改任何被评估的文件。所有数字经独立复算验证，数据层结论经真实网络调用实测（2026-08-05/06，AAPL / 00700.HK / 600519.SH / 00005.HK）。*
