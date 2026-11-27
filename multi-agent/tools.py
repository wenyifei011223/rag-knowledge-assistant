"""工具定义 + 参数 Schema 校验 + 异常捕获与有限重试。

复用项目一的 RAG 链作为 search_kb 的后端。无 LangChain 依赖时，
用纯 Python 实现等价的 Schema 校验与 @tool 注册表，接口与手册保持一致。
装好 langchain-core / pydantic 后可无缝替换为官方实现（见 README）。
"""
from __future__ import annotations

import time
from typing import Callable

# 复用项目一 RAG 链（上级目录）
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rag_chain import answer as rag_answer  # noqa: E402


class ValidationError(ValueError):
    """参数校验失败，等价于 Pydantic ValidationError。"""


class SearchInput:
    """等价于 Pydantic BaseModel：query 为必填非空字符串。"""

    def __init__(self, query: str):
        if not isinstance(query, str):
            raise ValidationError("query 必须是字符串")
        if not query.strip():
            raise ValidationError("query 不能为空")
        self.query = query


def _search_kb(query: str) -> str:
    """真正执行检索：调用项目一 RAG 链，返回带来源的文字证据。"""
    result = rag_answer(query, top_k=3)
    if result["generation"] == "domain-reject":
        return "未找到相关依据。"
    sources = ", ".join(result["sources"])
    return f"{result['answer']}\n[来源: {sources}]"


# 工具注册表：name -> (schema 类, 执行函数, 描述)
TOOL_REGISTRY: dict[str, dict] = {}


def tool(name: str, schema: type, description: str):
    """类 @tool 装饰器：把函数注册为可被 Agent 调用的工具。"""
    def deco(fn: Callable[[str], str]):
        TOOL_REGISTRY[name] = {
            "name": name, "schema": schema, "fn": fn, "description": description,
        }
        return fn
    return deco


@tool("search_kb", SearchInput,
      "在企业知识库中检索相关内容，用于回答知识类问题。")
def search_kb(query: str) -> str:
    """带 Schema 校验的工具入口：参数错误在执行前被拦下。"""
    args = SearchInput(query)      # 校验；失败抛 ValidationError
    return _search_kb(args.query)


def get_tool(name: str) -> dict:
    if name not in TOOL_REGISTRY:
        raise KeyError(f"未注册工具: {name}")
    return TOOL_REGISTRY[name]


def invoke_tool(name: str, params: dict, *, retries: int = 2,
                delay: float = 0.01, log: list | None = None) -> str:
    """工具调用入口：Schema 校验 + 异常捕获 + 有限重试（指数退避）。

    重试只对执行期异常生效；Schema 校验错误不重试（传错参数重试无意义）。
    """
    t = get_tool(name)
    attempts = 0
    last_error: Exception | None = None
    while attempts <= retries:
        try:
            t["schema"](**params)              # 校验先行
            return t["fn"](**params)
        except ValidationError:
            raise                              # 参数错误，直接抛出，不重试
        except Exception as e:                 # 执行期异常才重试
            last_error = e
            attempts += 1
            if log is not None:
                log.append(f"attempt {attempts} failed: {type(e).__name__}: {e}")
            if attempts <= retries:
                time.sleep(delay * (2 ** (attempts - 1)))  # 指数退避
    return f"调用失败（已重试 {retries} 次）：{last_error}"


def tool_schemas() -> list[dict]:
    """导出给 LLM 的工具 Schema（等价于 LangChain 的 bind_tools）。"""
    return [
        {
            "name": t["name"],
            "description": t["description"],
            "parameters": {"query": {"type": "string", "required": True}},
        }
        for t in TOOL_REGISTRY.values()
    ]


if __name__ == "__main__":
    print("=== 工具 Schema ===")
    import json
    print(json.dumps(tool_schemas(), ensure_ascii=False, indent=2))
    print("\n=== 正常调用 ===")
    print(invoke_tool("search_kb", {"query": "混合检索为什么要用BM25"})[:300])
    print("\n=== 参数校验失败（应抛出，不重试）===")
    try:
        invoke_tool("search_kb", {"query": ""})
    except ValidationError as e:
        print(f"ValidationError: {e}")
    print("\n=== 执行期异常 + 有限重试 ===")
    log: list[str] = []
    def flaky():
        raise RuntimeError("模拟上游超时")
    for i in range(3):
        try:
            flaky()
        except Exception as e:
            log.append(f"attempt {i+1} failed: {e}")
    print("\n".join(log))
