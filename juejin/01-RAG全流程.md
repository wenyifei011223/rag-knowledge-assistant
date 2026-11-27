# 零依赖跑通一个 RAG 知识库：从文档分块到带引用的回答

> 掘金发文版 ｜ 建议封面：`assets/covers/01-rag-baseline-cover.png` ｜ 标签：RAG、大模型、检索增强生成、Python、BM25

把静态文档变成能回答问题的知识库，是 AI 应用开发最常见的落地形态。但"接个大模型能聊天"远远不够——真正能用的 RAG 要做到：回答能追溯到原文、域外问题能拒答、分块和召回参数有实验依据、整条链路能一键复现。

这篇用纯 Python 标准库（零第三方依赖）把这条链路完整跑一遍，代码和全部运行证据都在文末仓库。

## 一、整体架构：离线 + 在线两段

```
离线：文档 → 清洗 → 分块 → 向量化 → 索引入库
在线：问题 → 查询改写 → 混合检索+重排 → 域外判定 → 带引用生成 → 回答/拒答
```

拆成两段的好处：索引可以离线一次性构建，在线只做检索和生成，延迟可控；每块带来源 ID，回答才能标引用。

## 二、离线入库：四步建成索引

`ingest.py` 的核心只有四步：

```python
chunks = load_chunks(corpus_dir, chunk_size=500, overlap=100)  # 加载+清洗+分块
vocab, idf, vectors = build_tfidf(chunks)                       # 向量化（可用 bge 替换）
store = {"embedding": "local-tfidf-dense", "chunks": ...}       # 每块带 id 与来源
write(store)                                                    # 写入 store/vectors.json
```

每个块生成稳定 ID（`文件名#序号`）并带来源元数据——这是回答能追溯的前提。`chunk_size=500, overlap=100` 是起点，不是结论，后面的笔记会用对照实验来选。

## 三、在线问答：五步产出可核查回答

`rag_chain.py` 的链路：

```python
query, kind = rewrite_query(q, history)          # 多轮追问改写
results, mode = retrieve(query, "rerank", 4)     # 混合检索 + 重排
if not domain_guard(query, results):             # 域外判定
    answer = "未找到相关依据。"
else:
    context = build_context(results)             # 每段带 [来源: id]
    answer = deepseek_chat(...) or extractive_answer(...)  # 生成 / 抽取兜底
```

三个关键点：

1. **查询改写**：多轮对话里"它为什么这么做"这种追问，直接检索几乎召不回东西，必须把历史合并成独立问题。
2. **域外判定**：中文里"今天天气怎么样"和"怎么保证回答不编造"共享"怎么""怎么样"这类通用词，只用余弦相似度阈值会误判。改成中文二元组 + 过滤通用词后稳定。
3. **带引用生成**：上下文每段标 `[来源: id]`，提示词约束回答必须引用；没有大模型 Key 时用抽取式兜底，只引用原句，保证不编造。

> 踩坑：多轮追问被误拒。原始追问"它为什么这么做"没有领域词，域外判定必须作用在**改写后**的问题上，直接拿原句判会拒掉合法问题。

## 四、幻觉抑制：两道防线

- **第一道（检索侧）**：域外问题按词项覆盖判定拒答，宁可拒答也不硬编。
- **第二道（生成侧）**：引用约束 + 抽取式兜底，回答里的每个结论都能指回原文编号。

这两道防线是 RAG 区别于"套壳聊天"的核心，也是面试/评审最会追问的地方。

## 五、结果验证：不是拍脑袋，是跑出来的

真实运行证据（仓库 `evidence/` 目录）：

| 证据文件 | 内容 |
|---|---|
| `rag_answer_in_domain.json` | 域内问题带来源编号的回答 |
| `domain_rejection.json` | 域外问题返回"未找到相关依据" |
| `query_rewrite.json` | 多轮追问改写链路 |
| `retrieve_compare.txt` | 四种检索方式同一问题对比 |
| `experiment_results.md` | 14 组对照实验真实结果 |

一键复现：`bash scripts/run_all.sh`。

## 六、局限与升级路径

诚实说明：当前是 5 篇示例语料的**纯 Python 基线**，命中率偏高（基线 30/30）不代表真实业务效果——示例语料小、问题与语料高度对齐。代码预留了升级入口：装好 `sentence-transformers`（bge）、`CrossEncoder`、`Chroma` 并配置 `DEEPSEEK_API_KEY` 后会自动切换到正式模型，届时需要重跑实验、替换数字。

## 结语

RAG 的难点不在"接模型"，而在链路每一环都可追溯、可复现、可解释。这条零依赖基线把骨架搭好，升级模型时换的只是向量化和生成两头，中间的检索、拒答、引用约束逻辑都不用动。

完整代码、评测集与全部运行证据：[github.com/wenyifei011223/rag-knowledge-assistant](https://github.com/wenyifei011223/rag-knowledge-assistant)

---

**配图清单（发布前补充）**

| 位置 | 截图内容 | 采集命令 |
|---|---|---|
| 封面 | 用 `assets/covers/01-rag-baseline-cover.png` | 已生成 |
| 第二节后 | `python3 ingest.py` 输出（块数、维度） | `python3 ingest.py` |
| 第三节后 | 域内回答的 `[来源]` 标注输出 | `python3 rag_chain.py "混合检索权重0.4和0.6是怎么来的" --top-k 4` |
| 第四节后 | 域外拒答输出 | `python3 rag_chain.py "今天广州天气怎么样" --top-k 4` |
| 第五节后 | 14 组实验结果图 | `evidence/experiment_hit_rate.svg` 转 PNG |
