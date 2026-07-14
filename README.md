# aaai

个人 AI/自动化实验仓库。

## skills/stock-analysis-debate

多智能体辩论式股票分析 skill。编排 Market/News/Social/Fundamentals 分析师 + Bull/Bear 辩论 + 风险辩论 + 组合经理，产出 Buy/Hold/Sell 建议。

**数据源**：yfinance（OHLCV/基本面/财报）、stockstats（技术指标）、新浪财经（CN/HK 新闻，翻页抓全）、东方财富（CN 公告）、长桥证券 API（HK/US 分部收入）。

### 新闻处理流水（数据层去噪 + 分析层打分）

- **新浪翻页抓全**：`fetch_data.py` 翻页抓取完整 30 天新闻，解决"40 条只覆盖 1 天"问题。
- **分层保留**：近 7 天全量保留；8-30 天仅保留命中高信号词（财报/评级/价格战/并购/监管等）的新闻。
- **去重**：数据层做标题归一化后完全相同去重；近似重复（媒体洗稿）交由 News Analyst LLM 识别。
- **去噪**：关键词 + 来源黑名单过滤明显噪声（地缘无关/鸡汤/国旗等）。
- **打分标注**：News Analyst 对每条新闻打影响力分(0-3) + 标注业务线，输出高分事件表与业务线命中表。
- 全量保留可审计：`news_meta.txt` 记录抓取/去重/去噪统计。

### 多业务分部视角（仅 HK/US）

- **Phase 1.5**：`prepare_segments.py --gen-yaml` 从长桥 API 抓取分部收入数据，生成 `segments.yaml`（业务线清单，ticker 级跨次复用）+ `segments_financials.csv`（紧凑分部数据）。
- **Segment Analyst**：条件触发（`multi_segment: true`），识别各业务线增长/衰退拐点，判断对集团股价综合方向。
- **CN 市场不走业务线分析**（长桥无 A 股分部数据），退化为 4 分析师流程。
- **降级**：长桥抓取失败时生成 `segments_fetch_failed.flag`，跳过分部视角，不阻断分析。

### 工具模块

| 文件 | 职责 |
|------|------|
| `tools/fetch_data.py` | 主抓取流程（新浪翻页+去噪流水+长桥分部+flag） |
| `tools/news_filter.py` | 新闻去重/去噪/分层保留纯函数 |
| `tools/longbridge_fetcher.py` | 长桥 counter_id/API1+API2 抓取解析/分部清单推导 |
| `tools/prepare_segments.py` | 长桥 JSON→CSV + `--gen-yaml` 生成清单 |

### 测试

```bash
PYTHONPATH=skills/stock-analysis-debate/tools python -m pytest skills/stock-analysis-debate/tools/tests/ -v
```

### 用法

参考 `skills/stock-analysis-debate/SKILL.md`。
