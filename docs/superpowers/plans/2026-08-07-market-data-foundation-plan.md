# 市场情报工作台数据底座实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立可独立运行的 Python 数据底座，统一 A 股、港股、美股的时间/代码/资金数据，写入 DuckDB，支持 fixture、实时任务、历史回放和基础 API。

**Architecture:** 在现有根项目中新增 `market_workbench` 包。领域模型与供应商适配器隔离，原始数据和派生数据分层保存；采集任务通过 repository 写入 DuckDB，FastAPI 只读取统一数据契约。现有 Longbridge client 作为可选适配器，不能把账户现金流字段当作市场资金流。

**Tech Stack:** Python >=3.10、Pydantic、FastAPI、Uvicorn、DuckDB、pandas、yfinance、exchange-calendars、pytest；现有 `longbridge_rest_client` 仅通过适配器调用。

## Global Constraints

- 市场代码固定为 `CN`、`HK`、`US`；市场时区分别为 `Asia/Shanghai`、`Asia/Hong_Kong`、`America/New_York`。
- 港股代码保留用户输入的有效前导零；内部可另存 provider symbol，但不能覆盖 canonical symbol。
- 实时采集粒度可选 1/3/5 分钟；没有真实 provider 能力时返回 `unavailable`，不伪造实时数据。
- `standardized_flow_score` 使用日线 60 个有效交易日、日内 20 个同交易时段有效交易日的百分位窗口，`round(200 * (p - 0.5))` 后限制在 `-100..100`。
- 原始 provider payload、统一模型和派生评分分别保存；所有结果携带 `source`、`retrieved_at`、`as_of` 和质量状态。
- 不采用先写失败测试的 TDD；每个任务先实现最小闭环，再运行针对真实语义场景的单元、契约或集成测试。
- 代码修改后同步更新根目录 `README.md`；不修改其他用户未提交文件。
- 测试从 `/Users/zhangqi.huang/aaai` 执行，命令使用 `rtk` 前缀。

## 文件结构

| 文件 | 责任 |
|---|---|
| `pyproject.toml` | 增加 `market_workbench` 包发现和可选依赖组 `workbench` |
| `market_workbench/domain/` | 市场、时间、证券、行情、资金和质量模型 |
| `market_workbench/storage/` | DuckDB schema、连接管理和 repository |
| `market_workbench/providers/` | provider capability、fixture、Longbridge 和 yfinance 适配器 |
| `market_workbench/metrics/` | 资金标准化评分与聚合 |
| `market_workbench/ingestion/` | 交易日历、采集 runner、调度和恢复 |
| `market_workbench/api/` | FastAPI app、请求/响应 schema 和读取路由 |
| `market_workbench/cli.py` | 本地启动和数据目录配置 |
| `tests/market_workbench/` | 数据底座语义测试、fixture 和 API 测试 |
| `docs/market-workbench-provider-capabilities.md` | 已验证的 provider 能力和降级边界 |
| `README.md` | 本地安装、启动、离线回放和数据边界 |

---

### Task 1: 建立应用包和本地 CLI

**Files:**
- Modify: `pyproject.toml`
- Create: `market_workbench/__init__.py`
- Create: `market_workbench/cli.py`
- Create: `tests/market_workbench/__init__.py`
- Create: `tests/market_workbench/test_cli.py`

**Interfaces:**
- `market_workbench.cli.build_parser() -> argparse.ArgumentParser`
- `market_workbench.cli.main(argv: Sequence[str] | None = None) -> int`
- CLI 参数：`--data-dir`、`--host`、`--port`、`--offline`、`--version`

- [ ] **Step 1: 更新包发现和可选依赖**

在 `pyproject.toml` 保留现有项目名和 Longbridge 依赖，同时把 setuptools include 扩展为 `longbridge_rest_client*` 和 `market_workbench*`，新增可选依赖组：

```toml
[project.optional-dependencies]
workbench = [
  "duckdb>=1.0",
  "exchange-calendars>=4.5",
  "fastapi>=0.110",
  "pandas>=2.0",
  "pydantic>=2.0",
  "pytest>=8.0",
  "requests>=2.31",
  "uvicorn>=0.29",
  "yfinance>=0.2.40",
]
```

- [ ] **Step 2: 实现 CLI 最小闭环**

`main()` 解析参数，创建数据目录路径，并在 `--version` 时输出包版本；没有 `--version` 时调用后续 Task 7 提供的 `create_app(data_dir, offline)`。在 API 尚未实现前，先让 `--version` 和参数解析可独立运行。

- [ ] **Step 3: 添加 CLI 语义测试并运行**

覆盖：默认参数、显式数据目录、`--offline` 布尔值、`--version` 返回码；使用 `tmp_path`，禁止写入用户真实 home 目录。

Run:

```bash
rtk python -m pip install -e ".[workbench]"
rtk python -m pytest tests/market_workbench/test_cli.py -q
```

Expected: 所有 CLI 场景通过。

---

### Task 2: 建立领域模型、市场时间和代码规范化

**Files:**
- Create: `market_workbench/domain/__init__.py`
- Create: `market_workbench/domain/enums.py`
- Create: `market_workbench/domain/models.py`
- Create: `market_workbench/domain/time.py`
- Create: `market_workbench/domain/identifiers.py`
- Create: `tests/market_workbench/test_domain.py`

**Interfaces:**

```python
Market = Literal["CN", "HK", "US"]

class Instrument(BaseModel):
    symbol: str
    market: Market
    exchange: str
    name: str
    currency: str
    timezone: str

class PriceVolumeBar(BaseModel):
    symbol: str
    market: Market
    interval: Literal["1m", "3m", "5m", "1d"]
    timestamp_utc: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal | None
    turnover: Decimal | None
    source: str
    retrieved_at: datetime

class FlowObservation(BaseModel):
    scope_type: Literal["market", "index", "industry", "theme", "stock"]
    scope_id: str
    market: Market
    timestamp_utc: datetime
    native_metric_name: str
    native_value: Decimal | None
    standardized_flow_score: int | None
    flow_proxy: bool
    source: str
    retrieved_at: datetime
    as_of: datetime

class RelationEdge(BaseModel):
    source_id: str
    target_id: str
    relation_type: str
    strength: float
    evidence_ids: list[str]
    valid_from: datetime | None
    valid_to: datetime | None
    solid: bool

def normalize_symbol(raw: str, market: Market) -> str: ...
def market_timezone(market: Market) -> ZoneInfo: ...
def to_market_time(timestamp_utc: datetime, market: Market) -> datetime: ...
```

- [ ] **Step 1: 实现模型约束**

所有时间字段要求带 timezone；价格不能为负；`high >= max(open, close)`、`low <= min(open, close)`；`standardized_flow_score` 只能为 `None` 或 `-100..100`；`flow_proxy=True` 时 `native_metric_name` 必须明确是代理字段。

- [ ] **Step 2: 实现市场时区和 symbol 规范化**

CN 保留 `.SH`、`.SZ`、`.BJ` 交易所后缀；HK canonical symbol 保留用户提供的五位形式和 `.HK`；US 使用大写 ticker。provider 变体只在 adapter 层生成。

- [ ] **Step 3: 运行语义测试**

测试 A/H/US 时区转换、夏令时边界、港股 `00700.HK` 前导零、CN `.SH` 不被误改成 `.SS`、无时区 datetime 被拒绝、非法 OHLC 被拒绝。

Run:

```bash
rtk python -m pytest tests/market_workbench/test_domain.py -q
```

---

### Task 3: 建立 DuckDB schema 和 repository

**Files:**
- Create: `market_workbench/storage/__init__.py`
- Create: `market_workbench/storage/schema.sql`
- Create: `market_workbench/storage/database.py`
- Create: `market_workbench/storage/repositories.py`
- Create: `tests/market_workbench/test_storage.py`

**Interfaces:**

```python
class Database:
    @classmethod
    def open(cls, path: Path) -> "Database": ...
    def initialize(self) -> None: ...
    def close(self) -> None: ...

class MarketRepository:
    def upsert_instruments(self, rows: Sequence[Instrument]) -> int: ...
    def list_instruments(self, market: Market | None = None) -> list[Instrument]: ...

class TimeSeriesRepository:
    def upsert_price_bars(self, rows: Sequence[PriceVolumeBar]) -> int: ...
    def upsert_flows(self, rows: Sequence[FlowObservation]) -> int: ...
    def list_price_bars(self, request: PriceBarQuery) -> list[PriceVolumeBar]: ...
    def list_flows(self, request: FlowQuery) -> list[FlowObservation]: ...

class RelationRepository:
    def upsert_relations(self, rows: Sequence[RelationEdge]) -> int: ...
    def list_relations(self, *, market: Market | None, as_of: datetime, limit: int) -> list[RelationEdge]: ...

class JobRepository:
    def start(self, job_key: str, started_at: datetime) -> str: ...
    def finish(self, run_id: str, status: JobStatus, error: str | None = None) -> None: ...

class PriceBarQuery(BaseModel):
    market: Market | None
    symbols: list[str] | None
    start: datetime
    end: datetime
    interval: str

class FlowQuery(BaseModel):
    market: Market | None
    scope_type: str
    scope_id: str | None
    start: datetime
    end: datetime
    metric: Literal["native", "standardized"]

JobStatus = Literal["pending", "running", "success", "partial", "failed"]
```

- [ ] **Step 1: 写 schema.sql**

建立 `instrument`、`price_volume_bar`、`flow_observation`、`taxonomy_membership`、`relation_edge`、`job_run` 和 `data_quality` 表。行情幂等键为 `source + symbol + interval + timestamp_utc`；资金幂等键为 `source + scope_type + scope_id + timestamp_utc + native_metric_name`。原始 provider payload 用 JSON 字段保存，禁止用新采集结果覆盖已有 raw payload。

- [ ] **Step 2: 实现连接管理和 repository**

`Database.open()` 创建父目录、连接 DuckDB、执行 schema；repository 使用参数化 SQL。upsert 返回实际新增或更新行数，查询结果恢复为领域模型。

- [ ] **Step 3: 运行存储测试**

使用临时数据库验证：重复写入只保留一行；同一逻辑记录的新派生评分可更新但 raw payload 保留；按市场、scope、时间范围查询排序稳定；job 失败状态保留错误信息。

Run:

```bash
rtk python -m pytest tests/market_workbench/test_storage.py -q
```

---

### Task 4: 定义 provider capability 并接入 fixture/真实适配器

**Files:**
- Create: `market_workbench/providers/__init__.py`
- Create: `market_workbench/providers/base.py`
- Create: `market_workbench/providers/capabilities.py`
- Create: `market_workbench/providers/fixture.py`
- Create: `market_workbench/providers/longbridge.py`
- Create: `market_workbench/providers/yfinance.py`
- Create: `tests/market_workbench/test_providers.py`
- Create: `docs/market-workbench-provider-capabilities.md`

**Interfaces:**

```python
class ProviderCapabilities(BaseModel):
    provider: str
    markets: set[Market]
    supports_realtime: bool
    supports_history: bool
    supports_price_volume: bool
    supports_native_flow: bool
    supports_news: bool

class MarketDataProvider(Protocol):
    def capabilities(self) -> ProviderCapabilities: ...
    def fetch_price_bars(self, request: PriceBarRequest) -> ProviderResult: ...
    def fetch_flow(self, request: FlowRequest) -> ProviderResult: ...

class UnsupportedCapability(RuntimeError): ...

class PriceBarRequest(BaseModel):
    market: Market
    symbols: list[str]
    start: datetime
    end: datetime
    interval: Literal["1m", "3m", "5m", "1d"]
    as_of: datetime | None

class FlowRequest(PriceBarRequest):
    scope_type: str
    scope_ids: list[str]

class ProviderResult(BaseModel):
    records: list[PriceVolumeBar | FlowObservation]
    source: str
    retrieved_at: datetime
    as_of: datetime
    coverage: float
    status: Literal["ok", "partial", "unavailable"]
```

- [ ] **Step 1: 实现 fixture provider**

fixture provider 从 `tests/market_workbench/fixtures/` 读取固定 A/H/US 行情和资金数据，支持历史查询、指定 `as_of` 和重复调用；用它覆盖所有后续无凭据测试。

- [ ] **Step 2: 实现 Longbridge adapter 的能力边界**

只调用现有 `LongbridgeClient` 已有的 documented operation；真实实时行情、盘口和逐笔接口若不在 REST client 范围内，adapter 必须报告 `supports_realtime=False`，不能伪装为实时。Longbridge 的账户现金流操作不得映射为市场资金流。

- [ ] **Step 3: 实现 yfinance historical adapter**

将 DataFrame 解析为 `PriceVolumeBar`，保留市场时区和成交量单位；历史请求的结束日期按 provider 的 exclusive end 语义处理。yfinance 不提供可靠 native flow 时返回 unsupported，而不是生成假资金值。

- [ ] **Step 4: 写 capability 文档和契约测试**

文档列出每个 provider 对 CN/HK/US 的行情、历史、资金和新闻能力、时间延迟、需要的凭据、明确降级项。测试检查 unsupported capability、provider symbol 转换、异常 payload 和空结果。

Run:

```bash
rtk python -m pytest tests/market_workbench/test_providers.py -q
```

真实 provider smoke test 只在配置凭据后单独执行，不作为默认测试前提。

---

### Task 5: 实现标准化资金评分和聚合

**Files:**
- Create: `market_workbench/metrics/__init__.py`
- Create: `market_workbench/metrics/flow.py`
- Create: `tests/market_workbench/test_flow_metrics.py`

**Interfaces:**

```python
def percentile_score(
    current: Decimal,
    history: Sequence[Decimal],
    *,
    min_samples: int = 20,
) -> int | None: ...

def standardize_flow(
    current: FlowObservation,
    history: Sequence[FlowObservation],
    *,
    min_samples: int = 20,
) -> FlowObservation: ...

def aggregate_flow(
    rows: Sequence[FlowObservation],
    *,
    scope_type: str,
    scope_id: str,
    as_of: datetime,
) -> FlowObservation: ...
```

- [ ] **Step 1: 实现 percentile_score**

使用排序后的历史值计算当前值的百分位；相同值采用平均排名；样本不足、当前值为空、历史含非有限值时返回 `None`。分数按设计公式取整并限制在 `-100..100`。

- [ ] **Step 2: 实现标准化和聚合**

标准化结果保留原始 observation 的 source/native 字段，并记录窗口长度和最小样本数。跨股票聚合时只聚合同市场、同指标、同时间窗口的有效值；无法保持口径一致时返回不可用。

- [ ] **Step 3: 运行语义测试**

覆盖中位数为 0、最大/最小值边界、重复值、样本不足、混合市场禁止聚合、代理值保留 `flow_proxy` 和历史 `as_of` 截止过滤。

Run:

```bash
rtk python -m pytest tests/market_workbench/test_flow_metrics.py -q
```

---

### Task 6: 实现交易日历、采集 runner、调度和离线回放

**Files:**
- Create: `market_workbench/ingestion/__init__.py`
- Create: `market_workbench/ingestion/calendar.py`
- Create: `market_workbench/ingestion/pipeline.py`
- Create: `market_workbench/ingestion/scheduler.py`
- Create: `market_workbench/ingestion/recovery.py`
- Create: `tests/market_workbench/test_ingestion.py`

**Interfaces:**

```python
class MarketCalendar(Protocol):
    def is_open(self, market: Market, when: datetime) -> bool: ...
    def session_key(self, market: Market, when: datetime) -> str: ...

class CollectionRunner:
    def collect_once(
        self,
        market: Market,
        as_of: datetime,
        *,
        provider: MarketDataProvider,
    ) -> CollectionSummary: ...

class ReplayReader:
    def query(self, request: ReplayQuery) -> ReplayResult: ...

class Scheduler:
    def due_markets(self, now: datetime) -> list[Market]: ...

class CollectionSummary(BaseModel):
    run_id: str
    market: Market
    status: Literal["success", "partial", "failed"]
    price_rows: int
    flow_rows: int
    errors: list[str]

class ReplayQuery(BaseModel):
    market: Market
    start: datetime
    end: datetime
    as_of: datetime
    scope_type: str | None
    scope_id: str | None

class ReplayResult(BaseModel):
    market: Market
    as_of: datetime
    price_bars: list[PriceVolumeBar]
    flows: list[FlowObservation]
    quality: DataQuality
```

- [ ] **Step 1: 封装 XSHG/XHKG/XNYS 日历**

用 `exchange-calendars` 作为默认实现，统一输出 market-local session key；测试使用 fake calendar 覆盖周末、节假日、午间休市和美股夏令时，不直接依赖当天真实网络。

- [ ] **Step 2: 实现 collect_once**

按 provider capability 选择 price/flow 操作，写入 raw/normalized/derived 数据和 `job_run`；单个操作失败时保存 `partial`，不删除其他成功市场的数据。每次运行记录 source、retrieved_at、as_of 和 coverage。

- [ ] **Step 3: 实现调度与退避恢复**

调度器根据市场日历和 1/3/5 分钟配置产生任务；重试只针对超时、网络错误、429 和 5xx；400/401/403、结构错误和 unsupported capability 立即进入可见失败/不可用状态。应用重启时读取最近未完成 job 并执行一次增量补采。

- [ ] **Step 4: 实现离线 ReplayReader**

`ReplayQuery` 必须包含 market、start、end、as_of 和可选 scope；repository 查询条件同时限制 `timestamp <= as_of` 与 `retrieved_at` 证据范围，禁止读取未来数据。离线模式不触发 provider。

- [ ] **Step 5: 运行采集/恢复测试**

覆盖：非交易时段不采集、重复运行幂等、一个 provider 失败仍保留其他市场、重启后恢复、429 重试、401 不重试、历史回放隔离未来数据。

Run:

```bash
rtk python -m pytest tests/market_workbench/test_ingestion.py -q
```

---

### Task 7: 提供 FastAPI 读取 API

**Files:**
- Create: `market_workbench/api/__init__.py`
- Create: `market_workbench/api/schemas.py`
- Create: `market_workbench/api/app.py`
- Create: `market_workbench/api/routes.py`
- Create: `tests/market_workbench/test_api.py`

**Interfaces and endpoints:**

```text
GET /api/v1/markets/overview?market=CN,HK,US&as_of=<ISO datetime>
GET /api/v1/price-volume?market=CN&scope_type=industry&scope_id=ai&start=<ISO>&end=<ISO>
GET /api/v1/flows?market=CN&scope_type=industry&scope_id=ai&start=<ISO>&end=<ISO>&metric=standardized
GET /api/v1/graph?market=CN&view=flow&as_of=<ISO>&min_strength=0.5&limit=50
GET /api/v1/replay?market=CN&start=<ISO>&end=<ISO>&as_of=<ISO>
GET /api/v1/status
```

`create_app(data_dir: Path, offline: bool = False) -> FastAPI` 初始化 repository、provider registry 和 replay mode。API 返回 `data_as_of`、`source_statuses`、`coverage` 和 `is_stale`，不能只返回裸数值。

- [ ] **Step 1: 实现 Pydantic response schemas**

为 overview、time series、flow、graph、replay 和 status 定义稳定 response model，字段名与领域模型一致；无数据返回空列表和质量状态，不返回 500 伪装为数据。

- [ ] **Step 2: 实现查询路由和错误映射**

无效 market/scope/date 返回 422；不可用 provider 返回结构化 `unavailable`；数据库错误返回带 request id 的 500 并写日志，不泄露 Token。

- [ ] **Step 3: 用 fixture DB 运行 API 测试**

使用 FastAPI TestClient 和临时 DuckDB，验证筛选、排序、`as_of` 隔离、空数据、质量状态和错误码。

Run:

```bash
rtk python -m pytest tests/market_workbench/test_api.py -q
```

---

### Task 8: 文档、安装和数据底座验收

**Files:**
- Modify: `README.md`
- Modify: `market_workbench/cli.py`
- Create: `tests/market_workbench/test_smoke.py`

- [ ] **Step 1: 补充 README**

追加本地安装命令、`rtk python -m pip install -e '.[workbench]'`、fixture 启动、`--data-dir`、`--offline`、provider 能力边界、数据目录和不提供自动交易的说明。

- [ ] **Step 2: 实现无凭据 smoke test**

启动 fixture provider，写入 A/H/US 至少一个市场概览、行情和资金记录，调用 overview/flows/replay/status API，验证完整链路不访问外网。

- [ ] **Step 3: 运行底座验证**

```bash
rtk python -m pytest tests/market_workbench -q
rtk python -m pytest tests/test_longbridge_rest_client.py -q
rtk git diff --check
```

Expected：新增数据底座测试通过，现有 Longbridge 测试不回归；工作区其他未提交修改不被纳入本任务。
