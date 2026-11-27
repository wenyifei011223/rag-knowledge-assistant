"""14 组对照实验：逐组跑命中率与延迟，数字全部来自真实运行。"""
from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path

from ingest import CORPUS, build_tfidf, load_chunks, try_bge
from retrieve import bm25_search, dense_search, rerank, rrf_fuse

BASE = Path(__file__).resolve().parent
EVAL = BASE / "eval_set.json"
EVIDENCE = BASE / "evidence"

# A-N 共 14 组。A-I 默认 hybrid+rerank；J-N 改变检索方式。
GROUPS = [
    ("A", "chunk_size=300", dict(chunk_size=300, overlap=100, top_k=4, mode="rerank")),
    ("B", "chunk_size=500（基线）", dict(chunk_size=500, overlap=100, top_k=4, mode="rerank")),
    ("C", "chunk_size=1000", dict(chunk_size=1000, overlap=100, top_k=4, mode="rerank")),
    ("D", "overlap=0", dict(chunk_size=500, overlap=0, top_k=4, mode="rerank")),
    ("E", "overlap=100（基线）", dict(chunk_size=500, overlap=100, top_k=4, mode="rerank")),
    ("F", "overlap=200", dict(chunk_size=500, overlap=200, top_k=4, mode="rerank")),
    ("G", "k=2", dict(chunk_size=500, overlap=100, top_k=2, mode="rerank")),
    ("H", "k=4（基线）", dict(chunk_size=500, overlap=100, top_k=4, mode="rerank")),
    ("I", "k=8", dict(chunk_size=500, overlap=100, top_k=8, mode="rerank")),
    ("J", "纯向量检索", dict(chunk_size=500, overlap=100, top_k=4, mode="vector")),
    ("K", "混合检索 [0.4,0.6]", dict(chunk_size=500, overlap=100, top_k=4, mode="weighted", w_bm25=0.4, w_dense=0.6)),
    ("L", "混合 + 重排序（基线）", dict(chunk_size=500, overlap=100, top_k=4, mode="rerank")),
    ("M", "weights [0.6,0.4]", dict(chunk_size=500, overlap=100, top_k=4, mode="weighted", w_bm25=0.6, w_dense=0.4)),
    ("N", "weights [0.3,0.7]", dict(chunk_size=500, overlap=100, top_k=4, mode="weighted", w_bm25=0.3, w_dense=0.7)),
]


def build_store(chunk_size: int, overlap: int, cache: dict) -> dict:
    key = (chunk_size, overlap)
    if key in cache:
        return cache[key]
    chunks = load_chunks(CORPUS, chunk_size, overlap)
    bge = try_bge([c["text"] for c in chunks])
    if bge:
        store = {"embedding": "bge-small-zh-v1.5", "chunks": [{**c, "vector": v} for c, v in zip(chunks, bge)]}
    else:
        vocab, idf, vectors = build_tfidf(chunks)
        store = {
            "embedding": "local-tfidf-dense",
            "vocab": vocab, "idf": idf,
            "chunks": [{**c, "vector": v} for c, v in zip(chunks, vectors)],
        }
    cache[key] = store
    print(f"[experiment] build store chunk={chunk_size} overlap={overlap} chunks={len(chunks)} embedding={store['embedding']}")
    return store


def weighted_search(query: str, store: dict, top_k: int, w_bm25: float, w_dense: float) -> list[dict]:
    pool = max(20, top_k * 5)
    dense = dense_search(query, store, pool)
    bm25 = bm25_search(query, store, pool)
    max_d = max((r["score"] for r in dense), default=1.0) or 1.0
    max_b = max((r["score"] for r in bm25), default=1.0) or 1.0
    fused: dict[str, dict] = {}
    for r in dense:
        fused[r["id"]] = {**r, "score": w_dense * (r["score"] / max_d)}
    for r in bm25:
        if r["id"] in fused:
            fused[r["id"]]["score"] += w_bm25 * (r["score"] / max_b)
        else:
            fused[r["id"]] = {**r, "score": w_bm25 * (r["score"] / max_b)}
    return sorted(fused.values(), key=lambda x: x["score"], reverse=True)[:top_k]


def run_group(group: tuple, eval_set: list[dict], cache: dict) -> dict:
    letter, variable, p = group
    store = build_store(p["chunk_size"], p["overlap"], cache)
    hit = 0
    total = 0.0
    for item in eval_set:
        t0 = time.perf_counter()
        if p["mode"] == "vector":
            results = dense_search(item["question"], store, p["top_k"])
        elif p["mode"] == "weighted":
            results = weighted_search(item["question"], store, p["top_k"], p["w_bm25"], p["w_dense"])
        else:
            pool = max(20, p["top_k"] * 5)
            fused = rrf_fuse(dense_search(item["question"], store, pool),
                             bm25_search(item["question"], store, pool), pool)
            results, _ = rerank(item["question"], fused, store)
            results = results[:p["top_k"]]
        total += time.perf_counter() - t0
        sources = [r["source"] for r in results]
        if item["source"] in sources:
            hit += 1
    n = len(eval_set)
    return {
        "group": letter, "variable": variable, "chunk_size": p["chunk_size"],
        "overlap": p["overlap"], "top_k": p["top_k"], "mode": p["mode"],
        "hit": hit, "total": n, "hit_rate": round(hit / n, 4),
        "avg_latency": round(total / n, 6),
    }


def main() -> None:
    EVIDENCE.mkdir(exist_ok=True)
    eval_set = json.loads(EVAL.read_text(encoding="utf-8"))
    cache: dict = {}
    rows = []
    for g in GROUPS:
        row = run_group(g, eval_set, cache)
        rows.append(row)
        print(f"[experiment] {row['group']} {row['variable']}: hit={row['hit']}/{row['total']} rate={row['hit_rate']:.2%} latency={row['avg_latency']:.4f}s")

    baseline = next(r for r in rows if r["group"] == "B")
    for r in rows:
        delta = r["hit_rate"] - baseline["hit_rate"]
        r["vs_baseline"] = round(delta, 4)
        r["conclusion"] = (
            "与基线持平" if abs(delta) < 1e-9 else
            f"命中率{'高于' if delta > 0 else '低于'}基线 {abs(delta):.2%}"
        )

    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    payload = {
        "run_at": stamp,
        "eval_size": len(eval_set),
        "hit_definition": "Top-k 结果中包含该评测题标注的正确来源文档即命中；命中率=命中数/30",
        "baseline": "B: chunk_size=500, overlap=100, k=4, hybrid+rerank",
        "embedding": next(iter(cache.values()))["embedding"],
        "rerank": "CrossEncoder 可用则用；本环境未安装，使用 lexical-coverage-fallback",
        "rows": rows,
    }
    (EVIDENCE / "experiment_results.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# 14 组对照实验结果（真实运行）",
        "",
        f"运行时间：{stamp}",
        f"评测集：{len(eval_set)} 题；命中率定义：{payload['hit_definition']}",
        f"基线：{payload['baseline']}",
        f"Embedding：{payload['embedding']}；重排序：{payload['rerank']}",
        "",
        "| 组 | 变量 | chunk | overlap | k | 方式 | 命中 | 命中率 | 平均延迟(s) | 相对基线 | 结论 |",
        "|---|---|---:|---:|---:|---|---:|---:|---:|---:|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r['group']} | {r['variable']} | {r['chunk_size']} | {r['overlap']} | {r['top_k']} | {r['mode']} "
            f"| {r['hit']}/{r['total']} | {r['hit_rate']:.2%} | {r['avg_latency']:.4f} "
            f"| {r['vs_baseline']:+.2%} | {r['conclusion']} |"
        )
    lines += ["", "说明：本环境未安装 CrossEncoder / bge / Chroma / DeepSeek，故数字来自本地 TF-IDF 稠密向量 + BM25 + RRF + 词项覆盖重排基线，不是最终模型配置。装好依赖后需重跑并以新结果为准。"]
    (EVIDENCE / "experiment_results.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[experiment] results -> evidence/experiment_results.md")


if __name__ == "__main__":
    main()
