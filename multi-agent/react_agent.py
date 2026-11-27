"""手写 ReAct 闭环（等价 create_react_agent 的底层原理）。

消息链：HumanMessage -> AIMessage(tool_calls) -> ToolMessage -> AIMessage(最终答案)
手写 StateGraph：agent 节点 / tools 节点 / 条件边 should_continue / START-END。
输出 Mermaid 状态图，作为"状态流转框架"的可视化证据。
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

import llm
from tools import invoke_tool


@dataclass
class Message:
    role: str
    content: str
    tool_calls: list | None = None
    name: str | None = None

    def typename(self) -> str:
        return {
            "human": "HumanMessage", "ai": "AIMessage",
            "tool": "ToolMessage", "system": "SystemMessage",
        }[self.role]


@dataclass
class MessagesState:
    messages: list[Message] = field(default_factory=list)


# ---- 节点函数 ----
def call_model(state: MessagesState) -> dict:
    """模型节点：根据最后一条用户消息决定是否产出 tool_calls。"""
    last = state.messages[-1]
    if last.role == "tool":
        # 观察之后：基于工具结果产出最终答案（不编造，直接引用证据）
        content = f"根据检索到的证据回答：\n{last.content}"
        return {"messages": [Message("ai", content)]}
    decision = llm.decide(last.content)
    if decision["tool"]:
        return {"messages": [Message("ai", "", tool_calls=[decision])]}
    return {"messages": [Message("ai", "这是问候或闲聊，无需检索知识库。")]}


def should_continue(state: MessagesState) -> str:
    """条件边：最后一条 AI 消息带 tool_calls 就去 tools，否则到 END。"""
    last = state.messages[-1]
    return "tools" if last.tool_calls else "__end__"


def tool_node(state: MessagesState) -> dict:
    """工具节点：执行 Model 请求的 tool_calls，结果作为 ToolMessage 追加。"""
    last = state.messages[-1]
    out = []
    for call in last.tool_calls or []:
        result = invoke_tool(call["tool"], call["args"])
        out.append(Message("tool", result, name=call["tool"]))
    return {"messages": out}


class StateGraph:
    """极简状态图：显式维护节点和边，按条件边路由，等价于 LangGraph 的编排。"""
    def __init__(self):
        self.nodes: dict[str, callable] = {}
        self.edges: dict[str, str] = {}
        self.conditional: dict[str, tuple[callable, dict]] = {}

    def add_node(self, name: str, fn: callable):
        self.nodes[name] = fn

    def add_edge(self, src: str, dst: str):
        self.edges[src] = dst

    def add_conditional_edges(self, src: str, router: callable, mapping: dict):
        self.conditional[src] = (router, mapping)

    def compile(self):
        return CompiledGraph(self)

    def draw_mermaid(self) -> str:
        lines = ["graph TD", "    START --> agent",
                 "    agent -->|有 tool_calls| tools",
                 "    agent -->|无 tool_calls| END",
                 "    tools --> agent"]
        return "\n".join(lines)


class CompiledGraph:
    def __init__(self, graph: StateGraph):
        self.g = graph

    def invoke(self, state: MessagesState, max_steps: int = 6) -> MessagesState:
        node = "agent"
        for _ in range(max_steps):
            if node == "__end__":
                break
            if node == "START":
                node = self.g.edges.get("START", "agent")
                continue
            # 执行当前节点
            result = self.g.nodes[node](state)
            state.messages.extend(result["messages"])
            # 路由下一步：条件边优先，其次普通边
            if node in self.g.conditional:
                router, mapping = self.g.conditional[node]
                node = mapping[router(state)]
            else:
                node = self.g.edges.get(node, "__end__")
        return state

    def get_graph(self) -> StateGraph:
        return self.g


def build_react_graph() -> CompiledGraph:
    """组装 ReAct 状态图：START->agent<->tools->END。"""
    builder = StateGraph()
    builder.add_node("agent", call_model)
    builder.add_node("tools", tool_node)
    builder.add_edge("START", "agent")
    builder.add_conditional_edges(
        "agent", should_continue, {"tools": "tools", "__end__": "__end__"})
    builder.add_edge("tools", "agent")
    return builder.compile()


def run(question: str) -> dict:
    """跑一次 ReAct 闭环，返回完整消息链 + Mermaid 图 + LLM 模式。"""
    graph = build_react_graph()
    state = MessagesState([Message("human", question)])
    state = graph.invoke(state)
    return {
        "question": question,
        "llm_mode": llm.mode(),
        "message_chain": [
            {"type": m.typename(), "role": m.role, "content": m.content[:500],
             "tool_calls": m.tool_calls, "name": m.name}
            for m in state.messages
        ],
        "final_answer": state.messages[-1].content,
        "mermaid": graph.get_graph().draw_mermaid(),
    }


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("question")
    args = ap.parse_args()
    print(json.dumps(run(args.question), ensure_ascii=False, indent=2))
