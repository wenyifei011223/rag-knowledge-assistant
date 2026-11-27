"""向量检索 + BM25 混合检索（RRF 融合）+ 轻量重排序。

CrossEncoder 可用时自动使用；否则使用词项覆盖重排降级，并明确打印提示。
"""
from __future__ import annotations

import argparse
import json
import math
import re
from collections import Counter
from pathlib import Path

BASE = Path(__file__).resolve().parent
STORE = BASE / "store" / "vectors.json"
TOKEN_RE = re.compile(r"[\u4e00-\u9fff]|[A-Za-z0-9]+")
K1, B = 1.5, 0.75


def tokenize(text: str) -> list[str]:
    return TOKEN_RE.findall(text.lower())


def load_store(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def query_vector(query: str, store: dict) -> list[float]:
    if store["embedding"] != "local-tfidf-dense":
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore
            model = SentenceTransformer("BAAI/bge-small-zh-v1.5")
            return list(map(float, model.encode([query], normalize_embeddings=True)[0]))
        except Exception:
            pass
    vocab = store["vocab"]
    index = {w: i for i, w in enumerate(vocab)}
    idf = store["idf"]
    tf = Counter(tokenize(query))
    vec = [0.0] * len(vocab)
    for w, c in tf.items():
        if w in index:
            vec[index[w]] = c * idf[w]
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def cosine(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):
        return 0.0
    return sum(x * y for x, y in zip(a, b))


def dense_search(query: str, store: dict, top_k: int) -> list[dict]:
    qv = query_vector(query, store)
    scored = []
    for c in store["chunks"]:
        scored.append({**c, "score": cosine(qv, c["vector"]), "dense_score": cosine(qv, c["vector"])})
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_k]


def bm25_search(query: str, store: dict, top_k: int) -> list[dict]:
    qtokens = tokenize(query)
    chunks = store["chunks"]
    docs_tokens = [tokenize(c["text"]) for c in chunks]
    avgdl = sum(len(d) for d in docs_tokens) / max(1, len(docs_tokens))
    df = Counter()
    for toks in docs_tokens:
        df.update(set(toks))
    n = len(chunks)
    scores = []
    for c, toks in zip(chunks, docs_tokens):
        tf = Counter(toks)
        score = 0.0
        for q in qtokens:
            if q not in tf:
                continue
            idf = math.log(1 + (n - df[q] + 0.5) / (df[q] + 0.5))
            score += idf * (tf[q] * (K1 + 1)) / (tf[q] + K1 * (1 - B + B * len(toks) / avgdl))
        scores.append({**c, "score": score})
    scores.sort(key=lambda x: x["score"], reverse=True)
    return scores[:top_k]


def rrf_fuse(dense: list[dict], bm25: list[dict], top_k: int) -> list[dict]:
    fused: dict[str, dict] = {}
    for rank, item in enumerate(dense, 1):
        fused.setdefault(item["id"], {**item, "score": 0.0})["score"] += 1 / (60 + rank)
    for rank, item in enumerate(bm25, 1):
        fused.setdefault(item["id"], {**item, "score": 0.0})["score"] += 1 / (60 + rank)
    out = sorted(fused.values(), key=lambda x: x["score"], reverse=True)
    return out[:top_k]


def rerank(query: str, results: list[dict], store: dict) -> tuple[list[dict], str]:
    try:
        from sentence_transformers import CrossEncoder  # type: ignore
        model = CrossEncoder("BAAI/bge-reranker-base")
        pairs = [[query, r["text"]] for r in results]
        scores = model.predict(pairs)
        for r, s in zip(results, scores):
            r["rerank_score"] = float(s)
        results.sort(key=lambda x: x["rerank_score"], reverse=True)
        return results, "cross-encoder"
    except Exception:
        qtokens = set(tokenize(query))
        for r in results:
            tokens = set(tokenize(r["text"]))
            coverage = len(qtokens & tokens) / max(1, len(qtokens))
            r["rerank_score"] = r.get("score", 0) * (1 + coverage)
        results.sort(key=lambda x: x["rerank_score"], reverse=True)
        return results, "lexical-coverage-fallback"


def retrieve(query: str, mode: str, top_k: int, store_path: Path = STORE) -> tuple[list[dict], str]:
    store = load_store(store_path)
    pool = max(20, top_k * 5)
    if mode == "vector":
        return dense_search(query, store, top_k), "dense"
    if mode == "bm25":
        return bm25_search(query, store, top_k), "bm25"
    dense = dense_search(query, store, pool)
    bm25 = bm25_search(query, store, pool)
    fused = rrf_fuse(dense, bm25, pool)
    if mode == "hybrid":
        return fused[:top_k], "hybrid-rrf"
    reranked, kind = rerank(query, fused[:pool], store)
    return reranked[:top_k], f"hybrid-rrf+{kind}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("query")
    ap.add_argument("--mode", choices=["vector", "bm25", "hybrid", "rerank"], default="hybrid")
    ap.add_argument("--top-k", type=int, default=4)
    ap.add_argument("--store", type=Path, default=STORE)
    args = ap.parse_args()
    results, kind = retrieve(args.query, args.mode, args.top_k, args.store)
    print(f"query: {args.query}")
    print(f"mode: {kind}")
    for i, r in enumerate(results, 1):
        print(f"\n[{i}] {r['id']}  score={r['score']:.4f}")
        print(r["text"][:260].replace("\n", " "))


if __name__ == "__main__":
    main()
