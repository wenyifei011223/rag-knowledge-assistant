# 06 FastAPI + Docker 把 RAG 封装成服务

> 对应技能：编程与工程 ｜ **状态：预备稿（项目二尚未实施，代码骨架来自手册，运行证据待补）**
>
> ⚠️ 本篇的代码是待实现的设计稿，不是已跑通的结果。项目二完成后需补：curl 请求/JSON 返回截图、docker ps 截图、Swagger 文档页截图。在补之前简历只能写"了解 Docker 容器化部署"，不能写"完成容器化部署"。

## 1. 背景与目标

把问答链封成 HTTP 服务，才能被前端或其他系统调用。目标：提供 `/ask` 问答接口和 `/health` 健康检查接口，用 Docker 容器化部署，并用截图证明服务真的跑起来了。

## 2. 环境与依赖

- Python 3.11+，`fastapi`、`uvicorn[standard]`、`pydantic>=2`
- Docker（可选加分项，装不上时至少跑通 FastAPI + curl）
- `.env` 存大模型 Key，不进仓库

## 3. 核心实现（设计稿）

`main.py`：

```python
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="企业知识库问答服务")

class Query(BaseModel):
    question: str

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/ask")
def ask(q: Query):
    answer = agent_with_memory.invoke(
        {"messages": [{"role": "user", "content": q.question}]},
        {"configurable": {"thread_id": "default"}},   # 会话记忆
    )["messages"][-1].content
    return {"answer": answer}
```

`Dockerfile`：

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

启动与测试：

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
curl -X POST http://127.0.0.1:8000/ask -H "Content-Type: application/json" -d '{"question":"你的测试问题"}'
docker build -t ai-kb .
docker run -p 8000:8000 --env-file .env ai-kb
```

## 4. 关键参数与踩坑

- Dockerfile 先 COPY requirements 再安装，最后 COPY 代码——利用构建缓存，代码改动不用重装依赖。
- `/health` 用于容器健康检查和负载均衡探活。
- `thread_id` 决定会话记忆归属，同一 id 多轮调用才能保持上下文。
- Key 只能通过 `--env-file .env` 或环境变量传入，`.gitignore` 已忽略 `.env`。

## 5. 结果验证（待补）

项目二完成后采集三张关键截图：

- [ ] curl 请求 + JSON 返回
- [ ] `docker ps` 显示容器在运行
- [ ] Swagger 文档页 `http://127.0.0.1:8000/docs`

## 6. 面试怎么讲（先背原理，证据待补后再讲实证）

"服务层用 FastAPI 封了两个接口：`/ask` 接收问题走问答链并返回带引用的答案，`/health` 做健康检查。请求响应用 Pydantic 模型做类型校验，thread_id 控制会话记忆。Docker 用多阶段思路把依赖安装和代码复制分层以利用缓存，docker run 映射端口并用 env-file 传 Key，避免密钥进镜像。当前项目二还在实施，等 curl、docker ps 和 Swagger 三张截图齐了再把简历里的'了解'改成'完成'。"

> 诚实底线：Docker 没跑通就写"了解容器化部署"；跑通了且有三张截图，才写"完成服务封装与容器化部署"。
