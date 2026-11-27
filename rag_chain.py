"""完整 RAG 链：查询改写 -> 混合检索 -> 重排 -> 提示词约束 -> 引用回答/域外拒答。

无 DeepSeek Key 时使用抽取式回答（只引用原文句子，不编造）；
配置 DEEPSEEK_API_KEY 后自动切换到 DeepSeek 生成式回答，提示词不变。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import urllib.request
from pathlib import Path

from retrieve import retrieve, tokenize

BASE = Path(__file__).resolve().parent
STORE = BASE / "store" / "vectors.json"
REJECT_THRESHOLD = 0.12
STOPWORDS = {"怎么", "什么", "为什么", "怎么样", "如何", "的", "了", "是", "在", "有", "和", "与", "吗", "呢", "它", "这", "那", "谁", "哪", "多少", "吗"}
GENERIC_BIGRAMS = {"怎么", "什么", "为什么", "怎么样", "如何", "今天", "我们", "可以", "这个", "那个", "一个", "没有", "就是", "不是"}


def domain_tokens(text: str) -> set[str]:
    """中文按二元组切词，避免单字'天/气'造成误命中。"""
    tokens = set(re.findall(r"[A-Za-z0-9]+", text.lower()))
    for run in re.findall(r"[\u4e00-\u9fff]{2,}", text):
        tokens.update(run[i:i + 2] for i in range(len(run) - 1))
    return {t for t in tokens if t not in GENERIC_BIGRAMS}

SYSTEM_PROMPT = """你是一个严格基于给定资料回答的企业知识库助手。
规则：
1. 只能使用【上下文】里的信息，禁止使用外部知识或猜测。
2. 每个结论后面必须标注来源编号，例如 [来源: 02_rag_pipeline.md#008]。
3. 如果上下文没有足够依据，必须固定回复：未找到相关依据。
4. 不要编造数字、日期、参数或文件名。"""


def deepseek_chat(messages: list[dict]) -> str | None:
    key = os.environ.get("DEEPSEEK_API_KEY")
    if not key:
        return None
    payload = json.dumps({
        "model": "deepseek-chat",
        "messages": messages,
        "temperature": 0.1,
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://api.deepseek.com/chat/completions",
        data=payload,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data["choices"][0]["message"]["content"]
    except Exception as exc:
        print(f"[rag_chain] DeepSeek调用失败，回退抽取式回答: {exc}")
        return None


def rewrite_query(query: str, history: list[str] | None = None) -> tuple[str, str]:
    if not history:
        return query, "无历史，直接使用原问题"
    llm = deepseek_chat([
        {"role": "system", "content": "把用户的追问改写成可独立检索的问题，只输出改写后的问题。"},
        {"role": "user", "content": "历史：" + " | ".join(history[-3:]) + "\n追问：" + query},
    ])
    if llm:
        return llm.strip(), "deepseek-rewrite"
    rewritten = " ".join(history[-2:] + [query])
    return rewritten, "rule-based-rewrite-fallback"


def build_context(results: list[dict]) -> str:
    parts = []
    for i, r in enumerate(results, 1):
        parts.append(f"[{i}] [来源: {r['id']}]\n{r['text']}")
    return "\n\n".join(parts)


def domain_guard(query: str, results: list[dict]) -> bool:
    """True 表示有领域依据。用词项覆盖而非单纯相似度，避免'怎么/什么'造成误命中。"""
    qtokens = domain_tokens(query)
    if not qtokens:
        return False
    corpus_tokens = set()
    for r in results:
        corpus_tokens.update(domain_tokens(r["text"]))
    overlap = qtokens & corpus_tokens
    return len(overlap) >= 2 or any(len(t) >= 4 for t in overlap)


def extractive_answer(query: str, results: list[dict]) -> str:
    qtokens = set(tokenize(query))
    sentences = []
    for r in results:
        for sent in re.split(r"(?<=[。！？；\n])", r["text"]):
            sent = sent.strip()
            if len(sent) < 12:
                continue
            toks = set(tokenize(sent))
            overlap = len(qtokens & toks) / max(1, len(qtokens))
            sentences.append((overlap, sent, r["id"]))
    sentences.sort(key=lambda x: x[0], reverse=True)
    picked = [s for s in sentences if s[0] > 0][:3]
    if not picked:
        picked = sentences[:1]
    lines = [f"{sent} [来源: {sid}]" for _, sent, sid in picked if sent]
    return "根据资料：" + " ".join(lines)


def answer(query: str, top_k: int = 4, history: list[str] | None = None,
           store_path: Path = STORE) -> dict:
    rewritten, rewrite_kind = rewrite_query(query, history)
    results, mode = retrieve(rewritten, "rerank", top_k, store_path)
    best_dense = max((r.get("dense_score", 0.0) for r in results), default=0.0)
    context = build_context(results)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"【上下文】\n{context}\n\n【问题】\n{query}"},
    ]
    if not domain_guard(rewritten, results) or best_dense < REJECT_THRESHOLD:
        final = "未找到相关依据。"
        gen_kind = "domain-reject"
    else:
        llm = deepseek_chat(messages)
        if llm:
            final, gen_kind = llm.strip(), "deepseek-generative"
        else:
            final, gen_kind = extractive_answer(query, results), "extractive-fallback"
    return {
        "question": query,
        "rewritten_query": rewritten,
        "rewrite_kind": rewrite_kind,
        "mode": mode,
        "max_dense_similarity": round(best_dense, 4),
        "generation": gen_kind,
        "answer": final,
        "sources": [r["id"] for r in results],
        "prompt": messages,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("query")
    ap.add_argument("--top-k", type=int, default=4)
    ap.add_argument("--history", default="[]", help="历史问题 JSON 数组字符串")
    args = ap.parse_args()
    history = json.loads(args.history)
    out = answer(args.query, args.top_k, history)
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
