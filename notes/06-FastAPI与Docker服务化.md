# 06 FastAPI + Docker 把 RAG 封装成服务

> 对应技能：编程与工程 ｜ **状态：服务封装已跑通（标准库 HTTP 服务 curl 测通），Docker 未构建验证**
>
> 本环境无 FastAPI/Docker，用标准库 `http.server` 实现等价接口并 curl 测通——"服务封装"成立。`main.py` 是 FastAPI 版本（装依赖即用），`Dockerfile` 已写好但未构建。简历写"了解 Docker 容器化部署"，别写"完成容器化部署"。

## 1. 背景与目标

把问答链封成 HTTP 服务，才能被前端或其他系统调用。目标：提供 `/ask` 问答接口和 `/health` 健康检查接口，并证明服务真的跑起来了。

## 2. 环境与依赖

- 本环境：Python 标准库 `http.server`（无需安装，`curl_results.txt` 已测通）
- 生产：`fastapi`、`uvicorn[standard]`、`pydantic>=2`；Docker（可选加分项）
- `.env` 存大模型 Key，不进仓库

## 3. 核心实现

标准库服务（`multi-agent/server.py`，已测通）：

```python
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if path == "/health": self._send(200, {"status": "ok"})
        elif path == "/docs":  self._send(200, 接口说明)

    def do_POST(self):
        if path != "/ask": self._send(404, ...); return
        data = json.loads(self.rfile.read(length))
        question = data.get("question", "")
        if not question.strip():        # Pydantic 等价校验
            self._send(422, {"error": "question 必填且不能为空"}); return
        result = react_agent.run(question)
        self._send(200, {"answer": result["final_answer"],
                         "message_count": len(result["message_chain"]),
                         "memory": MEM.get_context(thread_id)})
```

FastAPI 版本（`multi-agent/main.py`，装依赖即用）接口契约完全一致：

```python
class Query(BaseModel):
    question: str = Field(description="用户问题，不能为空")
    thread_id: str = "default"

@app.get("/health")
def health(): return {"status": "ok"}

@app.post("/ask")
def ask(q: Query): ...
```

Dockerfile（分层利用构建缓存）：

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## 4. 关键参数与踩坑

- **先 COPY requirements 再安装，最后 COPY 代码**——代码改动不触发依赖重装，利用 Docker 构建缓存。
- `/health` 用于容器健康检查和负载均衡探活。
- `thread_id` 决定会话记忆归属；上下文超过阈值时把早期消息压成累积摘要，保留最近若干条——避免上下文无限膨胀。
- 空 `question` 返回 422 校验错误（不是 500），这是接口工程质量的基本体现。

## 5. 结果验证（真实运行，证据在 `multi-agent/evidence/`）

`curl_results.txt` 实测（服务跑在 8765 端口）：

```
GET  /health  -> {"status": "ok"}
GET  /docs    -> {"title":"ReAct 多智能体问答服务", "endpoints":[...]}
POST /ask     -> {"answer":"根据检索到的证据回答：... [来源: ...]",
                  "message_count": 4, "memory": {...}}
POST /ask {"question":""} -> {"error": "question 必填且不能为空"}
```

上下文压缩实测：6 轮对话后早期消息被压成累积摘要（`user:问题0 | assistant:回答0 | ...`），最近 4 条保留原文——证明摘要压缩不是空实现。

**待补（需有 FastAPI/Docker 的环境本地采集）**：Swagger 文档页截图、`docker ps` 容器运行截图。手册要求截图必须亲手运行，不伪造。

## 6. 面试怎么讲

"服务层封了三个接口：`/ask` 接收问题走 ReAct 链返回带来源答案和完整消息数，`/health` 做探活，`/docs` 给接口契约。请求用 Pydantic 模型做类型校验，空问题返回 422 而不是 500。thread_id 控制会话记忆，超阈值把早期对话压成累积摘要。本环境没有 Docker，所以我用标准库先跑通服务并 curl 验证了接口——容器化我只写了 Dockerfile 了解做法，没实测，简历上也如实写'了解 Docker 容器化部署'。"
