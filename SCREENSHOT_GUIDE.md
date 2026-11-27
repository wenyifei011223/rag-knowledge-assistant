# 截图与配图采集清单

> 手册第七部分 + 第九部分要求的全部配图。分两类：**A 类封面图**（发文必需，可生成）和 **B 类证据截图**（必须真实运行采集，不能伪造）。
>
> 手册原话："所有结果数字、截图、时间必须由你亲手跑出来。抄来的答案撑不过第二句。"

## 当前进度

| 类别 | 需要 | 已有 | 状态 |
|---|---|---|---|
| 封面图 | 每篇掘金文章 1 张 | 3 张（`assets/covers/`） | ✅ 已生成 |
| 项目一证据图 | 6 张 | 0（有 1 张 SVG 图表可转为 PNG） | ⚠️ 部分可补 |
| 项目二证据图 | 6 张 | 0（项目二未实施） | ❌ 无法采集 |

---

## A. 封面图（掘金发文必需）

掘金发文流程要求"上传一张封面图"。3 篇预备发文各需要 1 张，建议 1200×630 或 16:9 横图。

| 文章 | 封面文件 | 状态 |
|---|---|---|
| 01 RAG 基线 | `assets/covers/01-rag-baseline-cover.png` | ✅ 已生成（文档→向量→检索→回答链路） |
| 02 十四组实验 | `assets/covers/02-experiments-cover.png` | ✅ 已生成（条形图/数据仪表盘风格） |
| 03 幻觉抑制 | `assets/covers/03-hallucination-cover.png` | ✅ 已生成（盾牌/防线意象） |

封面图是装饰性配图，不承载证据，已用生成工具制作并在 3 篇博客 front matter 中引用。右下角有工具水印，不影响发布。

---

## B. 项目一证据截图（RAG，已跑通，可采集）

源码和日志都已存在 `evidence/`，以下截图需要你**本地真实运行后截屏**：

### B1. 入库证据（手册 Step 3 必截图）
```bash
python3 ingest.py
```
截：`[ingest] embedding=local-tfidf-dense, chunks=26` 终端输出 + 生成的 `store/vectors.json` 文件存在。

### B2. 检索对比证据（手册 Step 6 必截图）
```bash
python3 retrieve.py "对照实验中的命中率如何定义" --mode vector --top-k 4
python3 retrieve.py "对照实验中的命中率如何定义" --mode hybrid --top-k 4
```
截：同一问题下两种模式的结果差异。手册说"这张对比图就是混合检索最好的证据"。

### B3. 带来源标注的回答 + 域外拒答（手册 Step 9 必截图）
```bash
python3 rag_chain.py "混合检索的权重应该如何确定" --top-k 4
python3 rag_chain.py "广州明天适合穿什么衣服" --top-k 4
```
截：① 带 `[来源: ...]` 编号的回答；② 域外问题返回"未找到相关依据"——后者是幻觉抑制的直接证据。

### B4. 14 组实验结果图表
`evidence/experiment_hit_rate.svg` 已有，用浏览器打开后截成 PNG，或直接把 SVG 转 PNG 上传。

### B5. 一键复现
```bash
bash scripts/run_all.sh
```
截：`All artifacts ready in ./evidence` 完成画面，证明整条链路可一条命令复现。

---

## C. 项目二证据截图（LangGraph / FastAPI，项目未实施，暂无法采集）

这部分对应笔记 05、06，**必须等项目二真正跑起来才能截**，现在编不出来：

| 编号 | 截图内容 | 采集命令/位置 |
|---|---|---|
| C1 | ReAct 完整消息链 | 运行后截 `HumanMessage → AIMessage(tool_calls) → ToolMessage → AIMessage` |
| C2 | Mermaid 状态流转图 | `graph.get_graph().draw_mermaid()` 输出到 mermaid.live 渲染后截图 |
| C3 | 多 Agent 编排输出 | planner/retriever/summarizer 节点流转 |
| C4 | 上下文记忆 | 同一 thread_id 两轮对话，第二轮理解"它" |
| C5 | curl 请求 + JSON 返回 | `curl -X POST http://127.0.0.1:8000/ask ...` |
| C6 | docker ps + Swagger 页 | `docker ps` 截图 + `http://127.0.0.1:8000/docs` |

> Docker 装不上时，至少截 C5（FastAPI + curl），简历写"了解 Docker 容器化部署"，别硬写"完成"。

---

## 发布优先级建议

- **现在就能发**（有真实数据支撑）：01 RAG 全流程、03 混合检索 — 配 B1-B4 + 封面图即可。
- **等项目二后发**：05 ReAct Agent — 必须补 C1/C2 才有技术含量，否则只是抄手册代码。
- **笔记 02/04/06**：放 GitHub 作技能点证据，不必单独发掘金。

## 关于"截图能不能由 AI 代做"

- 封面图：可以生成，属于装饰性配图。
- 证据截图：**不可以伪造**。手册第九部分的验收标准就是"打开能跑、截图是真的"。以上 B/C 类截图必须由你本地运行程序后截取，否则面试追问时无法自圆其说。
