# 01 RAG 全流程：从文档到可问答的知识库

> 对应技能：AI 应用开发 ｜ 状态：已跑通（纯 Python 基线，可一键复现）

## 1. 背景与目标

把静态文档变成一个能回答问题的知识库，是 AI 应用开发最常见的落地形态。目标不是"接个大模型能聊天"，而是做到：回答能追溯到原文、域外问题能拒答、分块和召回参数有实验依据、整条链路能一键复现。本篇串起离线入库到在线问答的完整链路。

## 2. 环境与依赖

- Python 3.13，核心脚本**零第三方依赖**（标准库即可运行）
- 离线索引：`ingest.py`；在线问答：`rag_chain.py`
- 语料：`data/corpus/` 下 5 篇原创技术文档
- 可选升级：`sentence-transformers`（bge）、`CrossEncoder`、`DEEPSEEK_API_KEY`，检测到即自动切换

## 3. 核心实现

离线四步（`ingest.py`）：

```python
chunks = load_chunks(corpus_dir, chunk_size=500, overlap=100)  # 加载+清洗+分块
vocab, idf, vectors = build_tfidf(chunks)                       # 向量化
store = {"embedding": "local-tfidf-dense", "chunks": ...}       # 每块带 id 与来源
write(store)                                                    # 写入 store/vectors.json
```

在线五步（`rag_chain.py`）：查询改写 → 混合检索+重排 → 域外判断 → 组装带编号上下文 → 引用回答/拒答。

```python
query, kind = rewrite_query(q, history)          # 多轮追问改写
results, mode = retrieve(query, "rerank", 4)     # 检索+重排
if not domain_guard(query, results):             # 域外判定
    answer = "未找到相关依据。"
else:
    context = build_context(results)             # 每段带 [来源: id]
    answer = deepseek_chat(...) or extractive_answer(...)  # 生成/抽取
```

## 4. 关键参数与踩坑

- `chunk_size=500, overlap=100` 是起点不是结论，最终由对照实验选（见笔记 02）。
- **域外误判**：一开始只用余弦相似度阈值，"广州天气"会命中"怎么保证回答不编造"这类句子。改成中文二元组 + 过滤通用词后稳定。
- **多轮追问被误拒**：原始追问"它为什么这么做"没有领域词，域外判定必须作用在**改写后**的问题上。
- 没有大模型 Key 时用抽取式回答兜底，只引用原句，保证不编造。

## 5. 结果验证

真实运行证据（在 `evidence/`）：

| 证据文件 | 内容 |
|---|---|
| `rag_answer_in_domain.json` | 域内问题带来源编号的回答 |
| `domain_rejection.json` | 域外问题返回"未找到相关依据" |
| `query_rewrite.json` | 多轮追问改写链路 |
| `retrieve_compare.txt` | 四种检索方式同一问题对比 |
| `experiment_results.md` | 14 组对照实验真实结果 |

一键复现：`bash scripts/run_all.sh`

## 6. 面试怎么讲

"我把 RAG 拆成离线入库和在线问答两段。离线做清洗、分块、向量化，每块带来源 ID；在线做查询改写、混合检索、重排、域外判定，再用带引用约束的提示词生成回答，没有 Key 时用抽取式兜底。域外问题按词项覆盖判定拒答，避免硬编。参数不是拍脑袋，14 组对照实验选出来的。整个链路一条命令能复现，证据都在仓库里。"

> 局限要主动说：当前是 5 篇示例语料的纯 Python 基线，命中率偏高不代表真实业务效果。
