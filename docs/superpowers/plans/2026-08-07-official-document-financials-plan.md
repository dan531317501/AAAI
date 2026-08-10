# Official Document Financials Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 HKEX/CNINFO PDF/HTML 官方披露确定性转换为结构化财务事实，并在逐指标解析失败时用免费 API 补缺且禁止覆盖官方事实。

**Architecture:** 保留现有官方披露发现和 SEC XBRL 适配器，新增独立文档下载/文本解析模块；`official_financials.py` 负责合并官方结构化事实、文档事实和免费 API fallback，按 `(metric, period_end, period_type)` 去重，官方事实优先。`fetch_data.py` 传入已获取的披露结果和现有季度财报文本，避免重复请求。

**Tech Stack:** Python 3.11+, requests, pypdf, pandas/yfinance, TOON structured output, pytest.

## Global Constraints

- 只接入免费 API 和公开官方披露；
- 不使用 LLM 从财报抽数；
- 官方事实成功后，免费 API 不得覆盖官方事实；
- 无法解析且无 API 值时保持 N/A/unavailable；
- 遵守当前项目的币种、期间、历史回放和 fail-closed 门禁；
- 修改代码后同步根目录 `README.md` 与 `skills/stock-analysis-debate/SKILL.md`；
- 测试验证函数实际语义，不为通过测试伪造场景。

---

### Task 1: 增加官方披露文档解析器

**Files:**
- Create: `skills/stock-analysis-debate/tools/official_document_parser.py`
- Modify: `skills/stock-analysis-debate/tools/requirements.txt`
- Test: `skills/stock-analysis-debate/tools/tests/test_official_document_parser.py`

**Interfaces:**
- Produces `parse_document_payload(payload, content_type, record, analysis_date, financial_currency)`;
- Produces `parse_official_documents(records, analysis_date, financial_currency)`;
- Each fact includes canonical metric, value, unit, currency, period, source URL, page, excerpt and extraction method.

- [ ] **Step 1: Implement PDF/HTML text extraction**

Use `pypdf.PdfReader` for page-preserving PDF text and `html.parser.HTMLParser` for HTML text. Download bytes with `provider_runtime.retry_call`, validate non-empty content, and return explicit per-document errors for missing text or unsupported content.

- [ ] **Step 2: Implement canonical row parsing**

Recognize English/Chinese aliases for revenue, profit, operating cash flow, assets, equity, cash, debt and EPS. Detect `USD'000`, `USD million` and equivalent units, distinguish annual/quarter/instant periods, remove year-over-year percentage columns, and attach one-based PDF page numbers and bounded source excerpts.

- [ ] **Step 3: Add semantic parser tests**

Cover annual rows with percentage comparison columns, quarterly rows, EPS unit behavior, HTML tables, unsupported/scanned documents, and source provenance. Use in-memory payloads; do not require network access.

- [ ] **Step 4: Add the free PDF dependency**

Add `pypdf` to the existing requirements without adding paid services or model dependencies.

### Task 2: Merge document facts and API fallback in the official financials layer

**Files:**
- Modify: `skills/stock-analysis-debate/tools/official_financials.py`
- Modify: `skills/stock-analysis-debate/tools/tests/test_official_financials.py`

**Interfaces:**
- Extend `fetch_official_financials(..., official_disclosures=None, api_fallback=None)`;
- Official disclosure facts are normalized with `official: true`;
- Free API fallback facts are normalized with `official: false`, `fallback_reason` and provider metadata.

- [ ] **Step 1: Add document parser integration**

Use passed discovery results when available; otherwise fetch them. Parse HKEX/CNINFO records and retain document audit metadata in the result.

- [ ] **Step 2: Add statement API fallback normalization**

Normalize the existing yfinance quarterly CSV text into canonical facts only for missing metric/period keys. Keep the source as `YFINANCE_FREE_API` and never replace a document or SEC fact.

- [ ] **Step 3: Replace document-only degradation status**

Set `numeric_status=available` when official document facts or fallback facts exist, while retaining `status=partial` when the official document itself was not numerically parsed and API fallback supplied only some facts. Record `official_document_parse_failed`, `api_fallback_used`, and remaining missing metrics explicitly.

- [ ] **Step 4: Update tests**

Replace the old “PDF numbers are never extracted” expectation with tests for official document facts, API supplement, official-over-API precedence, and fail-closed behavior.

### Task 3: Wire the shared fetch pipeline and documentation

**Files:**
- Modify: `skills/stock-analysis-debate/tools/fetch_data.py`
- Modify: `skills/stock-analysis-debate/tools/data_validation.py`
- Modify: `skills/stock-analysis-debate/SKILL.md`
- Modify: `README.md`
- Test: `skills/stock-analysis-debate/tools/tests/test_workflow_contract.py`

**Interfaces:**
- `fetch_data.py` passes the already-fetched official disclosure result and existing statement artifacts into `fetch_official_financials`;
- `validated_metrics.toon` retains official/fallback provenance and source page metadata.

- [ ] **Step 1: Remove duplicate official fetches**

Pass the raw disclosure result to the unified layer before removing SEC raw facts for the output artifact, preserving existing `official_filings.toon` compatibility.

- [ ] **Step 2: Propagate provenance into validation**

Expose `official`, `source_page`, `source_excerpt`, `extraction_method`, and fallback flags in validated metrics without changing valuation gates to accept unverified values.

- [ ] **Step 3: Update README and SKILL.md**

Document the official document parser, free API fallback, source-priority rule, and fail-closed behavior.

- [ ] **Step 4: Run workflow contract tests**

Verify output inventory and the new `official_financials.toon` contract.

### Task 4: Verify the real SMIC workflow

**Files:**
- Modify: `skills/stock-analysis-debate/reposrts/00981.HK/data/2026-08-07/*` (generated output only)

- [ ] **Step 1: Install declared dependency in the active environment**

Run `python -m pip install -r skills/stock-analysis-debate/tools/requirements.txt` if `pypdf` is absent.

- [ ] **Step 2: Run the full unit test suite**

Run `PYTHONPATH=skills/stock-analysis-debate/tools python -m pytest skills/stock-analysis-debate/tools/tests/ -v` and inspect the complete result.

- [ ] **Step 3: Re-run the SMIC data fetch**

Run `python skills/stock-analysis-debate/tools/fetch_data.py 00981.HK 2026-08-07 --ticker-data-dir skills/stock-analysis-debate/reposrts/00981.HK/data` after backing up the current generated directory.

- [ ] **Step 4: Verify official facts and fallback boundaries**

Confirm `official_financials.toon` contains official HKEX facts with page/source metadata, any API facts are marked fallback, and `validated_metrics.toon` exposes the same provenance.
