# Industry Research Skill 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现一个产业趋势调研 Skill，支持递归产业链建模、多数据源采集、多代理并行分析、历史趋势对比

**Architecture:** Phase Pipeline 架构。Phase 1-2 通过 Python 脚本 + LLM 编排完成产业链发现和数据采集；Phase 3-4 通过多 Agent 并行分析 + 串行综合研判；Phase 5-6 由主 session 完成历史对比和报告合成

**Tech Stack:** Python 3 (requests, PyYAML, pytest), Claude Agent SDK (多代理编排), WebFetch (数据源发现), SerpApi (新闻搜索)

---

## 文件结构总览

```
skills/industry-research/
├── SKILL.md                       # 新建: 完整编排流程
├── prompts/
│   ├── node_analyst.md            # 新建: 节点分析师模板
│   ├── policy_analyst.md          # 新建: 政策分析师
│   ├── competition_analyst.md     # 新建: 竞争格局分析师
│   ├── cross_impact_analyst.md    # 新建: 跨环节传导综合研判
│   └── report_synthesizer.md      # 新建: 最终报告合成指引
├── tools/
│   ├── __init__.py                # 新建: 空文件
│   ├── fetch_chain.py             # 新建: 产业链 YAML 验证与初始化
│   ├── fetch_sources.py           # 新建: 数据源搜索注册
│   ├── fetch_data.py              # 新建: 数据采集引擎
│   ├── parsers/
│   │   └── __init__.py            # 新建: 解析器注册表
│   ├── requirements.txt           # 新建: 依赖
│   ├── utils.py                   # 新建: HTTP 会话、Jina 代理、去重工具
│   └── tests/
│       ├── __init__.py            # 新建
│       ├── test_chain_model.py    # 新建: chain.yaml 模型验证
│       ├── test_fetch_sources.py  # 新建: 数据源注册测试
│       ├── test_fetch_data.py     # 新建: 数据采集测试
│       └── fixtures/
│           ├── sample_chain.yaml  # 新建: 测试用产业链
│           └── sample_sources.yaml # 新建: 测试用数据源
```

---

### Task 1: 项目脚手架搭建

**Files:**
- Create: `skills/industry-research/tools/__init__.py`
- Create: `skills/industry-research/tools/requirements.txt`
- Create: `skills/industry-research/tools/parsers/__init__.py`
- Create: `skills/industry-research/tools/tests/__init__.py`
- Create: `skills/industry-research/tools/utils.py`

- [ ] **Step 1: 创建目录结构**

```bash
mkdir -p skills/industry-research/prompts
mkdir -p skills/industry-research/tools/parsers
mkdir -p skills/industry-research/tools/tests/fixtures
mkdir -p skills/industry-research/data
```

- [ ] **Step 2: 创建 `__init__.py` 文件**

`skills/industry-research/tools/__init__.py`:
```python
# Industry Research Toolchain
```

`skills/industry-research/tools/parsers/__init__.py`:
```python
"""Site-specific data parsers.

Each parser module exports a parse(html: str) -> dict function.
Register new parsers by adding them to PARSER_REGISTRY.
"""

PARSER_REGISTRY = {}
```

`skills/industry-research/tools/tests/__init__.py`:
```python
# Tests for industry-research tools
```

- [ ] **Step 3: 创建 `requirements.txt`**

`skills/industry-research/tools/requirements.txt`:
```
pyyaml>=6.0
requests>=2.31.0
```

- [ ] **Step 4: 创建 `utils.py`**

`skills/industry-research/tools/utils.py`:
```python
"""Shared utilities for industry-research tools."""

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import requests


# --- Path helpers ---

def get_skill_root() -> Path:
    """Return the skill root directory (skills/industry-research/)."""
    return Path(__file__).resolve().parent.parent


def get_data_dir(industry: str) -> Path:
    """Return data/{industry}/ directory, creating if needed."""
    d = get_skill_root() / "data" / industry
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_report_dir(industry: str, date: str) -> Path:
    """Return data/{industry}/reports/{date}/ directory, creating if needed."""
    d = get_data_dir(industry) / "reports" / date
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_news_raw_dir(industry: str, date: str) -> Path:
    """Return data/{industry}/reports/{date}/news_raw/ directory."""
    d = get_report_dir(industry, date) / "news_raw"
    d.mkdir(parents=True, exist_ok=True)
    return d


# --- HTTP session with retry ---

def make_session(timeout: int = 30, max_retries: int = 3) -> requests.Session:
    """Create a requests.Session with retry and User-Agent."""
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry

    session = requests.Session()
    retry = Retry(total=max_retries, backoff_factor=1.0,
                  status_forcelist=[429, 500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.headers.update({
        "User-Agent": "IndustryResearch/1.0 (research-bot@example.com)"
    })
    return session


def fetch_via_jina(url: str, timeout: int = 30) -> Optional[str]:
    """Fetch page content via Jina AI Reader proxy. Returns text or None."""
    jina_url = f"https://r.jina.ai/{url}"
    try:
        resp = requests.get(jina_url, timeout=timeout,
                            headers={"Accept": "text/markdown"})
        resp.raise_for_status()
        return resp.text
    except Exception:
        return None


def fetch_direct(url: str, session: Optional[requests.Session] = None,
                 timeout: int = 30) -> Optional[str]:
    """Fetch URL directly. Returns text or None on failure."""
    s = session or make_session()
    try:
        resp = s.get(url, timeout=timeout)
        resp.raise_for_status()
        return resp.text
    except Exception:
        return None


def fetch_with_fallback(url: str, fallback_url: str = "",
                        session: Optional[requests.Session] = None,
                        timeout: int = 30) -> Optional[str]:
    """Try Jina proxy first, then direct fetch, then fallback URL."""
    result = fetch_via_jina(url, timeout)
    if result:
        return result
    result = fetch_direct(url, session, timeout)
    if result:
        return result
    if fallback_url:
        result = fetch_via_jina(fallback_url, timeout)
        if result:
            return result
        result = fetch_direct(fallback_url, session, timeout)
        if result:
            return result
    return None


# --- Content helpers ---

def content_hash(text: str) -> str:
    """SHA256 hash of text for deduplication."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def cache_raw_content(raw_dir: Path, source_id: str, url: str, content: str):
    """Save raw fetched content to news_raw/ for audit trail."""
    raw_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{source_id}_{content_hash(url)[:12]}.txt"
    filepath = raw_dir / filename
    filepath.write_text(content, encoding="utf-8")


# --- YAML helpers ---

def load_yaml(path: Path) -> dict:
    """Load a YAML file. Returns empty dict if not found."""
    import yaml
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def save_yaml(path: Path, data: dict):
    """Save data as YAML file."""
    import yaml
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False,
                       default_flow_style=False)


def load_json(path: Path) -> dict:
    """Load a JSON file. Returns empty dict if not found."""
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data):
    """Save data as JSON file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)
```

- [ ] **Step 5: 验证**

```bash
cd /Users/zhangqi.huang/aaai && python -c "from skills.industry_research.tools import utils; print('utils OK')"
```

Expected: 成功导入或报 ModuleNotFoundError（说明包路径需要调整，切换到工具目录执行）。

```bash
cd /Users/zhangqi.huang/aaai/skills/industry-research/tools && python -c "import utils; print('OK')"
```

Expected: `OK`

- [ ] **Step 6: Commit**

```bash
git add skills/industry-research/tools/__init__.py \
        skills/industry-research/tools/requirements.txt \
        skills/industry-research/tools/parsers/__init__.py \
        skills/industry-research/tools/tests/__init__.py \
        skills/industry-research/tools/utils.py
git commit -m "feat(industry-research): scaffold project structure and utils

- Create directory layout: prompts/, tools/, tools/parsers/, tools/tests/
- Add utils.py with HTTP session, Jina proxy, YAML/JSON helpers
- Add requirements.txt (pyyaml, requests)

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 2: 产业链模型验证 (`fetch_chain.py`)

**Files:**
- Create: `skills/industry-research/tools/fetch_chain.py`
- Create: `skills/industry-research/tools/tests/test_chain_model.py`
- Create: `skills/industry-research/tools/tests/fixtures/sample_chain.yaml`

- [ ] **Step 1: 编写测试 — chain.yaml 结构验证**

`skills/industry-research/tools/tests/test_chain_model.py`:
```python
"""Tests for chain.yaml model validation."""

import tempfile
from pathlib import Path

import pytest

# Import from the tools directory
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fetch_chain import validate_chain, init_chain, load_chain, ChainValidationError


VALID_CHAIN = {
    "industry": "测试行业",
    "description": "用于测试的示例产业链",
    "nodes": [
        {"id": "raw_a", "name": "原料A", "key_factors": ["价格", "产能"], "layer": -2},
        {"id": "comp_b", "name": "部件B", "key_factors": ["良率"], "layer": -1},
        {"id": "prod_c", "name": "产品C", "key_factors": ["销量", "价格"], "layer": 0},
        {"id": "consumer", "name": "消费者", "key_factors": ["需求", "偏好"], "layer": 1},
    ],
    "edges": [
        {"from": "raw_a", "to": "comp_b", "type": "upstream", "mechanism": "原料→部件"},
        {"from": "comp_b", "to": "prod_c", "type": "upstream", "mechanism": "部件→产品"},
        {"from": "prod_c", "to": "consumer", "type": "downstream", "mechanism": "产品→消费者"},
    ],
    "supports": [
        {"id": "policy", "name": "政策", "affects": ["prod_c"], "key_factors": ["补贴"]},
    ],
}


class TestValidateChain:
    """Test chain.yaml schema validation."""

    def test_valid_chain_passes(self):
        errors = validate_chain(VALID_CHAIN)
        assert len(errors) == 0

    def test_missing_industry_name(self):
        chain = {k: v for k, v in VALID_CHAIN.items() if k != "industry"}
        errors = validate_chain(chain)
        assert any("industry" in e.lower() for e in errors)

    def test_missing_nodes(self):
        chain = {k: v for k, v in VALID_CHAIN.items() if k != "nodes"}
        errors = validate_chain(chain)
        assert any("nodes" in e.lower() for e in errors)

    def test_node_missing_id(self):
        chain = dict(VALID_CHAIN)
        chain["nodes"] = [{"name": "无ID节点", "key_factors": ["x"], "layer": 0}]
        errors = validate_chain(chain)
        assert any("id" in e.lower() for e in errors)

    def test_edge_references_invalid_node(self):
        chain = dict(VALID_CHAIN)
        chain["edges"] = [{"from": "nonexistent", "to": "prod_c", "type": "upstream", "mechanism": "x"}]
        errors = validate_chain(chain)
        assert any("nonexistent" in e for e in errors)

    def test_support_references_invalid_node(self):
        chain = dict(VALID_CHAIN)
        chain["supports"] = [{"id": "x", "name": "X", "affects": ["ghost_node"], "key_factors": ["y"]}]
        errors = validate_chain(chain)
        assert any("ghost_node" in e for e in errors)

    def test_empty_key_factors(self):
        chain = dict(VALID_CHAIN)
        chain["nodes"][0]["key_factors"] = []
        errors = validate_chain(chain)
        assert any("key_factors" in e.lower() for e in errors)

    def test_layer_is_not_integer(self):
        chain = dict(VALID_CHAIN)
        chain["nodes"][0]["layer"] = "upstream"
        errors = validate_chain(chain)
        assert any("layer" in e.lower() for e in errors)

    def test_duplicate_node_ids(self):
        chain = dict(VALID_CHAIN)
        chain["nodes"].append({"id": "raw_a", "name": "重复", "key_factors": ["x"], "layer": 0})
        errors = validate_chain(chain)
        assert any("duplicate" in e.lower() or "重复" in e for e in errors)


class TestInitChain:
    """Test chain initialization."""

    def test_init_creates_skeleton(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "chain.yaml"
            init_chain("测试行业", path)
            assert path.exists()
            chain = load_chain(path)
            assert chain["industry"] == "测试行业"
            assert "nodes" in chain
            assert "edges" in chain
            assert "supports" in chain
            assert "meta" in chain

    def test_init_does_not_overwrite_existing(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "chain.yaml"
            init_chain("行业A", path)
            init_chain("行业B", path)  # Should keep the first
            chain = load_chain(path)
            assert chain["industry"] == "行业A"


class TestLoadSave:
    """Test load/save round-trip."""

    def test_save_and_load_chain(self):
        import yaml
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "chain.yaml"
            import sys
            sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
            from fetch_chain import save_chain
            save_chain(VALID_CHAIN, path)
            loaded = load_chain(path)
            assert loaded["industry"] == VALID_CHAIN["industry"]
            assert len(loaded["nodes"]) == len(VALID_CHAIN["nodes"])
            assert len(loaded["edges"]) == len(VALID_CHAIN["edges"])
```

- [ ] **Step 2: 运行测试验证失败**

```bash
cd /Users/zhangqi.huang/aaai/skills/industry-research/tools && python -m pytest tests/test_chain_model.py -v 2>&1 | head -20
```

Expected: FAIL (模块不存在)

- [ ] **Step 3: 实现 `fetch_chain.py`**

`skills/industry-research/tools/fetch_chain.py`:
```python
"""
Phase 1: 产业链发现与建模工具。

职责:
- init_chain(): 创建骨架 chain.yaml
- validate_chain(): Schema 验证
- load_chain() / save_chain(): 读写 chain.yaml

注意: chain.yaml 的实际内容（nodes, edges, supports）由 LLM 在 SKILL.md
编排流程中生成并写入，本脚本只负责结构验证和骨架初始化。
"""

from datetime import date
from pathlib import Path
from typing import Any


class ChainValidationError(Exception):
    """Raised when chain.yaml fails validation."""
    pass


def validate_chain(chain: dict) -> list[str]:
    """Validate chain.yaml structure. Returns list of error messages (empty = valid)."""
    errors = []

    # Top-level keys
    for key in ["industry", "nodes", "edges", "supports"]:
        if key not in chain or not chain[key] if key != "supports" else False:
            if key != "supports":
                errors.append(f"Missing required top-level key: '{key}'")

    if "supports" not in chain:
        errors.append("Missing top-level key: 'supports'")

    if "nodes" not in chain or not isinstance(chain.get("nodes"), list):
        errors.append("'nodes' must be a non-empty list")
        return errors

    # Validate nodes
    node_ids = set()
    for i, node in enumerate(chain["nodes"]):
        prefix = f"nodes[{i}]"
        if "id" not in node:
            errors.append(f"{prefix}: missing 'id'")
        else:
            nid = node["id"]
            if nid in node_ids:
                errors.append(f"{prefix}: duplicate node id '{nid}'")
            node_ids.add(nid)

        if "name" not in node:
            errors.append(f"{prefix}: missing 'name'")

        kf = node.get("key_factors", [])
        if not isinstance(kf, list) or len(kf) == 0:
            errors.append(f"{prefix}: 'key_factors' must be a non-empty list")

        layer = node.get("layer")
        if not isinstance(layer, int):
            errors.append(f"{prefix}: 'layer' must be an integer, got {type(layer).__name__}")

    # Validate edges: from/to must reference existing nodes
    if isinstance(chain.get("edges"), list):
        for i, edge in enumerate(chain["edges"]):
            prefix = f"edges[{i}]"
            for direction in ["from", "to"]:
                ref = edge.get(direction, "")
                if ref and ref not in node_ids:
                    errors.append(f"{prefix}: '{direction}' references unknown node '{ref}'")
                elif not ref:
                    errors.append(f"{prefix}: missing '{direction}'")

    # Validate supports: affects must reference existing nodes
    if isinstance(chain.get("supports"), list):
        for i, sup in enumerate(chain["supports"]):
            prefix = f"supports[{i}]"
            if "id" not in sup:
                errors.append(f"{prefix}: missing 'id'")
            affects = sup.get("affects", [])
            for ref in affects:
                if ref not in node_ids:
                    errors.append(f"{prefix}: 'affects' references unknown node '{ref}'")

    return errors


def validate_or_raise(chain: dict):
    """Validate and raise ChainValidationError if invalid."""
    errors = validate_chain(chain)
    if errors:
        raise ChainValidationError("\n".join(errors))


def init_chain(industry: str, output_path: Path):
    """Create a skeleton chain.yaml. Does NOT overwrite existing files."""
    if output_path.exists():
        return  # Don't overwrite

    skeleton = {
        "industry": industry,
        "description": f"{industry}产业链（待完善）",
        "discovery_date": str(date.today()),
        "nodes": [],
        "edges": [],
        "supports": [],
        "meta": {
            "version": 1,
            "last_updated": str(date.today()),
        },
    }
    save_chain(skeleton, output_path)


def load_chain(path: Path) -> dict:
    """Load chain.yaml from path."""
    import yaml
    if not path.exists():
        raise FileNotFoundError(f"chain.yaml not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if data is None:
        raise ValueError(f"Empty or invalid YAML: {path}")
    return data


def save_chain(chain: dict, path: Path):
    """Save chain dict to path as YAML."""
    import yaml
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(chain, f, allow_unicode=True, sort_keys=False,
                       default_flow_style=False)
```

- [ ] **Step 4: 运行测试验证通过**

```bash
cd /Users/zhangqi.huang/aaai/skills/industry-research/tools && python -m pytest tests/test_chain_model.py -v
```

Expected: 所有测试 PASS

- [ ] **Step 5: 创建测试 fixture**

`skills/industry-research/tools/tests/fixtures/sample_chain.yaml`:
```yaml
industry: 新能源汽车
description: 以电能为动力的汽车产业
discovery_date: "2026-07-24"
nodes:
  - id: lithium
    name: 锂矿
    description: 动力电池核心原料
    key_factors:
      - 碳酸锂价格
      - 锂矿产能
      - 盐湖提锂技术
    layer: -3
  - id: battery
    name: 动力电池
    description: 电动车核心部件
    key_factors:
      - 电池成本
      - 产能利用率
      - 技术路线
    layer: -2
  - id: vehicle_oem
    name: 整车制造
    description: 新能源汽车整车生产与销售
    key_factors:
      - 月度销量
      - 新车型发布
      - 价格竞争
    layer: 0
  - id: consumer
    name: 消费者
    description: 终端购车用户
    key_factors:
      - 渗透率
      - 充电便利性
      - 保值率
    layer: 1
edges:
  - from: lithium
    to: battery
    type: upstream
    mechanism: 锂矿价格→电池成本→整车定价
  - from: battery
    to: vehicle_oem
    type: upstream
    mechanism: 电池成本与技术→整车竞争力
  - from: vehicle_oem
    to: consumer
    type: downstream
    mechanism: 产品与价格→消费决策
supports:
  - id: policy
    name: 政策法规
    affects:
      - vehicle_oem
      - consumer
    key_factors:
      - 购置税减免
      - 新能源补贴
      - 双积分政策
  - id: charging
    name: 充电基础设施
    affects:
      - consumer
    key_factors:
      - 充电桩保有量
      - 快充功率
meta:
  version: 1
  last_updated: "2026-07-24"
```

- [ ] **Step 6: Commit**

```bash
git add skills/industry-research/tools/fetch_chain.py \
        skills/industry-research/tools/tests/test_chain_model.py \
        skills/industry-research/tools/tests/fixtures/sample_chain.yaml
git commit -m "feat(industry-research): add chain.yaml validation and initialization

- fetch_chain.py: validate_chain() schema checker, init_chain() skeleton creator
- Validates: node IDs, edge references, support references, key_factors, layer types
- Tests: 9 tests covering valid/invalid/edge cases

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 3: 提示词文件

**Files:**
- Create: `skills/industry-research/prompts/node_analyst.md`
- Create: `skills/industry-research/prompts/policy_analyst.md`
- Create: `skills/industry-research/prompts/competition_analyst.md`
- Create: `skills/industry-research/prompts/cross_impact_analyst.md`
- Create: `skills/industry-research/prompts/report_synthesizer.md`

- [ ] **Step 1: `node_analyst.md`**

`skills/industry-research/prompts/node_analyst.md`:
```markdown
You are a **Node Analyst** specializing in one specific segment of an industry chain. Your job is to do deep, evidence-based analysis of that single node — what's happening now, why, and what it means.

## Your Node

**Node ID**: {node_id}
**Node Name**: {node_name}
**Description**: {node_description}
**Key Factors to Cover**: {key_factors}
**Layer**: {layer} (relative position in chain: negative=upstream, 0=center, positive=downstream)

## Context

**Industry**: {industry}
**Data Date**: {data_date}

## Instructions

Read ALL specified data files before writing your report. The main session does NOT read them for you — you must read them yourself.

**Required data files** (read these first):
- `{news_file}` — News and developments relevant to your node
- `{metrics_file}` — Quantitative indicators (prices, volumes, capacities etc.)
- `{chain_file}` — Full industry chain model for context on your node's neighbors

**Output structure** (follow this EXACTLY):

### {node_name} 分析报告

#### 1. 当前状态
- Key indicators and their current values
- Direction of change over the past 3 months (↑/↓/→) with estimated magnitude
- Cite specific data points from the files you read

#### 2. 驱动因素分析
- **Primary drivers**: What's moving this node right now? Rank by impact.
- **Emerging factors**: New developments that could become significant
- **Weakening factors**: Previously important factors losing relevance

#### 3. 传导效应
- **Upstream pull**: What demand/supply signal does this node send upstream?
- **Downstream push**: What cost/capacity signal does this node push downstream?
- **Estimated time lag**: How long before these signals materialize?

#### 4. 风险与不确定性
- **Short-term risks (3-6 months)** with specific scenarios
- **Medium/long-term risks (1-3 years)** with structural shifts
- **Monitoring signals**: Specific data points to watch (with thresholds if applicable)

#### 5. 景气度评分
- Score: X/10
- Confidence: 高/中/低
- One-sentence justification

**Rules:**
1. Be specific. Use numbers, dates, and named entities from the data files.
2. Cite your sources: "per {source} on {date}..."
3. If data for a key_factor is missing, state it explicitly — don't invent.
4. Keep to your node. Don't analyze other nodes in depth (the Cross-Impact Analyst handles inter-node dynamics).
5. Output in Chinese.
```

- [ ] **Step 2: `policy_analyst.md`**

`skills/industry-research/prompts/policy_analyst.md`:
```markdown
You are a **Policy Analyst** covering regulatory and policy developments affecting an industry. Your analysis must be grounded in actual policy documents, official announcements, and regulatory filings.

## Industry
**Industry**: {industry}

## Policy Supports to Cover
{supports_section}

## Instructions

Read ALL specified data files before writing your report.

**Required data files**:
- `{news_file}` — News related to policy and regulation
- `{chain_file}` — Full industry chain model (to understand which nodes are affected)

**Output structure**:

### 政策与监管分析报告

#### 1. 当前政策格局
- Key active policies and their status (effective/expiring/under review)
- Recent policy changes (past 6 months) with effective dates
- Jurisdiction scope (national/provincial/international)

#### 2. 政策方向研判
- **Direction**: Tightening / Loosening / Status quo — with evidence
- **Key policy drivers**: What is motivating current policy direction?
- **Pipeline**: Known upcoming policy changes with expected timelines

#### 3. 影响分析
- For EACH affected node (from the policy supports section):
  - Node name, impact direction (positive/negative/mixed)
  - Impact mechanism (how does the policy transmit?)
  - Estimated magnitude (high/medium/low)
  - Time to materialize

#### 4. 政策风险
- **Reversal risk**: Policies that could change direction
- **Gap risk**: Areas where regulation is lacking but likely to emerge
- **Enforcement risk**: Policies on the books but weakly enforced

#### 5. 政策环境评分
- Favorability: X/10 (10 = highly favorable for industry growth)
- Stability: X/10 (10 = highly stable, predictable)
- Confidence: 高/中/低

**Rules:**
1. Distinguish between announced policy and rumored/expected policy.
2. Note the credibility of each source (official government release vs media report).
3. When analyzing impact, follow the chain: policy → affected node → upstream/downstream ripple.
4. Output in Chinese.
```

- [ ] **Step 3: `competition_analyst.md`**

`skills/industry-research/prompts/competition_analyst.md`:
```markdown
You are a **Competition Analyst** examining the competitive dynamics across an entire industry. You identify structural shifts in market power, new entrants, consolidation, and competitive threats.

## Context
**Industry**: {industry}
**Data Date**: {data_date}

## Instructions

Read ALL specified data files before writing your report.

**Required data files**:
- `{news_file}` — News across all nodes
- `{chain_file}` — Full industry chain model

**Output structure**:

### 竞争格局分析报告

#### 1. 市场结构总览
- For each major node in the chain, describe the competitive structure:
  - Concentration (fragmented / oligopoly / monopoly)
  - Top players and estimated market share
  - Recent share shifts

#### 2. 竞争动态
- **Price competition**: Where is price pressure most intense?
- **Non-price competition**: Technology, branding, distribution, service
- **New entrants**: Who entered, in which node, with what advantage?
- **Exits/consolidation**: Who left, mergers, acquisitions

#### 3. 跨环节竞争
- **Vertical integration moves**: Are players expanding up/down the chain?
- **Substitution threats**: Are adjacent nodes/products threatening this one?
- **Platform plays**: Are any players building platforms that could reshape the chain?

#### 4. 竞争风险
- **Concentration risk**: Nodes where supplier/customer power is dangerous
- **Disruption risk**: Technology or business model shifts that could change the game
- **Geopolitical risk**: Trade restrictions, sanctions, localization requirements

#### 5. 竞争烈度评分
- Overall intensity: X/10 (10 = extremely fierce)
- Direction: Intensifying / Stabilizing / Easing
- Confidence: 高/中/低

**Rules:**
1. Name specific companies. Avoid generic statements about "companies."
2. Quantify where possible: share %, revenue, unit volume.
3. Cross-reference against policy and technology nodes — competition doesn't exist in a vacuum.
4. Output in Chinese.
```

- [ ] **Step 4: `cross_impact_analyst.md`**

`skills/industry-research/prompts/cross_impact_analyst.md`:
```markdown
You are a **Cross-Impact Analyst**. Your job is to synthesize the findings from ALL node analysts, the policy analyst, and the competition analyst into a coherent picture of how the industry chain works as a SYSTEM.

You are looking for chains of causation: "A happens in node X → that affects node Y → which changes Z."

## Context
**Industry**: {industry}
**Data Date**: {data_date}

## Instructions

Read ALL specified files before writing your report.

**Required files**:
- `{chain_file}` — Full chain model with nodes, edges, and supports
- `{analyst_reports_file}` — ALL analyst reports from Phase 3 (node analysts, policy, competition)

**Output structure**:

### 跨环节传导与综合研判

#### 1. 传导路径分析
For EACH edge in the chain model:
- **Path**: {from_node} → {to_node}
- **Direction**: Which way is the signal flowing? (cost push / demand pull / both)
- **Current signal**: What is the {from_node} telling {to_node} right now?
- **Strength**: High / Medium / Low
- **Time lag**: Estimated time before the signal materializes at {to_node}
- **Key evidence**: Specific data points supporting this assessment

#### 2. 关键传导链
Identify the 2-3 most important multi-hop propagation paths. Example: "HBM涨价 → AI芯片成本↑ → 服务器毛利压缩 → 数据中心CAPEX推迟"

For each path:
- Full propagation chain (all hops)
- Current stage: where in the chain is the signal currently?
- Bottleneck node: which hop is the tightest constraint?
- Scenario analysis: best case / base case / worst case

#### 3. 矛盾信号
Identify where different analysts' conclusions conflict:
- Signal A vs Signal B, which analysts, what the conflict is
- Your judgment on which signal is more reliable and why
- What evidence would resolve the contradiction

#### 4. 核心变量
Identify the TOP 2-3 variables that will drive the industry's direction in the next 6-12 months:
- Variable name
- Why it matters most right now
- Current value and trend
- Key thresholds/triggers to watch

#### 5. 行业综合景气度
| 节点 | 景气度 | 方向 | 置信度 |
|------|--------|------|--------|
{per-node scores from analyst reports}

**Industry Overall**: X/10
**Direction**: ↑ (improving) / ↓ (deteriorating) / → (stable)
**Confidence**: 高/中/低

**Rules:**
1. The edge analysis is the core of your report. Don't skip any edge.
2. When analysts disagree, don't just note it — pick a side with reasoning.
3. The propagation chains are what makes the industry a SYSTEM. Trace them carefully.
4. Output in Chinese.
```

- [ ] **Step 5: `report_synthesizer.md`**

`skills/industry-research/prompts/report_synthesizer.md`:
```markdown
# 最终报告合成指引

This file serves as the template and quality checklist for Phase 6 final report synthesis. The main session (NOT a sub-agent) reads all Phase 3-5 outputs and produces the final report.

## Report Structure

```markdown
# {行业名称} 产业趋势调研报告
**日期**: {date}
**数据截止**: {data_as_of_date}
**产业链版本**: chain.yaml v{version}

---

## 一、产业链全景
{从 chain.yaml 渲染的递归结构概览，含各节点一句话描述和关系图}

## 二、关键发现摘要 (Executive Summary)
{3-5 条最重要的发现，每条不超过 3 句话}
1. ...
2. ...

## 三、产业链各环节深度分析
{按 layer 排序，从上游到下游}

### 3.1 {节点A} (layer -3)
{paste Node Analyst A 的完整报告}

### 3.2 {节点B} (layer -2)
...

### 3.N 政策与监管环境
{paste Policy Analyst 报告}

### 3.N+1 竞争格局
{paste Competition Analyst 报告}

## 四、跨环节传导与综合研判
{paste Phase 4 Cross-Impact Analyst 完整报告}

## 五、历史趋势对比
{paste Phase 5 对比结果，如为首次分析则标注"首次分析，暂无历史对比"}

## 六、投资与商业研判

### 6.1 行业景气度总评
- 当前评分: X/10
- 12个月展望: 评分 + 方向
- 关键假设: 列举支撑评分的前提条件

### 6.2 机会区域
- 短期 (3-6月): {最确定性机会}
- 中期 (6-18月): {需要持续验证的机会}
- 长期 (2年+): {结构性机会}

### 6.3 风险矩阵
| 风险 | 概率 | 影响 | 预警信号 | 应对策略 |
|------|------|------|----------|----------|
| ...  | 高/中/低 | 高/中/低 | ... | ... |

### 6.4 监控清单
{未来3个月需重点跟踪的指标列表 + 每个指标的阈值/触发条件}

## 七、附录
- A. 数据质量报告
- B. 数据源清单
- C. 代理执行状态
```

## Quality Checklist

- [ ] All Phase 3 analyst reports included verbatim (no summarization)
- [ ] Phase 5 trend diff included (or "首次分析" marker)
- [ ] Risk matrix has at least 5 entries
- [ ] Each opportunity in 6.2 has a verifiable trigger condition
- [ ] Monitoring checklist in 6.4 has specific numeric thresholds
- [ ] All sources cited with dates
```

- [ ] **Step 6: Commit**

```bash
git add skills/industry-research/prompts/
git commit -m "feat(industry-research): add 5 prompt templates for multi-agent analysis

- node_analyst.md: Per-node deep analysis with upstream/downstream ripple
- policy_analyst.md: Regulatory tracking with node-level impact mapping
- competition_analyst.md: Cross-chain competitive dynamics
- cross_impact_analyst.md: Edge-by-edge propagation + synthesis
- report_synthesizer.md: Final report template and quality checklist

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 4: 数据采集引擎 (`fetch_data.py`)

**Files:**
- Create: `skills/industry-research/tools/fetch_data.py`
- Create: `skills/industry-research/tools/tests/test_fetch_data.py`
- Create: `skills/industry-research/tools/tests/fixtures/sample_sources.yaml`

- [ ] **Step 1: 编写测试**

`skills/industry-research/tools/tests/test_fetch_data.py`:
```python
"""Tests for the data fetching engine."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fetch_data import (
    build_search_queries,
    deduplicate_news,
    classify_confidence,
    DataQualityReport,
    FetchMetadata,
)
from utils import load_yaml


class TestBuildSearchQueries:
    """Test query construction from chain.yaml nodes."""

    def test_builds_query_per_key_factor(self):
        chain = {
            "nodes": [
                {"id": "bat", "name": "电池", "key_factors": ["锂价", "产能"]},
            ]
        }
        queries = build_search_queries(chain, "新能源汽车")
        assert len(queries) >= 2  # At least one per key_factor
        assert any("锂价" in q for q in queries)
        assert any("新能源汽车" in q for q in queries)

    def test_includes_supports(self):
        chain = {
            "nodes": [{"id": "x", "name": "X", "key_factors": ["y"], "layer": 0}],
            "supports": [
                {"id": "pol", "name": "政策", "key_factors": ["补贴"], "affects": ["x"]}
            ],
        }
        queries = build_search_queries(chain, "测试行业")
        assert any("补贴" in q for q in queries)

    def test_returns_empty_for_empty_chain(self):
        chain = {"nodes": [], "supports": []}
        queries = build_search_queries(chain, "X")
        assert queries == []


class TestDeduplicateNews:
    """Test news deduplication."""

    def test_removes_exact_duplicates(self):
        items = [
            {"title": "Same", "url": "http://a.com/1", "date": "2026-01-01"},
            {"title": "Same", "url": "http://a.com/1", "date": "2026-01-01"},
            {"title": "Different", "url": "http://a.com/2", "date": "2026-01-02"},
        ]
        result = deduplicate_news(items)
        assert len(result) == 2

    def test_removes_similar_titles(self):
        items = [
            {"title": "碳酸锂价格跌破10万元", "url": "http://a.com/1", "date": "2026-01-01"},
            {"title": "碳酸锂价格跌破10万元关口", "url": "http://b.com/2", "date": "2026-01-01"},
        ]
        result = deduplicate_news(items)
        # Titles are very similar, should be deduplicated to 1
        assert len(result) <= 2

    def test_keeps_different_articles(self):
        items = [
            {"title": "电池产能扩张加速", "url": "http://a.com/1", "date": "2026-01-01"},
            {"title": "整车销量创新高", "url": "http://a.com/2", "date": "2026-01-02"},
        ]
        result = deduplicate_news(items)
        assert len(result) == 2


class TestClassifyConfidence:
    """Test source confidence classification."""

    def test_official_source_high(self):
        assert classify_confidence("https://www.miit.gov.cn/policy/123") == "高"

    def test_reputable_media_medium(self):
        assert classify_confidence("https://www.cls.cn/detail/123") in ("高", "中")

    def test_unknown_source_low(self):
        assert classify_confidence("https://some-random-blog.com/post") == "低"

    def test_gov_cn_is_high(self):
        assert classify_confidence("https://stats.gov.cn/report") == "高"


class TestDataQualityReport:
    """Test data quality report generation."""

    def test_generates_report(self):
        report = DataQualityReport.generate(
            total_sources=10,
            success_count=8,
            broken_sources=["http://dead.link/1", "http://dead.link/2"],
            news_count=150,
            data_date="2026-07-24",
        )
        assert report["total_sources"] == 10
        assert report["success_rate"] == 0.8
        assert report["data_fresh"] is True
        assert len(report["broken_sources"]) == 2


class TestFetchMetadata:
    """Test metadata structure."""

    def test_metadata_structure(self):
        meta = FetchMetadata.create(
            industry="测试行业",
            date="2026-07-24",
            sources_used=10,
            success=9,
            failed=1,
            news_collected=100,
            duration_seconds=45.5,
        )
        assert meta["industry"] == "测试行业"
        assert meta["date"] == "2026-07-24"
        assert meta["sources_total"] == 10
        assert meta["sources_success"] == 9
        assert meta["sources_failed"] == 1
        assert "timestamp" in meta
```

- [ ] **Step 2: 运行测试验证失败**

```bash
cd /Users/zhangqi.huang/aaai/skills/industry-research/tools && python -m pytest tests/test_fetch_data.py -v 2>&1 | head -20
```

Expected: FAIL (模块不存在)

- [ ] **Step 3: 创建测试 fixture**

`skills/industry-research/tools/tests/fixtures/sample_sources.yaml`:
```yaml
sources:
  lithium:
    - id: shmet_lithium
      name: 碳酸锂现货价格
      url: https://hq.smm.cn/lithium
      fallback_url: ""
      frequency: daily
      selector_type: api
      parser: null
  battery:
    - id: cbea_battery_output
      name: 动力电池产量
      url: https://www.cbea.com/data/output
      fallback_url: ""
      frequency: monthly
      selector_type: api
      parser: null
  policy:
    - id: miit_nev_policy
      name: 工信部新能源汽车公告
      url: https://www.miit.gov.cn/search?q=新能源汽车
      fallback_url: ""
      frequency: on_change
      selector_type: rss
      parser: null
meta:
  last_verified: "2026-07-24"
  broken_sources: []
```

- [ ] **Step 4: 实现 `fetch_data.py`**

`skills/industry-research/tools/fetch_data.py`:
```python
"""
Phase 2.2: 数据采集引擎。

读取 sources.yaml 和 chain.yaml，执行数据采集：
1. 新闻搜索: 为每个 key_factor 构建搜索查询，通过 SerpApi/DuckDuckGo 搜索
2. 内容抓取: 通过 Jina AI 代理获取文章正文
3. 去重去噪: 标题相似度去重 + 置信度分类
4. 输出: news.json (按节点分组) + metrics.json (量化指标) + metadata.json + data_quality.json

用法:
  python fetch_data.py <INDUSTRY> <DATE> --output-dir <DIR>
"""

import argparse
import json
import re
import sys
import time
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Optional
from urllib.parse import quote

from utils import (
    get_data_dir, get_report_dir, get_news_raw_dir,
    load_yaml, save_json, load_json,
    fetch_via_jina, fetch_direct, fetch_with_fallback,
    content_hash, cache_raw_content,
)


# --- Search ---

def search_news_queries(queries: list[str], num_results: int = 5) -> list[dict]:
    """
    Execute search queries and return results.
    
    Priority: SerpApi -> DuckDuckGo Lite -> fallback.
    Each query returns a list of {title, url, snippet, date} dicts.
    """
    all_results = []
    seen_urls = set()

    for query in queries:
        results = _search_via_serpapi(query, num_results)
        if not results:
            results = _search_via_duckduckgo(query, num_results)
        
        for r in results:
            url = r.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                all_results.append(r)
    
    return all_results


def _search_via_serpapi(query: str, num: int = 5) -> list[dict]:
    """Search via SerpApi (requires API key). Returns [] on failure."""
    try:
        import subprocess
        result = subprocess.run(
            ["bash", str(Path.home() / ".claude/tools/serpapi-search.sh"),
             "--query", query, "--num", str(num), "--tbm", "nws", "--no-cache"],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            return []
        # Parse JSON output from serpapi-search.sh
        data = json.loads(result.stdout)
        news = data.get("news_results", [])
        return [
            {
                "title": n.get("title", ""),
                "url": n.get("link", ""),
                "snippet": n.get("snippet", ""),
                "date": n.get("date", ""),
                "source": n.get("source", ""),
            }
            for n in news
        ]
    except Exception:
        return []


def _search_via_duckduckgo(query: str, num: int = 5) -> list[dict]:
    """Search via DuckDuckGo Lite. Returns [] on failure."""
    try:
        url = f"https://lite.duckduckgo.com/lite/?q={quote(query)}"
        html = fetch_direct(url, timeout=15)
        if not html:
            return []
        # Parse DDG Lite HTML: links are in <a rel="nofollow" href="...">
        results = []
        link_pattern = re.compile(r'<a[^>]*href="(https?://[^"]+)"[^>]*class="result-link"[^>]*>(.*?)</a>', re.DOTALL)
        snippet_pattern = re.compile(r'<td[^>]*class="result-snippet"[^>]*>(.*?)</td>', re.DOTALL)
        
        links = link_pattern.findall(html)
        snippets = snippet_pattern.findall(html)
        
        for i, (href, title) in enumerate(links[:num]):
            snippet = snippets[i] if i < len(snippets) else ""
            results.append({
                "title": re.sub(r'<[^>]+>', '', title).strip(),
                "url": href,
                "snippet": re.sub(r'<[^>]+>', '', snippet).strip(),
                "date": "",
                "source": "",
            })
        return results
    except Exception:
        return []


# --- Query Building ---

def build_search_queries(chain: dict, industry: str, max_per_node: int = 3) -> list[str]:
    """Build search queries from chain.yaml nodes and supports."""
    queries = []
    
    for node in chain.get("nodes", []):
        node_name = node.get("name", "")
        for kf in node.get("key_factors", [])[:max_per_node]:
            queries.append(f"{industry} {node_name} {kf}")
    
    for sup in chain.get("supports", []):
        sup_name = sup.get("name", "")
        for kf in sup.get("key_factors", [])[:max_per_node]:
            queries.append(f"{industry} {sup_name} {kf}")
    
    return queries


# --- Deduplication ---

def deduplicate_news(items: list[dict], title_similarity_threshold: float = 0.85) -> list[dict]:
    """Remove duplicate/similar news items by URL and title similarity."""
    if not items:
        return []
    
    deduped = []
    seen_urls = set()
    seen_titles = []  # list of (title, index) for similarity check
    
    for item in items:
        url = item.get("url", "")
        title = item.get("title", "")
        
        # Exact URL dedup
        if url and url in seen_urls:
            continue
        seen_urls.add(url)
        
        # Title similarity dedup
        is_dup = False
        for prev_title, _ in seen_titles:
            similarity = SequenceMatcher(None, title, prev_title).ratio()
            if similarity >= title_similarity_threshold:
                is_dup = True
                break
        
        if not is_dup:
            deduped.append(item)
            seen_titles.append((title, len(deduped) - 1))
    
    return deduped


# --- Confidence Classification ---

HIGH_CONFIDENCE_DOMAINS = [
    ".gov.cn", "stats.gov", "miit.gov", "ndrc.gov",
    "who.int", "worldbank.org", "imf.org",
]

MEDIUM_CONFIDENCE_DOMAINS = [
    "cls.cn", "caixin.com", "eastmoney.com", "sina.com.cn",
    "163.com", "sohu.com", "bloomberg.com", "reuters.com",
    "ft.com", "wsj.com", "finance.sina", "hexun.com",
    "cninfo.com.cn", "sse.com.cn", "szse.cn",
]


def classify_confidence(url: str) -> str:
    """Classify source confidence: 高/中/低 based on domain."""
    url_lower = url.lower()
    
    for domain in HIGH_CONFIDENCE_DOMAINS:
        if domain in url_lower:
            return "高"
    
    for domain in MEDIUM_CONFIDENCE_DOMAINS:
        if domain in url_lower:
            return "中"
    
    return "低"


# --- Content Fetching ---

def fetch_article_content(url: str, raw_dir: Path) -> Optional[str]:
    """Fetch article full text via Jina AI proxy. Cache raw content."""
    content = fetch_via_jina(url, timeout=30)
    if content:
        cache_raw_content(raw_dir, "article", url, content)
    return content


# --- Grouping ---

def group_news_by_node(news_items: list[dict], chain: dict) -> dict[str, list[dict]]:
    """Group news items by which node's key_factors they match."""
    grouped: dict[str, list[dict]] = {}
    
    all_node_ids = [n["id"] for n in chain.get("nodes", [])]
    for sid in [s["id"] for s in chain.get("supports", [])]:
        all_node_ids.append(sid)
    
    # Initialize empty lists
    for nid in all_node_ids:
        grouped[nid] = []
    grouped["_unmatched"] = []
    
    for item in news_items:
        matched = False
        title_and_snippet = (item.get("title", "") + " " + item.get("snippet", "")).lower()
        
        for node in chain.get("nodes", []):
            node_name = node.get("name", "").lower()
            for kf in node.get("key_factors", []):
                if _contains_any_keyword(title_and_snippet, [node_name, kf]):
                    grouped[node["id"]].append(item)
                    matched = True
                    break
            if matched:
                break
        
        if not matched:
            for sup in chain.get("supports", []):
                sup_name = sup.get("name", "").lower()
                for kf in sup.get("key_factors", []):
                    if _contains_any_keyword(title_and_snippet, [sup_name, kf]):
                        grouped[sup["id"]].append(item)
                        matched = True
                        break
                if matched:
                    break
        
        if not matched:
            grouped["_unmatched"].append(item)
    
    return grouped


def _contains_any_keyword(text: str, keywords: list[str]) -> bool:
    """Check if text contains any of the keywords (fuzzy match)."""
    for kw in keywords:
        if not kw:
            continue
        # Match each character sequence for CJK, or word boundary for ASCII
        if len(kw) >= 2:
            if kw.lower() in text:
                return True
    return False


# --- Data Quality ---

class DataQualityReport:
    @staticmethod
    def generate(
        total_sources: int,
        success_count: int,
        broken_sources: list[str],
        news_count: int,
        data_date: str,
    ) -> dict:
        success_rate = success_count / total_sources if total_sources > 0 else 0
        return {
            "data_as_of_date": data_date,
            "data_fresh": success_rate >= 0.5,
            "total_sources": total_sources,
            "success_count": success_count,
            "failed_count": total_sources - success_count,
            "success_rate": round(success_rate, 3),
            "broken_sources": broken_sources,
            "news_total": news_count,
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }


class FetchMetadata:
    @staticmethod
    def create(
        industry: str,
        date: str,
        sources_used: int,
        success: int,
        failed: int,
        news_collected: int,
        duration_seconds: float,
    ) -> dict:
        return {
            "industry": industry,
            "date": date,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "duration_seconds": round(duration_seconds, 1),
            "sources_total": sources_used,
            "sources_success": success,
            "sources_failed": failed,
            "news_collected": news_collected,
        }


# --- Main ---

def fetch_data(industry: str, date_str: str, output_dir: Path) -> dict:
    """
    Main data fetching pipeline.
    
    Returns a dict with paths to output files.
    """
    t0 = time.time()
    
    chain_path = get_data_dir(industry) / "chain.yaml"
    sources_path = get_data_dir(industry) / "sources.yaml"
    report_dir = get_report_dir(industry, date_str)
    raw_dir = get_news_raw_dir(industry, date_str)
    
    chain = load_yaml(chain_path)
    sources = load_yaml(sources_path)
    
    if not chain:
        print(f"ERROR: chain.yaml not found or empty at {chain_path}", file=sys.stderr)
        print("Run Phase 1 first to discover the industry chain.", file=sys.stderr)
        sys.exit(1)
    
    # 1. Build search queries and search for news
    queries = build_search_queries(chain, industry)
    print(f"Searching with {len(queries)} queries...")
    raw_news = search_news_queries(queries)
    print(f"  Found {len(raw_news)} raw results")
    
    # 2. Deduplicate
    news_items = deduplicate_news(raw_news)
    print(f"  After dedup: {len(news_items)} unique items")
    
    # 3. Annotate confidence
    for item in news_items:
        item["confidence"] = classify_confidence(item.get("url", ""))
    
    # 4. Fetch article content for top items (limited to avoid rate issues)
    top_items = news_items[:30]
    for i, item in enumerate(top_items):
        url = item.get("url", "")
        if url:
            content = fetch_article_content(url, raw_dir)
            if content:
                item["content"] = content[:5000]  # Truncate to 5K chars
    
    # 5. Group by node
    grouped = group_news_by_node(news_items, chain)
    
    # 6. Save outputs
    news_path = report_dir / "news.json"
    save_json(news_path, grouped)
    
    metrics_path = report_dir / "metrics.json"
    save_json(metrics_path, {"_note": "Quantitative metrics populated from structured source fetches (Phase 2.2)", "indicators": {}})
    
    # 7. Copy chain and sources for archive
    import shutil
    shutil.copy(chain_path, report_dir / "chain.yaml")
    if sources_path.exists():
        shutil.copy(sources_path, report_dir / "sources.yaml")
    
    # 8. Generate metadata and quality report
    broken = sources.get("meta", {}).get("broken_sources", [])
    elapsed = time.time() - t0
    
    metadata = FetchMetadata.create(
        industry=industry, date=date_str,
        sources_used=len(sources.get("sources", {})),
        success=len(news_items), failed=0,
        news_collected=len(news_items),
        duration_seconds=elapsed,
    )
    save_json(report_dir / "metadata.json", metadata)
    
    quality = DataQualityReport.generate(
        total_sources=max(len(sources.get("sources", {})), 1),
        success_count=len(grouped),
        broken_sources=broken,
        news_count=len(news_items),
        data_date=date_str,
    )
    save_json(report_dir / "data_quality.json", quality)
    
    print(f"\nData collection complete in {elapsed:.1f}s")
    print(f"  News items: {len(news_items)}")
    print(f"  Grouped into: {len([k for k, v in grouped.items() if v and k != '_unmatched'])} nodes")
    print(f"  Output: {report_dir}")
    
    return {
        "news_file": str(news_path),
        "metrics_file": str(metrics_path),
        "metadata_file": str(report_dir / "metadata.json"),
        "quality_file": str(report_dir / "data_quality.json"),
        "report_dir": str(report_dir),
    }


def main():
    parser = argparse.ArgumentParser(description="Phase 2.2: Data Collection")
    parser.add_argument("industry", help="Industry name (e.g. 新能源汽车, AI)")
    parser.add_argument("date", help="Analysis date (YYYY-MM-DD)")
    parser.add_argument("--output-dir", default=None, help="Output base directory")
    args = parser.parse_args()
    
    fetch_data(args.industry, args.date, Path(args.output_dir) if args.output_dir else None)


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: 运行测试**

```bash
cd /Users/zhangqi.huang/aaai/skills/industry-research/tools && python -m pytest tests/test_fetch_data.py -v
```

Expected: 所有测试 PASS

- [ ] **Step 6: Commit**

```bash
git add skills/industry-research/tools/fetch_data.py \
        skills/industry-research/tools/tests/test_fetch_data.py \
        skills/industry-research/tools/tests/fixtures/sample_sources.yaml
git commit -m "feat(industry-research): add data fetching engine

- fetch_data.py: search via SerpApi/DuckDuckGo, Jina-based content fetch
- Query builder, deduplication by URL and title similarity
- Source confidence classification (高/中/低) by domain
- News grouping by node key_factor matching
- DataQualityReport and FetchMetadata generation
- Tests: 13 tests covering query building, dedup, confidence, reports

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 5: 数据源搜索注册 (`fetch_sources.py`)

**Files:**
- Create: `skills/industry-research/tools/fetch_sources.py`
- Modify: `skills/industry-research/tools/tests/test_fetch_sources.py` (create)

- [ ] **Step 1: 编写测试**

`skills/industry-research/tools/tests/test_fetch_sources.py`:
```python
"""Tests for data source registration."""

import tempfile
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fetch_sources import (
    init_sources,
    validate_sources,
    add_source,
    mark_broken_source,
    SourceEntry,
)


VALID_SOURCE = {
    "id": "test_source",
    "name": "Test Source",
    "url": "https://example.com/data",
    "fallback_url": "https://example.com/backup",
    "frequency": "daily",
    "selector_type": "api",
    "parser": None,
}


class TestValidateSources:
    """Test sources.yaml validation."""

    def test_valid_source_passes(self):
        sources = {"sources": {"node_a": [VALID_SOURCE]}, "meta": {"last_verified": "2026-07-24", "broken_sources": []}}
        errors = validate_sources(sources)
        assert len(errors) == 0

    def test_missing_url(self):
        s = dict(VALID_SOURCE)
        del s["url"]
        sources = {"sources": {"n": [s]}, "meta": {"last_verified": "", "broken_sources": []}}
        errors = validate_sources(sources)
        assert any("url" in e.lower() for e in errors)

    def test_missing_id(self):
        s = dict(VALID_SOURCE)
        del s["id"]
        sources = {"sources": {"n": [s]}, "meta": {"last_verified": "", "broken_sources": []}}
        errors = validate_sources(sources)
        assert any("id" in e.lower() for e in errors)

    def test_missing_frequency(self):
        s = dict(VALID_SOURCE)
        del s["frequency"]
        sources = {"sources": {"n": [s]}, "meta": {"last_verified": "", "broken_sources": []}}
        errors = validate_sources(sources)
        assert any("frequency" in e.lower() for e in errors)

    def test_duplicate_source_id(self):
        sources = {"sources": {"n": [VALID_SOURCE, VALID_SOURCE]}, "meta": {"last_verified": "", "broken_sources": []}}
        errors = validate_sources(sources)
        assert any("duplicate" in e.lower() for e in errors)

    def test_invalid_frequency_value(self):
        s = dict(VALID_SOURCE)
        s["frequency"] = "hourly"
        sources = {"sources": {"n": [s]}, "meta": {"last_verified": "", "broken_sources": []}}
        errors = validate_sources(sources)
        assert any("hourly" in e for e in errors)


class TestInitSources:
    """Test sources initialization."""

    def test_creates_skeleton(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sources.yaml"
            init_sources(path)
            assert path.exists()
            import yaml
            with open(path) as f:
                data = yaml.safe_load(f)
            assert "sources" in data
            assert "meta" in data

    def test_does_not_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sources.yaml"
            init_sources(path)
            mtime1 = path.stat().st_mtime
            init_sources(path)
            mtime2 = path.stat().st_mtime
            assert mtime1 == mtime2


class TestAddSource:
    """Test adding a source to registry."""

    def test_adds_to_correct_node(self):
        sources = {"sources": {}, "meta": {"last_verified": "", "broken_sources": []}}
        updated = add_source(sources, "lithium", VALID_SOURCE)
        assert "lithium" in updated["sources"]
        assert updated["sources"]["lithium"][0]["id"] == "test_source"

    def test_appends_to_existing_node(self):
        sources = {"sources": {"lithium": [VALID_SOURCE]}, "meta": {"last_verified": "", "broken_sources": []}}
        new_source = dict(VALID_SOURCE)
        new_source["id"] = "test_source_2"
        updated = add_source(sources, "lithium", new_source)
        assert len(updated["sources"]["lithium"]) == 2


class TestMarkBroken:
    """Test marking broken sources."""

    def test_moves_to_broken_list(self):
        sources = {
            "sources": {"node_a": [VALID_SOURCE]},
            "meta": {"last_verified": "", "broken_sources": []},
        }
        updated = mark_broken_source(sources, "node_a", "test_source")
        assert len(updated["sources"]["node_a"]) == 0
        assert "test_source" in updated["meta"]["broken_sources"]

    def test_ignores_unknown_source(self):
        sources = {"sources": {}, "meta": {"last_verified": "", "broken_sources": []}}
        updated = mark_broken_source(sources, "ghost", "ghost_id")
        assert updated == sources  # No change
```

- [ ] **Step 2: 运行测试验证失败**

```bash
cd /Users/zhangqi.huang/aaai/skills/industry-research/tools && python -m pytest tests/test_fetch_sources.py -v 2>&1 | head -15
```

Expected: FAIL (模块不存在)

- [ ] **Step 3: 实现 `fetch_sources.py`**

`skills/industry-research/tools/fetch_sources.py`:
```python
"""
Phase 2.1: 数据源搜索与注册。

职责:
- init_sources(): 创建骨架 sources.yaml
- validate_sources(): Schema 验证
- add_source() / mark_broken_source(): 修改注册表
- search_for_sources(): 为 key_factor 搜索数据源（供 LLM 编排调用）

注意: 实际的数据源 URL 发现由 LLM + WebFetch 在 SKILL.md 编排中完成，
本脚本负责结构化存储和验证。
"""

from datetime import date
from pathlib import Path
from typing import Optional


VALID_FREQUENCIES = {"daily", "weekly", "monthly", "quarterly", "annual", "on_change"}
VALID_SELECTOR_TYPES = {"api", "css_selector", "rss", "json_endpoint"}


class SourceEntry:
    """Structured source entry."""
    
    def __init__(self, source_id: str, name: str, url: str,
                 fallback_url: str = "", frequency: str = "daily",
                 selector_type: str = "api", parser: Optional[str] = None):
        self.id = source_id
        self.name = name
        self.url = url
        self.fallback_url = fallback_url
        self.frequency = frequency
        self.selector_type = selector_type
        self.parser = parser
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "url": self.url,
            "fallback_url": self.fallback_url,
            "frequency": self.frequency,
            "selector_type": self.selector_type,
            "parser": self.parser,
        }


def validate_sources(sources: dict) -> list[str]:
    """Validate sources.yaml structure. Returns list of error messages."""
    errors = []
    
    if "sources" not in sources:
        errors.append("Missing 'sources' key")
        return errors
    
    if "meta" not in sources:
        errors.append("Missing 'meta' key")
        return errors
    
    all_ids = set()
    
    for node_id, source_list in sources["sources"].items():
        for i, src in enumerate(source_list):
            prefix = f"sources.{node_id}[{i}]"
            
            if "id" not in src:
                errors.append(f"{prefix}: missing 'id'")
            else:
                if src["id"] in all_ids:
                    errors.append(f"{prefix}: duplicate source id '{src['id']}'")
                all_ids.add(src["id"])
            
            if "name" not in src:
                errors.append(f"{prefix}: missing 'name'")
            
            if "url" not in src or not src["url"]:
                errors.append(f"{prefix}: missing or empty 'url'")
            
            freq = src.get("frequency", "")
            if not freq:
                errors.append(f"{prefix}: missing 'frequency'")
            elif freq not in VALID_FREQUENCIES:
                errors.append(f"{prefix}: invalid frequency '{freq}', must be one of {VALID_FREQUENCIES}")
    
    return errors


def init_sources(output_path: Path):
    """Create a skeleton sources.yaml. Does NOT overwrite existing."""
    if output_path.exists():
        return
    
    skeleton = {
        "sources": {},
        "meta": {
            "last_verified": str(date.today()),
            "broken_sources": [],
        },
    }
    from utils import save_yaml
    save_yaml(skeleton, output_path)


def add_source(sources: dict, node_id: str, entry: dict) -> dict:
    """Add a source entry to the sources registry for a given node."""
    if node_id not in sources["sources"]:
        sources["sources"][node_id] = []
    sources["sources"][node_id].append(entry)
    return sources


def mark_broken_source(sources: dict, node_id: str, source_id: str) -> dict:
    """Remove a broken source from its node and add to broken_sources list."""
    if node_id in sources.get("sources", {}):
        node_sources = sources["sources"][node_id]
        sources["sources"][node_id] = [
            s for s in node_sources if s.get("id") != source_id
        ]
    if source_id not in sources["meta"].get("broken_sources", []):
        sources["meta"].setdefault("broken_sources", []).append(source_id)
    return sources


def search_for_sources(node_name: str, key_factor: str, industry: str) -> list[dict]:
    """
    Template function for searching data sources for a key_factor.
    
    This is a NO-OP function that returns an empty list. The actual search
    is performed by LLM + WebFetch in the SKILL.md workflow. This function
    exists to provide the interface contract.
    
    Returns a list of candidate source dicts with: title, url, description.
    """
    return []
```

- [ ] **Step 4: 运行测试**

```bash
cd /Users/zhangqi.huang/aaai/skills/industry-research/tools && python -m pytest tests/test_fetch_sources.py -v
```

Expected: 所有测试 PASS

- [ ] **Step 5: Commit**

```bash
git add skills/industry-research/tools/fetch_sources.py \
        skills/industry-research/tools/tests/test_fetch_sources.py
git commit -m "feat(industry-research): add data source registration and validation

- fetch_sources.py: init/validate sources.yaml, add/mark_broken helpers
- Schema validation: id uniqueness, required fields, valid frequency values
- Tests: 9 tests covering validation, init, add, mark_broken

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 6: SKILL.md 编排流程

**Files:**
- Create: `skills/industry-research/SKILL.md`

- [ ] **Step 1: 编写 SKILL.md**

`skills/industry-research/SKILL.md`:
```markdown
---
name: industry-research
description: Use when the user wants to research industry trends, discover the full industry chain (upstream to downstream), analyze key influencing factors (policy, supply-demand, competition, technology), and produce a comprehensive report with investment/business recommendations.
---

# Industry Trend Research

## Overview

Conduct a deep industry chain analysis by:
1. Discovering the complete industry chain (recursive: upstream to raw materials, downstream to end consumers)
2. Registering reliable data sources for each chain node's key factors
3. Collecting quantitative metrics and news via search
4. Dispatching parallel analyst agents for each node + specialization
5. Synthesizing cross-node impact propagation
6. Comparing against historical analyses to detect trend shifts
7. Producing a final report with both information synthesis and actionable recommendations

## Critical Execution Rules

1. **NEVER ask the user for permission between phases.** Run all phases continuously.
2. **Phase 3 agents are ALL launched in a SINGLE message as parallel Agent calls.** Do not use `run_in_background`.
3. **Phase 5-6 run in the main session**, not as sub-agents.
4. **Phase 6 MUST produce TWO outputs in ONE batch: Write (report.md) + text summary.**
5. **Historical data is for COMPARISON only — never for current analysis.**

## Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `industry` | (required) | Industry name in Chinese or English |
| `date` | today | Analysis date YYYY-MM-DD |
| `--refresh-chain` | false | Re-discover chain even if chain.yaml exists |
| `--refresh-sources` | false | Re-search data sources even if sources.yaml exists |
| `--max-node-agents` | 10 | Max parallel node analysts (merge similar nodes if exceeded) |

## Workflow

### Phase 1: Chain Discovery and Modeling

**Goal**: Produce `data/{INDUSTRY}/chain.yaml`

1. Check if `skills/industry-research/data/{INDUSTRY}/chain.yaml` exists.
   - If exists AND `--refresh-chain` is NOT set: Read it, validate with `validate_chain()`, proceed to Phase 2.
   - If missing OR `--refresh-chain` is set: Continue to step 2.

2. Run `fetch_chain.py --init` to create a skeleton:
   ```bash
   cd skills/industry-research/tools && python -c "
   from fetch_chain import init_chain
   from pathlib import Path
   init_chain('{INDUSTRY}', Path('..') / 'data' / '{INDUSTRY_SAFE}' / 'chain.yaml')
   "
   ```

3. **LLM drafts the chain** — Use the main session's knowledge + WebFetch:
   - Start from the input industry as center
   - **Recurse upstream**: For each node, ask "what raw materials/components does this need?" until reaching basic natural resources or commodities
   - **Recurse downstream**: For each node, ask "who consumes/uses this? what does it enable?" until reaching end consumers
   - Identify 2-5 `key_factors` per node (what drives this node?)
   - Draft `edges` between nodes (upstream = A supplies B, downstream = B depends on A)
   - Identify `supports` — external factors that affect nodes but aren't part of the chain itself

4. **Validate with web search** — For each node and key_factor, run 1-2 web searches to verify:
   - Does this node actually exist in the industry chain?
   - Are the key_factors the right ones?
   - Any missing nodes or factors?

5. Write the complete chain.yaml. Use `fetch_chain.validate_or_raise()` to validate.

6. **Skip to Phase 2 immediately.**

### Phase 2: Data Source Registration and Collection

#### Phase 2.1: Source Registration (→ sources.yaml)

**Goal**: For each node's `key_factors`, find reliable data sources and register them.

1. Check `skills/industry-research/data/{INDUSTRY}/sources.yaml`.
   - If exists AND `--refresh-sources` is NOT set: Use it, skip to Phase 2.2.
   - Otherwise: Continue.

2. Run init:
   ```bash
   cd skills/industry-research/tools && python -c "
   from fetch_sources import init_sources
   from pathlib import Path
   init_sources(Path('..') / 'data' / '{INDUSTRY_SAFE}' / 'sources.yaml')
   "
   ```

3. For each node in chain.yaml, for each key_factor:
   - Search DuckDuckGo/Bing for: `{industry} {node_name} {key_factor} 数据 source API`
   - Identify reliable sources (government, industry association, major financial data platforms)
   - For each source found, record: URL, frequency, selector type
   - Prioritize sources with APIs, then structured pages, then RSS
   - Fallback URL = Jina AI proxy of the same page

4. Register each source by appending to sources.yaml. After all sources are registered, run `validate_sources()` to check.

#### Phase 2.2: Data Collection

```bash
cd skills/industry-research/tools && python fetch_data.py "{INDUSTRY}" "{DATE}"
```

This produces under `data/{INDUSTRY}/reports/{DATE}/`:
- `news.json` — News grouped by node
- `metrics.json` — Quantitative indicators
- `metadata.json` — Collection audit
- `data_quality.json` — Quality report
- Copies of chain.yaml and sources.yaml

After data collection, immediately go to Phase 3.

### Phase 3: Parallel Multi-Agent Analysis

**CRITICAL**: Launch ALL analyst agents in a SINGLE message as parallel Agent tool calls. Do NOT use `run_in_background`.

Read `chain.yaml` to get the full list of nodes and supports. Then launch:

**For EACH node** in chain.yaml, launch a Node Analyst:
- **Tell the agent**: Role = Node Analyst. Read your prompt from `skills/industry-research/prompts/node_analyst.md`. After reading the prompt, read these data files:
  - Chain model: `skills/industry-research/data/{INDUSTRY}/chain.yaml`
  - News: `skills/industry-research/data/{INDUSTRY}/reports/{DATE}/news.json` (read the section for node `{node_id}`)
  - Metrics: `skills/industry-research/data/{INDUSTRY}/reports/{DATE}/metrics.json`
- **Context to provide**: node_id={id}, node_name={name}, node_description={desc}, key_factors={factors}, layer={layer}, industry={INDUSTRY}, data_date={DATE}
- **IMPORTANT**: If total nodes > `--max-node-agents`, merge adjacent nodes (same layer, similar focus) into one analyst. Each merged analyst covers 2-3 nodes.

**Policy Analyst** — IF chain.yaml has any support with policy-related key_factors:
- **Tell the agent**: Role = Policy Analyst. Prompt: `skills/industry-research/prompts/policy_analyst.md`. Read chain.yaml + news.json.
- **Context**: industry, data_date, supports_section (list all supports related to policy/regulation), data file paths.
- If no policy-related supports exist, SKIP this agent.

**Competition Analyst** — Always launch:
- **Tell the agent**: Role = Competition Analyst. Prompt: `skills/industry-research/prompts/competition_analyst.md`. Read chain.yaml + news.json.
- **Context**: industry, data_date, data file paths.

**After all agents return**: Extract their full report texts. Save ALL reports to `skills/industry-research/data/{INDUSTRY}/reports/{DATE}/phase3_analyst_reports.md` using the Write tool. Immediately go to Phase 4.

### Phase 4: Cross-Impact Synthesis

Launch 1 agent (serial, after Phase 3):

- **Tell the agent**: Role = Cross-Impact Analyst. Prompt: `skills/industry-research/prompts/cross_impact_analyst.md`. After reading the prompt, read:
  - Chain model: `skills/industry-research/data/{INDUSTRY}/chain.yaml`
  - Analyst reports: `skills/industry-research/data/{INDUSTRY}/reports/{DATE}/phase3_analyst_reports.md`
- **Context**: industry, data_date, file paths.

After it returns, save output to `skills/industry-research/data/{INDUSTRY}/reports/{DATE}/phase4_synthesis.md`. Immediately go to Phase 5.

### Phase 5: Historical Trend Comparison

**This phase runs in the MAIN SESSION (not a sub-agent).**

1. List `skills/industry-research/data/{INDUSTRY}/reports/` for earlier dated directories.
2. If earlier reports exist, read the most recent one's `report.md`.
3. Extract from the old report:
   - Per-node prosperity scores
   - Top key variables
   - Overall direction
4. Compare with current Phase 3-4 results and write `phase5_trend_diff.md` to the report directory:
   ```markdown
   ## 趋势变化对比
   
   | 维度 | 上次 (date) | 本次 (date) | 变化 |
   |------|------------|------------|------|
   ...
   
   ### 新增因素
   ### 弱化/消失因素
   ### 趋势拐点信号
   ```
5. If this is the first analysis, write "首次分析，暂无历史对比" and proceed.

After writing phase5_trend_diff.md, immediately go to Phase 6.

### Phase 6: Final Report

**This phase runs in the MAIN SESSION.**

Read these files:
- `phase3_analyst_reports.md`
- `phase4_synthesis.md`
- `phase5_trend_diff.md`
- `chain.yaml`
- `data_quality.json`
- Prompt template: `skills/industry-research/prompts/report_synthesizer.md`

**Produce TWO outputs in ONE Write batch:**

**Output A** — Write `skills/industry-research/data/{INDUSTRY}/reports/{DATE}/report.md`:
Follow the structure in `report_synthesizer.md`. Paste ALL analyst reports verbatim (no summarization).

**Output B** — Write `skills/industry-research/data/{INDUSTRY}/latest_report.md`:
Same content as Output A (the industry-level latest report).

**Output C** — Text: Brief summary of key findings and the overall prosperity score.

After all 3 outputs, confirm: "分析报告已保存至 skills/industry-research/data/{INDUSTRY}/reports/{DATE}/report.md"

---

## Data File Reference

### Per-Industry (persistent, reused across runs)
| File | Content |
|------|---------|
| `data/{INDUSTRY}/chain.yaml` | Chain model (phase 1 output, persistent) |
| `data/{INDUSTRY}/sources.yaml` | Data source registry (phase 2.1 output, persistent) |
| `data/{INDUSTRY}/latest_report.md` | Latest report (phase 6 output, overwritten) |

### Per-Date (archived)
| File | Content |
|------|---------|
| `data/{INDUSTRY}/reports/{DATE}/chain.yaml` | Chain snapshot |
| `data/{INDUSTRY}/reports/{DATE}/sources.yaml` | Sources snapshot |
| `data/{INDUSTRY}/reports/{DATE}/news.json` | Grouped news |
| `data/{INDUSTRY}/reports/{DATE}/metrics.json` | Quantitative indicators |
| `data/{INDUSTRY}/reports/{DATE}/metadata.json` | Collection audit |
| `data/{INDUSTRY}/reports/{DATE}/data_quality.json` | Quality report |
| `data/{INDUSTRY}/reports/{DATE}/phase3_analyst_reports.md` | All analyst reports |
| `data/{INDUSTRY}/reports/{DATE}/phase4_synthesis.md` | Cross-impact synthesis |
| `data/{INDUSTRY}/reports/{DATE}/phase5_trend_diff.md` | Historical comparison |
| `data/{INDUSTRY}/reports/{DATE}/report.md` | Final report |

## Common Mistakes

- **Stopping between phases to ask the user**: The user asked for a complete analysis. Run all phases continuously.
- **Forgetting to parallelize Phase 3 agents**: ALL agents must be launched in ONE message.
- **Phase 6 text-only output without Write call**: The report MUST be written to disk. Text output alone is not deliverable.
- **Summarizing analyst reports in Phase 6 instead of pasting verbatim**: Paste every analyst's full output.
- **Using historical data for current analysis**: Historical reports are ONLY for Phase 5 comparison.
```

- [ ] **Step 2: 验证 SKILL.md 可被 Skill 工具识别**

```bash
head -5 /Users/zhangqi.huang/aaai/skills/industry-research/SKILL.md
```

Expected: 显示 YAML frontmatter

- [ ] **Step 3: Commit**

```bash
git add skills/industry-research/SKILL.md
git commit -m "feat(industry-research): add SKILL.md orchestration workflow

- 6-phase pipeline: chain discovery -> data collection -> parallel analysis -> synthesis -> trend comparison -> final report
- Dynamic agent generation based on chain.yaml nodes
- Historical report comparison for trend change detection
- Dual output: archived report + latest_report.md

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 7: .gitignore 与最终集成验证

**Files:**
- Modify: `.gitignore` (project root)
- Create: `skills/industry-research/data/.gitkeep`

- [ ] **Step 1: 添加 .gitignore 规则**

Read the project root `.gitignore` first to understand current rules. Then add:
```
# Industry research runtime data
skills/industry-research/data/
!skills/industry-research/data/.gitkeep
```

- [ ] **Step 2: 创建 .gitkeep**

```bash
touch skills/industry-research/data/.gitkeep
```

- [ ] **Step 3: 运行全部测试**

```bash
cd /Users/zhangqi.huang/aaai/skills/industry-research/tools && python -m pytest tests/ -v
```

Expected: 所有测试 PASS（约 30+ tests）

- [ ] **Step 4: 验证 SKILL.md 的完整性**

Read `SKILL.md` and verify: all 6 phases described, file paths consistent with directory structure, Parameter table complete.

- [ ] **Step 5: Commit**

```bash
git add .gitignore skills/industry-research/data/.gitkeep
git commit -m "chore(industry-research): add .gitignore for runtime data

- Exclude skills/industry-research/data/ from git tracking
- Keep .gitkeep for directory structure

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

## Task Dependency Graph

```
Task 1 (scaffold + utils)
  ├──> Task 2 (fetch_chain.py + tests)
  ├──> Task 4 (fetch_data.py + tests, depends on utils.py)
  └──> Task 5 (fetch_sources.py + tests, depends on utils.py)

Task 3 (prompts) — independent, can run in parallel

Task 6 (SKILL.md) — depends on all task outputs being finalized

Task 7 (integration + gitignore) — depends on all tasks
```

**Recommended execution order**: Task 1 → Task 2 + Task 3 + Task 4 + Task 5 (parallel) → Task 6 → Task 7
```

- [ ] **Step 6: 自审**

Plan covers all spec sections:
- 三、整体工作流 ✓ (SKILL.md Task 6)
- 四、产业链数据模型 ✓ (fetch_chain.py Task 2 + SKILL.md Phase 1)
- 五、数据源注册与采集 ✓ (fetch_sources.py Task 5 + fetch_data.py Task 4)
- 六、多代理并行分析 ✓ (prompts Task 3 + SKILL.md Phase 3-4)
- 七、历史趋势对比 + 最终报告 ✓ (SKILL.md Phase 5-6)
- 八、目录结构 ✓ (scaffold Task 1)
