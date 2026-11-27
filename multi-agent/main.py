"""FastAPI 版本（装好 fastapi/uvicorn 后使用，接口契约与 server.py 一致）。

启动：uvicorn main:app --host 0.0.0.0 --port 8000
本环境未安装 FastAPI，实际测通用 server.py（标准库实现）完成，见 evidence/。
"""
from __future__ import annotations

# 以下代码在 pip install -r requirements.txt 后可直接运行
try:
    from fastapi import FastAPI
    from pydantic import BaseModel, Field
except ImportError as e:
    raise SystemExit(
        "FastAPI 未安装。请 pip install -r requirements.txt，"
        "或直接用 python3 server.py（标准库等价实现，已 curl 测通）。"
    ) from e

import react_agent
from agents import ConversationMemory

app = FastAPI(title="ReAct 多智能体问答服务")
mem = ConversationMemory()


class Query(BaseModel):
    question: str = Field(description="用户问题，不能为空")
    thread_id: str = "default"


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/ask")
def ask(q: Query):
    result = react_agent.run(q.question)
    mem.add(q.thread_id, "user", q.question)
    mem.add(q.thread_id, "assistant", result["final_answer"][:200])
    return {
        "answer": result["final_answer"],
        "thread_id": q.thread_id,
        "message_count": len(result["message_chain"]),
        "memory": mem.get_context(q.thread_id),
    }
