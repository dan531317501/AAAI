# 企业 RAG 核心技术方案：准确率与召回率优化

## 1. 文档目标

本文面向企业级知识库、技术文档问答、代码/API 检索、故障根因分析等场景，重点研究 RAG（Retrieval-Augmented Generation）的核心技术问题：

- 如何提升首阶段检索召回率；
- 如何提升候选结果排序准确率；
- 如何提升最终回答准确率、引用准确率和事实一致性；
- 如何选择 Embedding、Sparse Retrieval 和 Reranker 模型；
- 如何通过可复现的评测指标判断方案是否真的有效。

本文不把“最终回答准确率”当作唯一指标，而是将 RAG 拆成“候选召回 → 结果排序 → 证据组装 → 答案生成”四个环节，逐层定位问题和优化手段。

## 2. 结论摘要

企业 RAG 的第一版推荐基线为：

```text
结构化分块
  + 租户/ACL/版本过滤
  + BM25 关键词检索
  + Dense Embedding 检索
  + RRF 混合召回
  + Cross-Encoder Reranker
  + 父文档/邻居段落扩展
  + 去重和上下文压缩
  + 带引用、可拒答的 LLM 生成
```

模型建议：

1. 自托管首选：`Qwen3-Embedding-0.6B/4B + Qwen3-Reranker-0.6B/4B`。
2. 中文、代码、错误码、API 场景的强基线：`BGE-M3 + bge-reranker-v2-m3`。
3. 允许使用外部 API、追求质量上限：`Voyage-4-large + rerank-2.5`。
4. 不建议一开始直接使用 8B。应先证明 4B 相比 0.6B 的指标增益足以覆盖 GPU、延迟和成本。

核心判断：

> 先把 `Evidence Recall@100` 做高，再用 Reranker 提升 `nDCG@10`，最后通过上下文组装、引用约束和答案校验提升最终回答准确率。

## 3. RAG 的指标分层

### 3.1 指标总表

| 层级 | 核心指标 | 指标含义 | 主要优化手段 |
|---|---|---|---|
| 首阶段召回 | `Evidence Recall@100` | 正确证据是否进入候选集 | 分块、BM25、Embedding、混合检索、查询改写 |
| 排序质量 | `nDCG@10`、`MRR@10`、`Precision@10` | 正确证据是否排在前面 | Reranker、Hard Negative、候选集质量 |
| 最终回答 | Answer Accuracy、Citation Precision、Faithfulness | 回答是否正确、引用是否支持回答 | 上下文拼装、引用约束、答案校验 |
| 多跳问题 | `Complete Recall@K` | 所有必要证据是否都被召回 | 查询分解、父子文档、邻居扩展 |
| 企业安全 | ACL Leakage、错误版本命中 | 是否检索到无权限或过期信息 | 检索前过滤租户、权限、版本 |
| 工程约束 | p95 延迟、成本、吞吐 | 是否能够在线运行 | 模型尺寸、候选数量、缓存 |

Azure 的 RAG 评估指南也将 Recall@K、Precision@K、MRR 等作为检索层核心指标，不能只看最终 LLM 的主观评分。

参考：[Azure RAG 检索与评估指南](https://learn.microsoft.com/zh-cn/azure/architecture/ai-ml/guide/rag/rag-information-retrieval)

### 3.2 指标定义

#### Evidence Recall@K

```text
Evidence Recall@K
= Top-K 检索结果中命中的正确证据数量
  / 当前问题所需的正确证据总数量
```

这里的 gold evidence 最好精确到文档片段或页面区间，而不是只标注文档 ID。仅使用文档级 Hit@K 容易掩盖“命中了文档但没有命中答案所在段落”的问题。

#### Complete Recall@K

对于多跳问题，要求所有必要证据都被召回：

```text
Complete Recall@K
= 所有 required evidence 均出现在 Top-K 中的问题数
  / 多跳问题总数
```

例如一个问题同时需要“错误现象”“版本变更”和“修复方案”三个证据，缺少任意一个都不能算完整召回。

#### Citation Precision 与 Citation Recall

```text
Citation Precision
= 正确支持回答的引用数量 / 所有引用数量

Citation Recall
= 被回答实际使用并正确引用的 gold evidence 数量
  / 回答所需 gold evidence 总数量
```

这两个指标可以识别“回答看起来正确，但引用并不能支持结论”的问题。

### 3.3 指标与故障的对应关系

| 现象 | 优先查看 | 结论 | 优先改什么 |
|---|---|---|---|
| 正确文档根本搜不到 | `Evidence Recall@100` | 首阶段召回不足 | 分块、BM25、Embedding、混合检索 |
| 正确文档搜到了但排在后面 | `nDCG@10`、`MRR@10` | 排序不足 | Reranker、Hard Negative |
| 检索结果正确但回答错误 | Citation Precision、Faithfulness、Answer Accuracy | 证据组装或生成有问题 | 上下文压缩、引用约束、答案校验 |
| 多跳问题经常缺一段 | `Complete Recall@K` | 证据覆盖不完整 | 查询分解、父文档扩展、邻居扩展 |
| 旧文档经常被召回 | Version Hit、Stale Hit Rate | 版本治理不足 | 版本过滤、文档状态、时间权重 |
| 用户看到无权限信息 | ACL Leakage | 安全边界错误 | 在检索层执行权限过滤 |

最重要的边界是：

> Reranker 只能重新排序已有候选，不能找回没有进入候选集的证据。

## 4. 推荐整体技术链路

### 4.1 文档处理与分块

不要对所有文件使用统一固定长度切片，应采用结构感知的分块策略。

#### 通用文档

- 保留文档标题、章节标题和章节路径；
- 以段落、列表和语义边界切块；
- 将父文档 ID、章节路径、发布日期、版本号写入 metadata；
- 检索到子块后可扩展父块或相邻块。

#### API 文档

- 按接口、请求参数、响应参数、错误码分块；
- 保留 HTTP Method、URL、服务名、版本和权限信息；
- API 路径、字段名和错误码必须同时进入关键词索引。

#### 代码文档

- 按包、模块、类、函数和调用关系切块；
- 保留文件路径、符号名、分支、提交版本和行号；
- 代码符号和错误信息需要使用关键词检索补足向量检索的不足。

#### 表格和故障文档

- 表格需要保留表头、行列关系和单位；
- 故障文档建议保留“现象—原因—影响—修复—验证—版本”等字段；
- 不应将多列业务表格简单拼接为没有结构的长文本。

### 4.2 元数据和权限过滤

建议为每个 Chunk 保存以下字段：

```text
tenant_id
document_id
chunk_id
title
section_path
source_type
service
owner
version
status
published_at
updated_at
language
acl
symbol_names
api_paths
error_codes
```

租户、ACL、文档状态和版本条件应在检索阶段执行，而不是先检索所有数据、再在前端隐藏结果。多租户 RAG 的权限控制必须成为检索约束的一部分。

参考：[Azure 安全多租户 RAG](https://learn.microsoft.com/zh-cn/azure/architecture/ai-ml/guide/secure-multitenant-rag)

### 4.3 混合召回

推荐并行运行：

```text
BM25：精确实体、错误码、API、类名、版本号、专有名词
Dense：同义表达、自然语言问法、语义相似内容
Sparse：词汇扩展、缩写、领域术语
```

然后使用 RRF（Reciprocal Rank Fusion）合并不同检索通道：

```text
RRF Score(document)
= Σ 1 / (constant + rank(document, retriever_i))
```

建议的初始配置：

```text
BM25 Top 100
Dense Top 100
可选 Sparse Top 100
RRF 合并后保留 Top 50~100
```

BM25 在跨领域零样本检索中仍然是强基线，不能因为使用 Embedding 就完全放弃关键词检索。

参考：[BEIR 检索评测论文](https://arxiv.org/abs/2104.08663)

### 4.4 Reranker 精排

第一阶段检索目标是“尽可能召回”，Reranker 目标是“把真正相关证据排在前面”。推荐使用 Cross-Encoder 或 Listwise Reranker：

```text
召回 Top 50~100
  ↓
Reranker 对 query-document pair 重新打分
  ↓
保留 Top 8~15 进入上下文
```

Reranker 计算成本通常高于向量检索，因此不应对全量文档运行。

### 4.5 上下文组装

检索结果不能直接按分数拼接，需要进行：

- 相同文档片段去重；
- 父文档或相邻段落扩展；
- 版本和状态再次校验；
- 控制同一来源的最大片段数；
- 保留不同来源的证据多样性；
- 对冲突结论同时呈现版本和时间；
- 每个证据块保留稳定的 citation ID。

### 4.6 生成和答案校验

生成 Prompt 应明确：

1. 只能使用检索证据回答；
2. 没有充分证据时必须说明无法确认；
3. 每个事实性结论必须绑定引用；
4. 不得混用不同版本的文档；
5. 对冲突证据说明来源、时间和版本；
6. 不能将推测写成已确认事实。

对于高风险问题，可以增加 Claim Verifier，对回答中的每个声明重新检查是否被证据支持。

## 5. 模型候选与选型建议

### 5.1 Qwen3-Embedding 与 Qwen3-Reranker

Qwen3 Embedding 支持 0.6B、4B、8B 规模，支持 32K 上下文、100 多种语言、代码检索和 Matryoshka 降维。官方公布的多语言 MTEB Retrieval 分数如下：

| 模型 | MTEB Retrieval | C-MTEB Retrieval |
|---|---:|---:|
| Qwen3-Embedding-0.6B | 64.64 | 71.03 |
| Qwen3-Embedding-4B | 69.60 | 77.03 |
| Qwen3-Embedding-8B | 70.88 | 78.21 |

官方公布的 Qwen3 Reranker C-MTEB-R 分数为：

| 模型 | C-MTEB-R |
|---|---:|
| Qwen3-Reranker-0.6B | 71.31 |
| Qwen3-Reranker-4B | 75.94 |
| Qwen3-Reranker-8B | 77.45 |

这些是官方公开 benchmark 快照，不能直接替代企业语料上的评测。公开表格中的 Reranker 结果还依赖固定的 Top-100 候选集，因此不同首阶段检索器之间不能简单横向推导生产效果。

参考：[Qwen3-Embedding 官方仓库与评测](https://github.com/QwenLM/Qwen3-Embedding)

推荐：

```text
成本优先：Qwen3-Embedding-0.6B + Qwen3-Reranker-0.6B
质量优先：Qwen3-Embedding-4B + Qwen3-Reranker-4B
质量上限：Qwen3-Embedding-8B + Qwen3-Reranker-8B
```

从公开快照看，4B 到 8B 的提升约为 1 分多，因此 4B 往往更值得先做生产验证。

### 5.2 BGE-M3 与 bge-reranker-v2-m3

BGE-M3 的特点：

- Dense、Sparse、Multi-Vector 能力集中在同一模型；
- 支持中文和多语言；
- 适合与 BM25 组合；
- 对错误码、API、类名等精确实体场景容易建立强基线；
- 模型卡明确推荐 Hybrid Retrieval + Reranking。

推荐组合：

```text
BM25 + BGE-M3 Dense/Sparse + RRF + bge-reranker-v2-m3
```

参考：[BGE-M3 官方模型卡](https://huggingface.co/BAAI/bge-m3)

### 5.3 Voyage 托管模型

如果企业允许使用外部 API，可以使用以下组合做质量上限对照：

```text
voyage-4-large + rerank-2.5
```

Voyage 官方将 `voyage-4-large` 定位为高质量通用、多语言检索模型，同时提供 `voyage-4` 和 `voyage-4-lite` 作为质量、延迟和成本的不同折中；代码场景可以评估 `voyage-code-3`。

必须额外评估：

- 数据是否允许发送到外部服务；
- 数据驻留和隐私合规；
- API 稳定性、限流和超时；
- 单请求成本；
- p95 延迟。

参考：[Voyage Embeddings](https://docs.voyageai.com/docs/embeddings)、[Voyage Reranker](https://docs.voyageai.com/docs/reranker)

### 5.4 Jina 模型

Jina Embeddings v3 支持任务适配器、长文本和多语言，Jina Reranker v3 适合长文档候选排序，可以作为长文档场景的候选模型。

但相关模型卡标注 `CC BY-NC 4.0`，商业企业使用前必须完成许可审查，因此不建议直接作为默认生产模型。

参考：[Jina Embeddings v3](https://huggingface.co/jinaai/jina-embeddings-v3)、[Jina Reranker v3](https://huggingface.co/jinaai/jina-reranker-v3)

## 6. 查询理解和改写

建议将查询分为三类：

### 6.1 精确实体查询

包括错误码、API 路径、函数名、工单号、版本号、数据库表名等。

处理方式：

```text
原始查询保留
实体抽取
BM25/Keyword 强召回
Dense 作为补充
不允许仅依赖语义改写
```

### 6.2 语义问题

包括“为什么会出现这个问题”“有哪些替代方案”“如何配置”等自然语言问题。

处理方式：

```text
原始查询
查询改写
Dense 检索
BM25 兜底
```

### 6.3 多跳问题

包括同时需要多个文档、多个版本或多个业务系统证据的问题。

处理方式：

```text
查询分类
问题分解
子问题并行检索
证据合并
Complete Recall 校验
```

HyDE 可以用于复杂语义问题，但不能覆盖原始查询。对于 API、错误码和版本号，虚构的假设文档可能引入错误实体。

参考：[HyDE 论文](https://arxiv.org/abs/2212.10496)

## 7. Hard Negative 与领域微调

### 7.1 什么时候需要微调

只有在完成基础方案评测后，出现以下情况才建议微调：

- BM25、Dense、Hybrid 都无法召回领域术语；
- 大量相似文档之间排序不稳定；
- 当前版本和历史版本经常混淆；
- 通用模型对企业内部缩写、系统名、故障码理解不足。

### 7.2 正负样本构造

每条样本至少应包含：

```text
query
positive evidence span
hard negative evidence span
document version
service/domain
relevance grade
```

高价值 Hard Negative：

- 同一个错误码，但属于不同版本；
- 同一个 API 名称，但属于不同服务；
- 同一个业务术语，但实际结论相反；
- 内容高度相似但不能回答当前问题的文档；
- 已废弃文档和当前有效文档。

随机负样本只能验证模型是否能区分明显无关内容，不能有效提升企业领域排序能力。

### 7.3 微调方向

| 目标 | 方法 | 关注指标 |
|---|---|---|
| 提升候选召回 | Embedding 对比学习 | `Recall@100` |
| 提升排序 | Reranker Pairwise/Listwise 训练 | `nDCG@10`、`MRR@10` |
| 提升精确实体处理 | 关键词/稀疏检索增强 | Entity Recall |
| 减少版本混淆 | 时间、版本 Hard Negative | Version Hit、Stale Hit Rate |

训练集、验证集和测试集应按时间、服务或文档源切分，避免相同文档内容泄漏到不同数据集。

## 8. 可复现的实验矩阵

| 实验编号 | 方案 | 主要目的 | 重点指标 |
|---|---|---|---|
| B0 | 结构化分块 + BM25 | 建立精确关键词基线 | Entity Recall、Recall@100 |
| B1 | Dense Embedding + BM25 + RRF | 验证混合召回收益 | Recall@100、Precision@100 |
| B2 | B1 + 标题/章节/父文档上下文 | 验证分块和上下文收益 | Recall@100、Citation Recall |
| B3 | B2 + Reranker | 验证排序收益 | nDCG@10、MRR@10 |
| B4 | B3 + 查询分类/改写/分解 | 验证查询理解收益 | 分场景 Recall、Complete Recall |
| B5 | B4 + Hard Negative 微调 | 验证领域适配收益 | Recall、nDCG、最终答案准确率 |

每次实验必须固定：

- 同一批文档；
- 同一文档版本；
- 同一测试集；
- 同一权限范围；
- 同一候选数量；
- 同一 LLM 和 Prompt；
- 同一答案评测方式。

否则无法判断指标变化究竟来自模型、分块、Prompt 还是数据变化。

## 9. 评测数据集设计

建议至少准备 300 条真实问题，并按场景分层：

| 场景 | 必要标注 |
|---|---|
| 精确实体 | gold document、gold span、实体类型 |
| 语义问答 | gold evidence、标准答案、相关性等级 |
| 多跳问题 | 所有 required evidence、子问题关系 |
| 长文档/表格 | gold page、table/row/column 信息 |
| 版本冲突 | 当前版本、历史版本、允许命中的版本 |
| 无答案问题 | `no_answer=true`、可接受拒答范围 |
| 权限问题 | tenant、user role、可访问文档集合 |

建议将相关性标注为 0/1/2/3：

```text
0：无关
1：主题相关但不能回答
2：部分支持回答
3：直接支持回答
```

这样可以使用 nDCG 评估“部分相关”和“直接证据”的区别。

## 10. 验收门槛

以下是第一版建议起始门槛，不是行业统一标准，最终需要根据业务风险和基线校准：

```text
ACL Leakage = 0
过期版本误命中 = 0
Evidence Recall@100 ≥ 95%
Citation Precision ≥ 95%
多跳 Complete Recall@100 ≥ 90%
无答案问题误答率 ≤ 5%
```

线上还必须同时满足：

- p95 延迟符合业务 SLA；
- 单请求成本在预算内；
- Embedding、Reranker 和索引版本可追踪；
- 每次回答可追溯到 query、检索结果、模型版本和引用片段；
- 发生文档删除、权限变化或版本切换后，检索结果能够及时更新。

模型比较应使用配对 A/B 测试和 Bootstrap 95% 置信区间。只有满足以下条件，才认为方案确实有效：

1. 目标指标的提升置信区间下界大于 0；
2. 关键业务场景没有明显退化；
3. ACL Leakage 和过期版本误命中没有回归；
4. 延迟和成本没有超出可接受范围。

RAGAS、ARES 等方法可以帮助评估上下文相关性、答案忠实度和答案相关性，但应作为辅助评测，不能替代人工标注的 gold evidence 和业务答案集。

参考：[RAGAS 论文](https://arxiv.org/abs/2309.15217)、[ARES 论文](https://arxiv.org/abs/2311.09476)

## 11. 推荐落地顺序

### 阶段一：建立可比较基线

```text
结构化分块
→ BM25
→ Dense Embedding
→ RRF
→ 固定测试集评测
```

目标：得到 `Recall@100`、`nDCG@10`、`MRR@10` 和最终答案准确率基线。

### 阶段二：提升首阶段召回

```text
BM25 + Dense
→ Sparse/混合检索
→ 查询实体抽取
→ 父文档/邻居扩展
→ 版本和时间过滤
```

目标：优先提高 `Evidence Recall@100` 和 `Complete Recall@100`。

### 阶段三：提升排序准确率

```text
RRF Top 50~100
→ Cross-Encoder Reranker
→ Hard Negative
→ Top-K 调优
```

目标：提高 `nDCG@10`、`MRR@10` 和 `Citation Precision`。

### 阶段四：领域微调

```text
真实问题
→ gold evidence
→ Hard Negative
→ Embedding/Reranker 微调
→ 时间切分回归评测
```

目标：解决企业内部术语、版本混淆和高相似文档排序问题。

### 阶段五：生产化治理

- 记录每次检索的 query、模型版本、候选结果、RRF 分数、Reranker 分数和最终引用；
- 建立文档删除、权限变更和版本变更的增量更新机制；
- 持续采集低置信度、用户纠错和无答案样本；
- 按场景监控 Recall、Citation Precision、Faithfulness、延迟和成本；
- 任何模型升级必须重新跑固定评测集和关键场景回归。

## 12. 最终推荐

对于中文企业知识库，建议优先按以下顺序做实验：

```text
实验组 A：BM25 + BGE-M3 + RRF + bge-reranker-v2-m3
实验组 B：BM25 + Qwen3-Embedding-0.6B + Qwen3-Reranker-0.6B
实验组 C：BM25 + Qwen3-Embedding-4B + Qwen3-Reranker-4B
实验组 D：Voyage-4-large + rerank-2.5（合规允许时）
```

选择标准不是模型名称，而是同一批企业问题上的：

```text
Evidence Recall@100
nDCG@10
MRR@10
Citation Precision
最终答案准确率
多跳 Complete Recall
ACL Leakage
p95 延迟
单请求成本
```

最终应选择“在关键业务场景上指标最稳定、成本和延迟可接受”的组合，而不是公开 benchmark 分数最高的模型。

## 13. 参考资料

1. [Azure RAG 检索与评估指南](https://learn.microsoft.com/zh-cn/azure/architecture/ai-ml/guide/rag/rag-information-retrieval)
2. [Azure 安全多租户 RAG](https://learn.microsoft.com/zh-cn/azure/architecture/ai-ml/guide/secure-multitenant-rag)
3. [Qwen3-Embedding 官方仓库](https://github.com/QwenLM/Qwen3-Embedding)
4. [BGE-M3 官方模型卡](https://huggingface.co/BAAI/bge-m3)
5. [Voyage Embeddings 官方文档](https://docs.voyageai.com/docs/embeddings)
6. [Voyage Reranker 官方文档](https://docs.voyageai.com/docs/reranker)
7. [Jina Embeddings v3 官方模型卡](https://huggingface.co/jinaai/jina-embeddings-v3)
8. [BEIR: A Heterogeneous Benchmark for Zero-shot Evaluation of Information Retrieval Models](https://arxiv.org/abs/2104.08663)
9. [MTEB 官方评测说明](https://docs.mteb.org/overview/)
10. [HyDE: Precise Zero-Shot Dense Retrieval without Relevance Labels](https://arxiv.org/abs/2212.10496)
11. [RAGAS: Automated Evaluation of Retrieval Augmented Generation](https://arxiv.org/abs/2309.15217)
12. [ARES: An Automated Evaluation Framework for Retrieval-Augmented Generation Systems](https://arxiv.org/abs/2311.09476)
