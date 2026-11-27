"""LLM 抽象层：有 Key 走 DeepSeek，无 Key 用确定性本地策略。

真实项目里替换为 ChatOpenAI / ChatDeepSeek 即可，Agent 代码不用改。
本地策略只做"是否调用工具"的决策，不编造知识性答案——答案一律来自工具返回的证据。
"""
from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path

from tools import tool_schemas

DEEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions"


def deepseek_available() -> bool:
    return bool(os.environ.get("DEEPSEEK_API_KEY"))


def _deepseek_decide(question: str) -> dict:
    """真实 LLM：让模型输出工具调用决策（Function Calling 风格）。"""
    schemas = tool_schemas()
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content":
             "你是检索决策器。判断是否需要用 search_kb 工具回答用户问题。"
             "需要时只输出 JSON: {\"tool\":\"search_kb\",\"args\":{\"query\":\"检索词\"}}；"
             "不需要时输出 {\"tool\":null}。不要输出其他文字。"},
            {"role": "user", "content": question},
        ],
        "tools": [{"type": "function", "function": s} for s in schemas],
        "tool_choice": "auto",
        "temperature": 0,
    }
    req = urllib.request.Request(
        DEEPSEEK_URL, data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {os.environ['DEEPSEEK_API_KEY']}",
                 "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode())
    msg = data["choices"][0]["message"]
    calls = msg.get("tool_calls") or []
    if calls:
        return {"tool": "search_kb",
                "args": json.loads(calls[0]["function"]["arguments"])}
    return {"tool": None}


def _local_decide(question: str) -> dict:
    """无 Key 时的确定性决策：知识类问题走检索，问候/闲聊不调用工具。"""
    q = question.strip()
    if not q:
        return {"tool": None}
    # 纯问候/闲聊不查知识库
    if q in {"你好", "hi", "hello", "在吗"} or q.endswith("天气怎么样"):
        return {"tool": None}
    return {"tool": "search_kb", "args": {"query": q}}


def decide(question: str) -> dict:
    """决策是否调用工具；返回 {"tool": name|None, "args": dict}。"""
    if deepseek_available():
        try:
            return _deepseek_decide(question)
        except Exception:
            pass  # 在线决策失败，降级到本地策略，保证链路可用
    return _local_decide(question)


def mode() -> str:
    return "deepseek-function-calling" if deepseek_available() else "local-rule-fallback"
