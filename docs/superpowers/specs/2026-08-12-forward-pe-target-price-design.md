# Forward P/E 目标价与网络估值证据设计

## 背景

当前目标价 gate 复用了 Trailing P/E 的 TTM EPS、当前 P/E 和普通股/摊薄平均股数检查。该依赖会把 ADR 的预测 EPS、报价币种和财报币种混在一起，导致即使下一财年一致预期可用，目标价仍被错误关闭。

本次实现只落地已确认的 Forward P/E 方法：

```text
Forward EPS（下一财年一致预期）
× 可比公司 Forward P/E 的 P25 / P50 / P75
= Bear / Base / Bull Price Target
```

P25、P50、P75 分别对应低分位、中位数和高分位。示例中的 `32.14 USD/ADR`、`4.8x / 6.1x / 8.0x` 和三档价格只作为报告格式示例，不能写死到工具中。

## 设计决策

### 1. 目标价与 TTM 估值解耦

- `allow_exact_pe` 继续表示当前时点 Trailing P/E，仍需要连续四个财季。
- `allow_target_price` 改为独立的 `forward_eps_x_peer_forward_pe_percentiles` gate。
- Forward P/E 目标价不再依赖 `statement_ttm_diluted_eps`、`point_in_time_pe`、TTM 连续性或普通股数/摊薄平均股数比值。
- 但目标价仍必须有正的下一财年 EPS、明确的报价币种/单位、ADR/ADS 或普通股口径，以及可复核的可比公司倍数。

### 2. 网络搜索产物是证据，不是模型自由输入

每次当前研究在 Phase 1 先通过网络搜索建立 `valuation_consensus.toon`。搜索必须同时覆盖：

- 股票或行业的“合理/共识 Forward P/E”来源；
- 可比公司集合及其 Forward P/E 观测值；
- 来源 URL、来源名称、发布日期或更新时间、访问时间、预测期间、币种、股份口径和计算依据。

来源没有明确 Forward/NTM/FY 期间，或只能提供目标价但没有 EPS 和股份口径时，不得反推目标 P/E。历史回放禁止使用当前网络搜索结果支持估值。

网络证据默认最多 60 个自然日；过期证据保留在审计对象中，但使目标价 gate 关闭。网络新闻与估值证据分开管理，新闻同样只允许分析日往前 60 天内的可解析发布时间。

### 3. 可比公司倍数的统一口径

每条 peer observation 必须满足：

- `forward_pe > 0`；
- `forecast_period` 与目标 EPS 完全一致；
- 币种与目标价格币种一致，或已明确提供可复核的 FX；
- `share_basis` 一致（例如 `USD/ADR` 或 `KRW/common_share`）；
- 有 provider/source、as-of date 和字段/URL。

至少需要 3 条有效 peer observation。异常值不以人工删除，保留 `excluded_peers` 及排除原因；P25/P50/P75 使用线性插值分位数，避免用最小/最大值制造情景。

### 4. ADR/ADS 处理

工具不从普通股数与摊薄平均股数的比例猜 ADR。目标 EPS 只有在以下任一条件成立时可用：

1. 提供方明确声明 EPS 是报价证券（例如 USD/ADR）；或
2. 提供原始 EPS 币种/普通股口径、经官方或交易所来源确认的 ADR ratio 和必要 FX，由工具确定性换算。

无法确认时阻断目标价，并记录 `share_basis_unverified`，即使数字看起来能与价格相乘也不放行。

### 5. 新闻时效

抓取窗口固定为 60 天。`news.txt` 的审计必须记录 `news_start`、`news_end`、解析失败/超窗排除数和最新发布时间；缺少可解析日期的条目不能作为当前催化剂证据。News Analyst 只能使用窗口内条目，不能用旧新闻补充当前结论。

## 产物与接口

新增 `tools/forward_pe_valuation.py`，提供无网络的确定性函数：

- `validate_valuation_consensus(payload, analysis_date, ...)`：校验网络来源、新鲜度、期间、peer 口径和最小样本数；
- `calculate_forward_pe_scenarios(forward_eps, peers, ...)`：计算 P25/P50/P75 及三档目标价；
- `build_forward_pe_valuation(...)`：生成结构化 `forward_pe_valuation.toon`，保存输入、排除项、分位数、算式和 gate blocking reasons。

`data_validation.build_validated_metrics` 接收可选的 `valuation_consensus` 和计算结果，把 Forward EPS、peer 分位数、目标价和 `allow_target_price` 写入同一份 fail-closed contract。没有网络产物时明确写 `valuation_consensus_missing`，不恢复旧的 TTM 目标价逻辑。

## 工作流

1. 主会话创建 data/report 目录。
2. 主会话使用网络搜索完成股票/行业估值证据，并按 schema 写入 `valuation_consensus.toon`；没有来源、依据或期间的结果视为不可用。
3. `fetch_data.py` 读取该产物，抓取下一财年 EPS、新闻和其他数据，生成 `forward_pe_valuation.toon` 与更新后的 `validated_metrics.toon`。
4. Phase 2 Fundamentals Analyst 只引用 gate 允许的三档结果；Final Decision 按固定字段展示：

```text
Forward EPS: {value} {unit}
Target P/E: {bear}x / {base}x / {bull}x
Price Target: {bear} / {base} / {bull} {unit}
```

5. 任一输入缺失、过期、期间不一致、币种/股份口径不一致或样本少于 3 条时，`Price Target` 为 `Not Rated`，并在 `Investment Thesis` 写出阻断原因。

## 不在本次范围

- 不实现 DCF；DCF 仍是后续独立方法，不能以 Forward P/E 产物冒充。
- 不把 Longbridge 未在现有 REST client 暴露的 Fundamental API endpoint 猜测性加入客户端；网络搜索证据先通过结构化 artifact 接入。
- 不把技术价格区间、分析师目标价或文章反推倍数混入 Forward P/E 目标价。
