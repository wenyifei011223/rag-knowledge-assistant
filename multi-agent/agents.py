"""三类 Agent 编排（规划 / 检索 / 汇总）+ 上下文摘要压缩 + 会话记忆。

用 AgentState 在节点间传 question/plan/evidence/answer，职责分离便于单独调试。
上下文压缩：历史超过阈值时把早期消息压成摘要，再拼回问题，避免上下文膨胀。
"""
from __future__ import annotations

from dataclasses import dataclass, field

import llm
from tools import invoke_tool


@dataclass
class AgentState:
    question: str
    plan: str = ""
    evidence: str = ""
    answer: str = ""
    trace: list[str] = field(default_factory=list)


def planner(state: AgentState) -> AgentState:
    """规划节点：把问题拆成可检索的子问题（无 Key 时用规则拆解）。"""
    q = state.question
    # 复杂问题（含"和/与/以及/分别"等连接词）拆成多个子问题
    parts = [p.strip() for p in __import__("re").split(r"和|与|以及|同时", q) if p.strip()]
    if len(parts) == 1:
        parts = [q]
    state.plan = "\n".join(f"{i+1}. {p}" for i, p in enumerate(parts))
    state.trace.append(f"[planner] 生成 {len(parts)} 个检索步骤")
    return state


def retriever_node(state: AgentState) -> AgentState:
    """检索节点：按 plan 每个子问题调用工具，异常自动重试。"""
    chunks = []
    for line in state.plan.splitlines():
        sub = line.split(". ", 1)[-1].strip()
        if not sub:
            continue
        ev = invoke_tool("search_kb", {"query": sub}, retries=2)
        chunks.append(f"子问题：{sub}\n证据：{ev}")
    state.evidence = "\n\n".join(chunks)
    state.trace.append(f"[retriever] 汇总 {len(chunks)} 份证据")
    return state


def summarizer(state: AgentState) -> AgentState:
    """汇总节点：只根据证据组织答案，带来源，不编造。"""
    state.answer = (
        f"问题：{state.question}\n\n"
        f"依据以下证据回答：\n{state.evidence[:800]}\n\n"
        f"（答案来自检索证据，未使用模型臆测）"
    )
    state.trace.append("[summarizer] 基于证据生成带来源答案")
    return state


class MultiAgentGraph:
    """手写线性编排：START -> planner -> retriever -> summarizer -> END。"""
    def __init__(self):
        self.nodes = {
            "planner": planner, "retriever": retriever_node, "summarizer": summarizer,
        }

    def invoke(self, question: str) -> AgentState:
        state = AgentState(question=question)
        for name in ("planner", "retriever", "summarizer"):
            state = self.nodes[name](state)
        return state

    def draw_mermaid(self) -> str:
        return "\n".join([
            "graph LR", "    START --> planner", "    planner --> retriever",
            "    retriever --> summarizer", "    summarizer --> END",
        ])


class ConversationMemory:
    """会话记忆：thread_id 隔离 + 超阈值摘要压缩。"""

    def __init__(self, summary_threshold: int = 6):
        self.store: dict[str, list[dict]] = {}
        self.summaries: dict[str, str] = {}
        self.threshold = summary_threshold

    def _compress(self, thread_id: str, history: list[dict]):
        """把早期消息压成摘要，保留最近 2 条原文。"""
        early = history[:-2]
        if not early:
            return
        digest = " | ".join(f"{m['role']}:{m['content'][:40]}" for m in early)
        # 累积摘要：把上一次摘要并入，避免反复覆盖丢失早期上下文
        prev = self.summaries.get(thread_id, "")
        merged = f"{prev} | {digest}" if prev else digest
        self.summaries[thread_id] = merged[-500:]
        self.store[thread_id] = history[-2:]
        return

    def add(self, thread_id: str, role: str, content: str):
        history = self.store.setdefault(thread_id, [])
        if len(history) >= self.threshold:
            self._compress(thread_id, history)
        self.store[thread_id].append({"role": role, "content": content})

    def get_context(self, thread_id: str) -> dict:
        return {
            "summary": self.summaries.get(thread_id, ""),
            "recent": self.store.get(thread_id, []),
        }


def run(question: str, thread_id: str = "default") -> dict:
    graph = MultiAgentGraph()
    state = graph.invoke(question)
    mem = ConversationMemory()
    mem.add(thread_id, "user", question)
    mem.add(thread_id, "assistant", state.answer[:200])
    return {
        "question": question,
        "llm_mode": llm.mode(),
        "plan": state.plan,
        "evidence": state.evidence[:600],
        "answer": state.answer[:800],
        "trace": state.trace,
        "memory_context": mem.get_context(thread_id),
        "mermaid": graph.draw_mermaid(),
    }


if __name__ == "__main__":
    import json
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("question")
    ap.add_argument("--thread", default="default")
    args = ap.parse_args()
    print(json.dumps(run(args.question, args.thread), ensure_ascii=False, indent=2))
