# 市场情报工作台新闻事件中心实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立可审计的新闻与事件中心，按行业/主题、公司、美国经济、政治地缘和市场结构分类，把新闻关联到市场、行业、主题、股票和资金/价格图表。

**Architecture:** 新闻 provider 只负责返回原始文章，news pipeline 负责标准化、去重、实体关联、评分和事件聚类，repository 负责持久化，API 返回带来源和质量元数据的文章/事件。前端消息中心消费 API，不在浏览器中做新闻评分或因果判断。

**Tech Stack:** Python >=3.10、Pydantic、DuckDB、requests/httpx、现有新闻过滤逻辑的可复用规则、pytest；React/TypeScript、Vitest、React Testing Library。

## Global Constraints

- 新闻类别固定为行业/主题热点、公司与产业链、美国经济、政治与地缘、市场结构五类。
- 来源优先级为官方机构/交易所/监管披露 > 授权金融新闻源 > 权威媒体 > 聚合来源；低等级来源不能覆盖高等级事实字段。
- 每条新闻保留原文标题、中文标题、摘要、来源、链接、发布时间、事件发生时间、影响对象和证据层级。
- `relevance_score` 和 `impact_score` 为 `0..100`；`confidence` 为 `high|medium|low`，三者不合并为单一情绪分。
- 新闻发布时间和事件发生时间分开保存；无法识别事件时间时使用 `event_time=None`，不能把抓取时间冒充发生时间。
- 首版只保存标题、摘要、来源和链接；全文仅在授权允许时保存。
- 统计相关、共同提及和新闻关联不得在 UI 中表述为确定因果。
- 先实现 fixture pipeline，再执行真实 source smoke test；不采用先写失败测试的 TDD。
- 修改代码后同步更新根目录 `README.md`；测试命令使用 `rtk` 前缀。

## 文件结构

| 文件 | 责任 |
|---|---|
| `market_workbench/news/models.py` | Raw article、normalized article、event 和 source policy 模型 |
| `market_workbench/news/providers.py` | NewsProvider protocol、fixture 和真实 source adapter |
| `market_workbench/news/processing.py` | 标题规范化、精确/近似去重、分类和实体关联 |
| `market_workbench/news/scoring.py` | relevance、impact、confidence 计算 |
| `market_workbench/news/events.py` | 事件聚类和 relation edge 生成 |
| `market_workbench/storage/` | news_event、event_cluster、relation_edge 的 schema/repository 扩展 |
| `market_workbench/api/routes.py` | 新闻、事件、新闻详情 API 扩展 |
| `frontend/src/features/news/` | 消息列表、详情、筛选和事件时间线 |
| `tests/market_workbench/test_news_*.py` | 新闻纯函数、repository、API 和 pipeline 测试 |
| `frontend/tests/news.test.tsx` | 消息中心交互测试 |
| `README.md` | 来源配置、版权边界和新闻运行说明 |

---

### Task 1: 建立新闻领域模型、来源策略和存储表

**Files:**
- Create: `market_workbench/news/__init__.py`
- Create: `market_workbench/news/models.py`
- Create: `market_workbench/news/providers.py`
- Modify: `market_workbench/storage/schema.sql`
- Modify: `market_workbench/storage/repositories.py`
- Create: `tests/market_workbench/test_news_storage.py`

**Interfaces:**

```python
NewsCategory = Literal["industry", "company", "macro_us", "political", "market_structure"]
SourceTier = Literal["official", "licensed_finance", "major_media", "aggregator"]
Confidence = Literal["high", "medium", "low"]

class RawNewsItem(BaseModel):
    source: str
    source_tier: SourceTier
    title: str
    summary: str | None
    link: AnyHttpUrl
    published_at: datetime
    raw_payload: dict[str, Any]

class NewsArticle(BaseModel):
    article_id: str
    original_title: str
    display_title_zh: str | None
    summary: str | None
    source: str
    source_tier: SourceTier
    link: AnyHttpUrl
    published_at: datetime
    event_time: datetime | None
    category: NewsCategory
    market_codes: list[Market]
    entity_ids: list[str]
    relevance_score: int
    impact_score: int
    confidence: Confidence

class NewsProvider(Protocol):
    def fetch(self, request: NewsRequest) -> list[RawNewsItem]: ...
    def source_tier(self) -> SourceTier: ...

class NewsRequest(BaseModel):
    markets: list[Market]
    start: datetime
    end: datetime
    as_of: datetime | None
    scope_ids: set[str]
    limit: int
```

- [ ] **Step 1: 实现模型和 source policy**

验证标题非空、URL 合法、发布时间带时区、分数在 0..100、category/market/confidence 使用受限枚举。source policy 保存 provider 名称、tier、支持市场、允许保存的字段和请求频率。

- [ ] **Step 2: 扩展 DuckDB schema**

新增 `news_article` 和 `event_cluster` 表；`relation_edge` 表由子计划 A 建立，本任务只写入新闻关联边。文章幂等键为 `source + link`，没有 link 时使用 `source + normalized_title + published_at`；relation edge 必须保存 `evidence_ids`、`strength`、`valid_from`、`valid_to` 和 `relation_type`。

- [ ] **Step 3: 实现 repository 和存储测试**

提供 `upsert_articles()`、`list_articles()`、`upsert_event_clusters()`、`list_relations()`；测试重复 link 不生成重复文章、低等级文章不能覆盖高等级摘要/事件时间、edge 能反查 evidence id。

Run:

```bash
rtk python -m pytest tests/market_workbench/test_news_storage.py -q
```

---

### Task 2: 实现新闻标准化、精确/近似去重和来源合并

**Files:**
- Create: `market_workbench/news/processing.py`
- Create: `tests/market_workbench/test_news_processing.py`

**Interfaces:**

```python
def normalize_title(title: str) -> str: ...
def normalize_article(raw: RawNewsItem, *, article_id: str) -> NewsArticle: ...
def deduplicate_exact(items: Sequence[RawNewsItem]) -> list[RawNewsItem]: ...
def cluster_similar(items: Sequence[NewsArticle], *, window: timedelta = timedelta(hours=48)) -> list[list[NewsArticle]]: ...
def merge_cluster(cluster: Sequence[NewsArticle]) -> NewsArticle: ...
```

- [ ] **Step 1: 复用并隔离现有规则**

将现有 `skills/stock-analysis-debate/tools/news_filter.py` 中标题全角/半角、空白归一化和保守噪声规则抽象为工作台自己的纯函数；不要让工作台 import Skill 的脚本路径，避免运行环境耦合。现有 Skill 行为保持不变。

- [ ] **Step 2: 实现精确去重**

先按 normalized title + link 去重；保留发布时间更早、source tier 更高、摘要更完整的记录，合并来源列表，不丢失原始 link。

- [ ] **Step 3: 实现近似聚类**

在 48 小时窗口内使用中文/英文字符 bigram 集合相似度；相似度达到 0.8 才聚类。聚类不是删除证据，所有 article id 保留在 cluster 中；merge 后事实字段选择最高 source tier，争议字段保持为空并降 confidence。

- [ ] **Step 4: 运行语义测试**

覆盖全角标题、空格、重复 link、同标题多来源、相似但不同事件、超过 48 小时不聚类、低等级噪声不覆盖高等级摘要和空摘要保留。

Run:

```bash
rtk python -m pytest tests/market_workbench/test_news_processing.py -q
```

---

### Task 3: 实现分类、实体关联和三类评分

**Files:**
- Create: `market_workbench/news/scoring.py`
- Create: `market_workbench/news/entity_linker.py`
- Create: `tests/market_workbench/test_news_scoring.py`

**Interfaces:**

```python
def classify_category(article: NewsArticle, rules: ClassificationRules) -> NewsCategory: ...
def link_entities(article: NewsArticle, index: TaxonomyIndex) -> NewsArticle: ...
def score_relevance(article: NewsArticle, *, market: Market | None, scope_ids: set[str]) -> int: ...
def score_impact(article: NewsArticle, *, confirmed_source_count: int) -> int: ...
def assess_confidence(article: NewsArticle, *, corroborating_ids: Sequence[str]) -> Confidence: ...

class ClassificationRules(BaseModel):
    category_keywords: dict[NewsCategory, list[str]]
    source_overrides: dict[str, NewsCategory]

class TaxonomyIndex(Protocol):
    def resolve(self, alias: str) -> list[str]: ...
```

- [ ] **Step 1: 定义分类规则**

公司公告/财报/并购/监管归入 company；美联储/利率/通胀/就业/财政归入 macro_us；外交、制裁、冲突、谈判归入 political；指数调整、交易规则、异常资金归入 market_structure；行业产品/供需/政策主题归入 industry。多标签候选冲突时保留 primary category 和 secondary tags。

- [ ] **Step 2: 实现 canonical entity linker**

基于 `instrument`、`taxonomy_membership` 和 alias 表匹配 ticker、行业、主题和市场；保存命中的 alias、entity id 和匹配置信度。未命中不猜测股票，文章仍可作为宏观/政治事件保存。

- [ ] **Step 3: 实现可解释评分**

relevance：直接股票匹配 50 分、行业/主题匹配 30 分、市场匹配 20 分；没有匹配项为 0。impact 根据 category 基础权重、受影响市场数量和确认来源数量计算并限制在 0..100；confidence 由 source tier 和独立 corroborating article 数量决定。评分函数输出中间原因，供 API 详情展示。

- [ ] **Step 4: 运行评分和关联测试**

测试 AI 新闻命中 AI 主题但未命中无关股票、Fed 新闻命中 US/macro_us、政治事件可关联多个市场但不自动生成股票、同一文章多个别名只生成一个 entity、分数上下限和原因可追溯。

Run:

```bash
rtk python -m pytest tests/market_workbench/test_news_scoring.py -q
```

---

### Task 4: 实现事件聚类、关系边和 provider pipeline

**Files:**
- Create: `market_workbench/news/events.py`
- Create: `market_workbench/news/pipeline.py`
- Create: `market_workbench/news/fixture_provider.py`
- Modify: `market_workbench/ingestion/scheduler.py`
- Create: `tests/market_workbench/test_news_pipeline.py`

**Interfaces:**

```python
class NewsPipeline:
    def run_once(self, request: NewsRequest, provider: NewsProvider) -> NewsRunSummary: ...

def build_event_cluster(cluster: Sequence[NewsArticle]) -> EventCluster: ...
def build_news_relations(event: EventCluster) -> list[RelationEdge]: ...

class EventCluster(BaseModel):
    event_id: str
    primary_article_id: str
    article_ids: list[str]
    category: NewsCategory
    title: str
    entity_ids: list[str]
    impact_score: int
    confidence: Confidence
    evidence_ids: list[str]

# RelationEdge imports the shared model from market_workbench.domain.models.

class NewsRunSummary(BaseModel):
    inserted_articles: int
    merged_clusters: int
    relation_edges: int
    status: Literal["success", "partial", "failed"]
```

- [ ] **Step 1: 实现 fixture provider**

准备 AI 行业新闻、Fed 宏观新闻、政治事件、公司公告、重复转载和无关噪声 fixture；每条包含发布时间、事件时间、来源 tier、摘要和链接，不访问网络。

- [ ] **Step 2: 实现事件 cluster 和 relation edge**

事件 cluster 保留 primary article、全部 article ids、category、affected entities、scores 和 evidence ids。生成 `news -> industry/theme/stock` 边，边强度使用 relevance/impact 的可解释组合；不存在实体时只生成事件节点，不生成虚构股票边。

- [ ] **Step 3: 接入采集和调度**

新闻默认在开盘前执行一次，交易时段按 15 分钟执行，收盘后再执行一次。任务使用与行情相同的 job/recovery 机制；provider 失败只影响新闻任务，不阻塞行情采集。

- [ ] **Step 4: 运行 pipeline 测试**

覆盖 fixture 完整链路、重复聚类、官方来源覆盖聚合来源、单一新闻多市场关联、新闻失败不影响行情 job、新闻 `event_time` 不被 `published_at` 替换。

Run:

```bash
rtk python -m pytest tests/market_workbench/test_news_pipeline.py -q
```

---

### Task 5: 提供新闻/事件 API 并接入网络图证据

**Files:**
- Modify: `market_workbench/api/schemas.py`
- Modify: `market_workbench/api/routes.py`
- Create: `tests/market_workbench/test_news_api.py`

**Endpoints:**

```text
GET /api/v1/news?market=US&category=macro_us&scope_id=ai&start=<ISO>&end=<ISO>&limit=50
GET /api/v1/news/{article_id}
GET /api/v1/events/timeline?market=CN,HK,US&start=<ISO>&end=<ISO>
```

- [ ] **Step 1: 定义 response schema**

响应必须包含 article/event 的来源、发布时间、事件时间、relevance、impact、confidence、entity ids、evidence ids、quality metadata 和 `data_as_of`。

- [ ] **Step 2: 实现筛选和详情路由**

支持 market/category/scope/time/limit；详情返回原始标题、中文标题、摘要、来源链接、来源 tier、评分原因和关联关系。无数据返回空列表，不把 provider 失败转换成空成功。

- [ ] **Step 3: 扩展 graph API**

event graph 返回新闻事件节点和 relation edge 的 evidence ids；点击关系时前端可以请求 article detail，不能只返回无来源的边。

- [ ] **Step 4: 运行 API 测试**

用 fixture DB 验证分类筛选、时间筛选、详情来源、事件时间、quality/error response 和 graph evidence ids。

Run:

```bash
rtk python -m pytest tests/market_workbench/test_news_api.py -q
```

---

### Task 6: 实现前端消息中心和事件时间线

**Files:**
- Create: `frontend/src/features/news/NewsFilters.tsx`
- Create: `frontend/src/features/news/NewsList.tsx`
- Create: `frontend/src/features/news/NewsDetail.tsx`
- Create: `frontend/src/features/news/EventTimeline.tsx`
- Modify: `frontend/src/features/news/index.ts`
- Modify: `frontend/src/app/types.ts`
- Create: `frontend/tests/news.test.tsx`

**Interfaces:**

```ts
export function NewsList(props: { items: NewsArticle[]; onSelect(id: string): void }): JSX.Element;
export function NewsDetail(props: { article: NewsArticle; relations: RelationEdge[] }): JSX.Element;
export function EventTimeline(props: { events: EventCluster[] }): JSX.Element;

export interface NewsArticle {
  articleId: string;
  originalTitle: string;
  displayTitleZh?: string;
  summary?: string;
  source: string;
  sourceTier: "official" | "licensed_finance" | "major_media" | "aggregator";
  link: string;
  publishedAt: string;
  eventTime?: string;
  category: string;
  entityIds: string[];
  relevanceScore: number;
  impactScore: number;
  confidence: "high" | "medium" | "low";
}

export interface EventCluster {
  eventId: string;
  title: string;
  articleIds: string[];
  category: string;
  entityIds: string[];
  impactScore: number;
  evidenceIds: string[];
}

export interface RelationEdge {
  sourceId: string;
  targetId: string;
  relationType: string;
  strength: number;
  evidenceIds: string[];
}
```

- [ ] **Step 1: 实现消息筛选和列表**

按五类 category、market、scope、时间和最小 impact 筛选；列表展示中文标题、原文标题入口、来源、发布时间、事件时间、impact/relevance/confidence 和 quality 状态。

- [ ] **Step 2: 实现详情和证据链**

详情展示摘要、原文链接、来源 tier、关联实体、评分原因、article ids 和 network relation；没有 event_time 时明确显示“事件时间未识别”，不使用抓取时间替代。

- [ ] **Step 3: 实现事件时间线**

按 event_time 排序；缺少 event_time 的文章按 published_at 排序但显示不同时间字段。点击事件联动全局筛选、资金折线和网络图。

- [ ] **Step 4: 运行前端新闻测试**

测试五类分类筛选、重复 cluster 展示、来源链接、评分原因、事件时间缺失、低质量/过期状态和点击事件联动。

Run:

```bash
rtk npm --prefix frontend run test -- --run frontend/tests/news.test.tsx
```

---

### Task 7: README、版权边界和新闻全链路验收

**Files:**
- Modify: `README.md`
- Create: `tests/market_workbench/test_news_smoke.py`

- [ ] **Step 1: 补充 README**

追加新闻 source policy 配置、开盘前/盘中/收盘调度、标题/摘要/来源保存规则、全文版权边界、五类分类、评分解释和“关联不等于因果”的产品说明。

- [ ] **Step 2: 运行无网络新闻 smoke test**

fixture provider 写入行业、Fed、政治、公司和重复新闻，调用 news API 和 graph API，验证去重、评分、实体边和前端详情都能回溯 evidence id。

- [ ] **Step 3: 运行全链路验证**

```bash
rtk python -m pytest tests/market_workbench -q
rtk npm --prefix frontend run test -- --run
rtk npm --prefix frontend run build
rtk git diff --check
```

Expected：新闻中心测试通过，行情任务不因新闻 provider 失败而失败，构建产物可由 FastAPI 静态挂载。
