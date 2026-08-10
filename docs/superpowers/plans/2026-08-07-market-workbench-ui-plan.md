# 市场情报工作台可视化界面实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建本地 React/TypeScript 工作台，消费数据底座 API，提供每日扫描、资金折线、成交量柱状图、Top 10 词云、关系网络图、历史筛选和五套可切换皮肤。

**Architecture:** 前端使用一个全局 `FilterState` 驱动所有请求和图表联动；API 访问集中在 typed client；图表组件只消费已规范化的 response，不在组件中重新计算资金指标。主题通过 CSS variables 和图表 token 实现，五套皮肤不复制页面结构。

**Tech Stack:** Node >=20、React、TypeScript、Vite、Apache ECharts、echarts-wordcloud、Cytoscape.js、Vitest、React Testing Library。

## Global Constraints

- 前端默认中文展示；原始新闻标题和 provider 字段可在详情中展开。
- 市场范围固定为 CN/HK/US；市场方向同时显示颜色、箭头和正负号。
- 实时轮询间隔从后端配置读取，只允许 1/3/5 分钟；离线模式不启动轮询。
- 任何图表必须显示 `data_as_of`、source/quality 状态或 stale 标记。
- 词云必须同时渲染精确 Top 10 列表；网络图必须支持节点类型、关系强度、时间和 limit 过滤。
- 五套皮肤只改变视觉 token，不改变数据、单位、正负方向和关系语义。
- 网络图默认限制 50 个节点，点击后才展开邻居；禁止首屏渲染全量节点。
- 先完成最小实现，再运行基于真实交互语义的测试；不采用先写失败测试的 TDD。
- 修改代码后同步更新根目录 `README.md`；测试命令使用 `rtk` 前缀。

## 文件结构

| 文件 | 责任 |
|---|---|
| `frontend/package.json` | 前端依赖和脚本 |
| `frontend/src/app/` | App shell、API client、类型和全局筛选状态 |
| `frontend/src/features/dashboard/` | 市场卡片、折线、柱状图、词云和每日扫描布局 |
| `frontend/src/features/graph/` | Cytoscape 网络图和关系详情 |
| `frontend/src/features/news/` | 新闻中心占位接口和事件时间线入口，由子计划 C 完成业务细节 |
| `frontend/src/theme/` | 五套皮肤 token、主题持久化和图表颜色 |
| `frontend/src/components/` | DataQuality、Loading、EmptyState、FilterBar 等共用组件 |
| `frontend/tests/` | 组件、筛选联动、皮肤和图表数据语义测试 |
| `market_workbench/api/app.py` | 生产构建后静态资源挂载 |
| `README.md` | 前端开发、构建、启动和皮肤说明 |

---

### Task 1: 建立 Vite/React 工程和 API 类型边界

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/tsconfig.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/index.html`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/app/App.tsx`
- Create: `frontend/src/app/types.ts`
- Create: `frontend/src/app/api.ts`
- Create: `frontend/src/app/filterState.ts`
- Create: `frontend/tests/app.test.tsx`

**Interfaces:**

```ts
export type MarketCode = "CN" | "HK" | "US";
export type ScopeType = "market" | "index" | "industry" | "theme" | "stock";
export type MetricMode = "native" | "standardized";

export interface FilterState {
  markets: MarketCode[];
  scopeType: ScopeType;
  scopeId?: string;
  metricMode: MetricMode;
  interval: "1m" | "3m" | "5m" | "1d";
  start: string;
  end: string;
  asOf?: string;
  offline: boolean;
}

export interface QualityMeta {
  source: string;
  dataAsOf: string;
  retrievedAt: string;
  isStale: boolean;
  coverage: number;
  status: "ok" | "partial" | "unavailable" | "stale";
}

export interface PriceVolumeBar {
  timestamp: string;
  market: MarketCode;
  symbol: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number | null;
  turnover: number | null;
}

export interface MarketOverviewCard {
  market: MarketCode;
  indexLabel: string;
  changePercent: number | null;
  turnover: number | null;
  flowScore: number | null;
  quality: QualityMeta;
}

export interface OverviewResponse { cards: MarketOverviewCard[]; quality: QualityMeta; }
export interface FlowSeriesResponse { series: FlowSeries[]; wordCloud: WordCloudItem[]; quality: QualityMeta; }
export interface PriceVolumeResponse { bars: PriceVolumeBar[]; quality: QualityMeta; }
export type GraphMode = "flow" | "chain" | "event";

export async function getOverview(filters: FilterState): Promise<OverviewResponse>;
export async function getFlows(filters: FilterState): Promise<FlowSeriesResponse>;
export async function getPriceVolume(filters: FilterState): Promise<PriceVolumeResponse>;
export async function getGraph(filters: FilterState, mode: GraphMode): Promise<GraphResponse>;
```

- [ ] **Step 1: 创建依赖和开发脚本**

提供 `dev`、`build`、`test`、`test:watch` 脚本；Vite 开发服务器将 `/api` 代理到 `http://127.0.0.1:8000`。依赖至少包括 React、TypeScript、ECharts、echarts-wordcloud、Cytoscape、Vitest、jsdom 和 React Testing Library。

- [ ] **Step 2: 实现 typed API client 和 filterState**

API client 统一处理 JSON、422、结构化 `unavailable` 和 stale metadata；`filterState` 提供 `initialFilterState()`、`updateFilter()` 和 `serializeFilters()`，不允许每个组件自行拼 query string。

- [ ] **Step 3: 实现 App shell 并运行测试/构建**

App 先渲染导航、内容区和数据状态占位，测试确认默认筛选包含 CN/HK/US、离线状态关闭轮询、API 错误不会导致空白页面。

Run:

```bash
rtk npm --prefix frontend install
rtk npm --prefix frontend run test -- --run
rtk npm --prefix frontend run build
```

---

### Task 2: 实现五套视觉皮肤和共用状态组件

**Files:**
- Create: `frontend/src/theme/theme.ts`
- Create: `frontend/src/theme/themes.ts`
- Create: `frontend/src/theme/theme.css`
- Create: `frontend/src/components/DataQualityBadge.tsx`
- Create: `frontend/src/components/EmptyState.tsx`
- Create: `frontend/src/components/LoadingState.tsx`
- Create: `frontend/src/components/FilterBar.tsx`
- Create: `frontend/tests/theme.test.tsx`

**Interfaces:**

```ts
export type ThemeId =
  | "terminal-dark"
  | "financial-blue-white"
  | "editorial-paper"
  | "cyber-neon"
  | "minimal-gray";

export interface ThemeTokens {
  background: string;
  surface: string;
  text: string;
  mutedText: string;
  positive: string;
  negative: string;
  neutral: string;
  accent: string;
  border: string;
}

export function applyTheme(theme: ThemeId): void;
export function readStoredTheme(): ThemeId;
```

- [ ] **Step 1: 定义五套 token**

实现量化终端黑、金融蓝白、报刊研究风、赛博霓虹风、极简灰阶风；默认使用金融蓝白。颜色 token 必须包含 positive/negative/neutral，但组件必须同时显示方向文字或图标。

- [ ] **Step 2: 实现主题切换和本地持久化**

用 `data-theme` 或 CSS variables 切换，不复制页面组件；使用 localStorage 保存 `market-workbench.theme`，未知值回退到 `financial-blue-white`。

- [ ] **Step 3: 实现共用状态和筛选组件**

FilterBar 展示市场、scope、时间、interval、原始/标准化模式、as-of 和离线状态；DataQualityBadge 展示 source、dataAsOf、coverage、stale/unavailable。测试确认皮肤切换不会改变筛选值，质量状态不会被皮肤隐藏。

Run:

```bash
rtk npm --prefix frontend run test -- --run tests/theme.test.tsx
```

---

### Task 3: 实现每日扫描页和三类基础图表

**Files:**
- Create: `frontend/src/features/dashboard/MarketOverviewCards.tsx`
- Create: `frontend/src/features/dashboard/FlowLineChart.tsx`
- Create: `frontend/src/features/dashboard/VolumeBarChart.tsx`
- Create: `frontend/src/features/dashboard/FlowWordCloud.tsx`
- Create: `frontend/src/features/dashboard/DailyScanPage.tsx`
- Create: `frontend/src/features/dashboard/chartOptions.ts`
- Create: `frontend/tests/dashboard.test.tsx`

**Interfaces:**

```ts
export interface FlowPoint { timestamp: string; value: number | null; nativeValue?: number | null; }
export interface FlowSeries { label: string; market: MarketCode; points: FlowPoint[]; quality: QualityMeta; }
export interface WordCloudItem { label: string; value: number; rank: number; market: MarketCode; }

export function FlowLineChart(props: { series: FlowSeries[]; metricMode: MetricMode }): JSX.Element;
export function VolumeBarChart(props: { bars: PriceVolumeBar[]; valueMode: "volume" | "turnover" }): JSX.Element;
export function FlowWordCloud(props: { items: WordCloudItem[] }): JSX.Element;
```

- [ ] **Step 1: 实现 overview cards 和轮询 hook**

`useMarketOverview(filters)` 和 `useMarketSeries(filters)` 按后端返回的 polling interval 请求；请求中的 `asOf` 固定时不轮询。加载、空数据、过期和部分失败都渲染显式状态。

- [ ] **Step 2: 实现资金折线图**

ECharts x 轴使用市场本地时间显示；y 轴按 `native` 或 `standardized` 模式配置单位；新闻/事件标记先消费 `eventMarkers` 可选字段。tooltip 同时显示 raw、score、source 和 dataAsOf。

- [ ] **Step 3: 实现成交量/成交额柱状图**

`valueMode` 明确区分 volume 和 turnover；不把成交额当成交量。正负方向使用主题 token 加箭头/符号；空 bar 显示缺失，不渲染为零。

- [ ] **Step 4: 实现词云和精确排名**

词云只展示前 10 项，字体大小对 `abs(value)` 做可解释的最小/最大缩放；右侧同步渲染 rank、label、value、market 和 quality。点击词条更新全局 scopeId。

- [ ] **Step 5: 运行组件测试**

测试切换原始/标准化模式、成交量/成交额、空数据、缺失值、Top 10 限制和点击词条联动；测试三地市场颜色同时显示方向符号。

Run:

```bash
rtk npm --prefix frontend run test -- --run tests/dashboard.test.tsx
```

---

### Task 4: 实现行业关系网络图

**Files:**
- Create: `frontend/src/features/graph/GraphView.tsx`
- Create: `frontend/src/features/graph/graphTransform.ts`
- Create: `frontend/src/features/graph/GraphControls.tsx`
- Create: `frontend/src/features/graph/RelationDetails.tsx`
- Create: `frontend/tests/graph.test.tsx`

**Interfaces:**

```ts
import type { ElementDefinition as CytoscapeElement } from "cytoscape";

export type GraphNodeType = "market" | "index" | "industry" | "theme" | "stock" | "macro" | "political" | "news";

export interface GraphNode { id: string; label: string; type: GraphNodeType; score?: number; sizeValue: number; direction?: "positive" | "negative" | "neutral"; }
export interface GraphEdge { id: string; source: string; target: string; type: string; strength: number; evidence?: string[]; solid: boolean; }
export interface GraphResponse { nodes: GraphNode[]; edges: GraphEdge[]; quality: QualityMeta; }

export function transformGraph(data: GraphResponse, mode: GraphMode): CytoscapeElement[];
```

- [ ] **Step 1: 实现 GraphControls**

提供 flow/chain/event 三种视图、节点类型、最小关系强度、limit、时间和展开深度；默认 limit=50，最小强度和 market filter 来自全局筛选。

- [ ] **Step 2: 实现 graphTransform**

flow 视图节点大小使用绝对标准化分数，chain 使用最近成交额，event 使用影响力与受影响节点数量组合值；结构性边为实线，统计/新闻边为虚线；把正负方向映射到当前皮肤 token。

- [ ] **Step 3: 实现 Cytoscape 交互**

支持缩放、拖拽、点击节点展开一层邻居、点击边打开 RelationDetails；首屏不加载全量图，展开请求使用节点 id 和 depth 参数。无证据边必须显示质量提示。

- [ ] **Step 4: 运行网络图测试**

测试三种模式的节点大小语义、limit 生效、边类型样式、点击回调、空图、过期数据和五套皮肤下方向颜色不丢失。

Run:

```bash
rtk npm --prefix frontend run test -- --run tests/graph.test.tsx
```

---

### Task 5: 接入历史回放、数据状态和后端静态资源

**Files:**
- Modify: `frontend/src/app/App.tsx`
- Create: `frontend/src/features/replay/ReplayPage.tsx`
- Create: `frontend/src/features/status/StatusPage.tsx`
- Modify: `market_workbench/api/app.py`
- Create: `frontend/tests/replay-status.test.tsx`

- [ ] **Step 1: 实现历史回放页**

选择 market、start、end、asOf 后调用 `/api/v1/replay`；固定 asOf 时禁止实时轮询；页面顶部显示“历史回放”和截止时间，后续图表继续复用 FilterState。

- [ ] **Step 2: 实现数据状态页**

展示 provider capability、job status、last success、coverage、stale/unavailable 原因和最近错误；不得展示 access token 或敏感请求头。

- [ ] **Step 3: 挂载前端生产构建**

FastAPI 在 `frontend/dist` 存在时挂载静态资源和 SPA fallback；开发模式继续使用 Vite proxy。没有 dist 时 API 仍能启动并返回明确错误，不在 import 阶段崩溃。

- [ ] **Step 4: 运行前端全量验证**

```bash
rtk npm --prefix frontend run test -- --run
rtk npm --prefix frontend run build
rtk python -m pytest tests/market_workbench/test_api.py -q
```

---

### Task 6: README 和工作台 UI 验收

**Files:**
- Modify: `README.md`
- Create: `frontend/tests/smoke.test.tsx`

- [ ] **Step 1: 补充 README**

追加 Node 安装、`rtk npm --prefix frontend install`、开发启动、生产构建、五套皮肤、图表/网络图交互和浏览器访问地址；说明 API 由子计划 A 提供，真实 provider 需要单独配置。

- [ ] **Step 2: 运行 fixture smoke test**

mock overview/flows/price-volume/graph/status API，渲染每日扫描页，验证 A/H/US 概览、折线、柱状、词云、网络图、筛选联动和主题切换在无网络状态下工作。

- [ ] **Step 3: 完成差异与构建验证**

```bash
rtk npm --prefix frontend run test -- --run
rtk npm --prefix frontend run build
rtk git diff --check
```
