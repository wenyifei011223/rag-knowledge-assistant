"""HTTP 服务：/health 健康检查 + /ask 问答 + /docs 接口说明。

用 Python 标准库 http.server 实现，无需 FastAPI 即可 curl 测通——
证明"服务封装"成立。装好 FastAPI 后见 main.py，接口契约完全一致。
"""
from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

import react_agent
from agents import ConversationMemory

MEM = ConversationMemory()


class Handler(BaseHTTPRequestHandler):
    def _send(self, status: int, payload: dict):
        body = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/health":
            self._send(200, {"status": "ok"})
        elif path == "/docs":
            self._send(200, {
                "title": "ReAct 多智能体问答服务",
                "endpoints": [
                    {"method": "GET", "path": "/health", "desc": "健康检查"},
                    {"method": "POST", "path": "/ask", "body": {"question": "str", "thread_id": "str"},
                     "desc": "ReAct 问答，返回完整消息链与答案"},
                ],
            })
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        path = urlparse(self.path).path
        if path != "/ask":
            self._send(404, {"error": "not found"})
            return
        length = int(self.headers.get("Content-Length", 0))
        try:
            data = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            self._send(400, {"error": "invalid json"})
            return
        question = data.get("question", "")
        if not isinstance(question, str) or not question.strip():
            self._send(422, {"error": "question 必填且不能为空"})
            return
        thread_id = data.get("thread_id", "default")
        result = react_agent.run(question)
        MEM.add(thread_id, "user", question)
        MEM.add(thread_id, "assistant", result["final_answer"][:200])
        self._send(200, {
            "answer": result["final_answer"],
            "thread_id": thread_id,
            "message_count": len(result["message_chain"]),
            "memory": MEM.get_context(thread_id),
        })

    def log_message(self, fmt, *args):
        print(f"[http] {self.address_string()} - {fmt % args}")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    args = ap.parse_args()
    print(f"serving on http://{args.host}:{args.port}")
    ThreadingHTTPServer((args.host, args.port), Handler).serve_forever()
