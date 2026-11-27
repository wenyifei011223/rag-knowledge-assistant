# RAG 知识库问答：可复现的检索与评测基线

一个零依赖起跑、可一键复现的 RAG 项目。它把"混合检索、重排序、查询改写、引用约束、域外拒答、对照实验"这些常见说法，落成能打开、能运行、能核对的代码和证据。

> **关于数字的坦白**：当前环境没有安装 bge、Chroma、CrossEncoder，也没有配置大模型 Key，所以默认跑的是纯 Python 基线（TF-IDF 稠密向量 + BM25 + RRF + 词项覆盖重排）。语料是为讲解这些技术主题而写的 5 篇示例文档，评测集也围绕这些文档设计，因此基线命中率偏高是预料之中的，**不能外推到真实业务语料**。本项目的价值在于链路完整、实验可复现、局限写得清楚，而不是刷一个好看的分数。

## 特性

- **离线索引**：加载、清洗、重叠分块、向量化入库，分块参数可命令行覆盖。
- **四种检索**：纯向量、BM25、RRF 混合、混合加重排，同一问题可直接对比。
- **完整 RAG 链**：查询改写 → 混合检索与重排 → 域外判断 → 带来源编号的上下文 → 引用回答。
- **幻觉抑制两层保险**：提示词强制引用与拒答，检索侧用词项覆盖做域外判定。
- **14 组对照实验**：分块大小、重叠窗口、Top-k、检索方式、混合权重逐项扫描，输出真实结果与图表。
- **自动升级**：检测到 `sentence-transformers` 自动切 bge 向量，检测到 CrossEncoder 自动切精排，检测到 `DEEPSEEK_API_KEY` 自动切生成式回答。

## 目录结构

```
.
├── ingest.py                 # 加载、清洗、分块、入库
├── retrieve.py               # 向量 / BM25 / RRF 混合 / 重排
├── rag_chain.py              # 查询改写 + 引用回答 + 域外拒答
├── experiment.py             # 14 组对照实验
├── eval_set.json             # 30 题评测集（题目 + 正确来源 + 关键词）
├── data/corpus/              # 5 篇可公开的示例技术文档
├── scripts/
│   ├── run_all.sh            # 一键复现全部产物
│   └── make_chart.py         # 实验结果 SVG 图表
├── evidence/                 # 运行日志、结果表、图表与链路证据
├── multi-agent/              # 项目二：ReAct 多智能体问答系统（独立子项目）
│   ├── tools.py              # 工具定义 + Schema 校验 + 有限重试
│   ├── llm.py                # LLM 抽象层（DeepSeek / 本地规则）
│   ├── react_agent.py        # 手写 ReAct StateGraph + 消息链 + Mermaid
│   ├── agents.py             # 三类 Agent 编排 + 上下文压缩 + 记忆
│   ├── server.py / main.py   # HTTP 服务（标准库 / FastAPI）
│   ├── Dockerfile            # 容器化配置（未构建验证）
│   ├── run_all.sh            # 一键复现项目二全部证据
│   └── evidence/             # ReAct 消息链 / curl 结果 / Mermaid 图
├── notes/                    # 6 篇技能点笔记（手册第七部分）
├── blog/                     # 3 篇掘金发文草稿（早期版）
├── juejin/publish/           # 6 篇可直接复制粘贴的发文版 + 封面 + 速查表
├── assets/covers/            # 6 张掘金封面图
├── requirements.txt          # 可选升级依赖
└── LICENSE                   # MIT
```

## 笔记与博客

`notes/` 下 6 篇笔记按手册统一模板（背景/环境/实现/踩坑/验证/面试讲法）组织，一一对应简历技能点：

| 编号 | 笔记 | 状态 |
|---|---|---|
| 01 | RAG 全流程：从文档到可问答的知识库 | 已跑通 |
| 02 | 分块策略与重叠窗口：chunk_size 怎么选 | 已跑对照实验 |
| 03 | 混合检索实战：BM25 + 向量 + RRF | 已跑对照实验 |
| 04 | 重排序与查询改写 | 已实现（重排为降级方案） |
| 05 | 手写 ReAct Agent（附状态流转图） | 已跑通（完整 4 条消息链，见 `multi-agent/evidence/`） |
| 06 | FastAPI + Docker 服务化 | 服务已 curl 测通；Docker 未构建验证（诚实标注） |

`multi-agent/` 是项目二实现，8 步功能全部可运行：工具 Schema 校验+有限重试、ReAct 最小闭环、手写 StateGraph、三类 Agent 编排、上下文压缩+会话记忆、HTTP 服务封装。本环境无 langgraph/FastAPI/Docker，用纯标准库实现等价版本并保留升级入口；`bash multi-agent/run_all.sh` 一键复现全部证据。

`juejin/publish/` 下 6 篇为可直接复制粘贴的发文版，每篇有对应封面 `0X-cover.png`，标题/摘要/标签见 `发布速查表.md`。`blog/` 是最早的 3 篇草稿，以 `juejin/publish/` 为准。

## 快速开始

只需要 Python 3.9+，无需安装包：

```bash
git clone https://github.com/wenyifei011223/rag-knowledge-assistant.git
cd rag-knowledge-assistant

python3 ingest.py
python3 retrieve.py "对照实验中的命中率如何定义" --mode hybrid --top-k 4
python3 rag_chain.py "混合检索的权重应该如何确定" --top-k 4
python3 rag_chain.py "广州明天适合穿什么衣服" --top-k 4
python3 scripts/run_all.sh
```

一键脚本会重建索引、生成四种检索对比、RAG 链证据、14 组实验结果和 SVG 图表，全部写入 `evidence/`。

## 实测结果

运行时间：2026-11-27 11:25:31。评测集 30 题，命中率定义为 Top-k 中含正确来源文档的题数占比。基线 B 为 chunk_size=500、overlap=100、k=4、混合检索加重排序。

| 组 | 变量 | 命中 | 命中率 | 平均延迟(s) | 相对基线 |
|---|---|---:|---:|---:|---:|
| A | chunk_size=300 | 29/30 | 96.67% | 0.0098 | -3.33% |
| B | chunk_size=500（基线） | 30/30 | 100.00% | 0.0079 | — |
| C | chunk_size=1000 | 30/30 | 100.00% | 0.0062 | 持平 |
| D | overlap=0 | 29/30 | 96.67% | 0.0127 | -3.33% |
| E | overlap=100（基线） | 30/30 | 100.00% | 0.0143 | — |
| F | overlap=200 | 28/30 | 93.33% | 0.0091 | -6.67% |
| G | k=2 | 26/30 | 86.67% | 0.0079 | -13.33% |
| H | k=4（基线） | 30/30 | 100.00% | 0.0077 | — |
| I | k=8 | 30/30 | 100.00% | 0.0082 | 持平 |
| J | 纯向量检索 | 29/30 | 96.67% | 0.0024 | -3.33% |
| K | 混合检索 [0.4,0.6] | 30/30 | 100.00% | 0.0051 | 持平 |
| L | 混合 + 重排序（基线） | 30/30 | 100.00% | 0.0078 | — |
| M | weights [0.6,0.4] | 30/30 | 100.00% | 0.0051 | 持平 |
| N | weights [0.3,0.7] | 30/30 | 100.00% | 0.0052 | 持平 |

完整表格、运行日志与图表见 `evidence/experiment_results.md`、`evidence/experiment_console.log` 和 `evidence/experiment_hit_rate.svg`。

### 怎么读这组数字

- **k=2 明显掉到 86.67%**：召回数量不足会漏掉正确来源，这是最一致的信号。
- **overlap=200 反而降到 93.33%**：重叠过大让重复内容挤占 Top-k 名额。
- **多数组别持平在 100%**：语料只有 5 篇、评测题围绕这些文档设计，区分度不够；这恰恰说明需要更大更真实的语料才能选出有说服力的参数。
- **纯向量延迟最低但命中少一题**：混合检索的收益要在精确标识符类问题上才明显，当前评测集这类题覆盖不足。
- **延迟数据来自本机基线环境**，受机器状态影响，不要当成生产环境指标。

## 升级到语义模型配置

```bash
pip install -r requirements.txt
export DEEPSEEK_API_KEY="your-key-here"   # 只通过环境变量传入，不要提交
python3 ingest.py
python3 scripts/run_all.sh
```

升级后 embeddings 会切到 `bge-small-zh-v1.5`，重排切到 `bge-reranker-base`，回答切到大模型生成。**所有实验数字都会变，必须以重跑结果为准。** API Key 只能用环境变量传入，仓库的 `.gitignore` 已忽略 `.env`。

## 评测集的边界

评测集标注的是"哪个文档能回答这个问题"，与检索参数无关，因此可以公平比较不同配置。但它没有覆盖回答质量维度：引用是否真的支持结论、域外问题是否稳定拒答、端到端延迟是否可接受，这些都需要单独补测。当前版本只覆盖命中率和延迟。

## 许可

MIT，详见 [LICENSE](LICENSE)。语料为原创示例文档，可自由使用。
