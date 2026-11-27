"""文档加载、清洗、分块与向量入库。

默认使用本地 TF-IDF 稠密向量基线（零依赖、可复现）；
若环境已安装 sentence-transformers，则自动切换为 bge 中文 embedding。
"""
from __future__ import annotations

import argparse
import json
import math
import re
from collections import Counter
from pathlib import Path

BASE = Path(__file__).resolve().parent
CORPUS = BASE / "data" / "corpus"
STORE = BASE / "store" / "vectors.json"
MAX_VOCAB = 3000

TOKEN_RE = re.compile(r"[\u4e00-\u9fff]|[A-Za-z0-9]+")


def tokenize(text: str) -> list[str]:
    return TOKEN_RE.findall(text.lower())


def clean(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def chunk_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    step = max(1, chunk_size - overlap)
    chunks = []
    for i in range(0, len(text), step):
        part = text[i:i + chunk_size].strip()
        if len(part) >= max(20, chunk_size // 4):
            chunks.append(part)
        if i + chunk_size >= len(text):
            break
    return chunks


def load_chunks(corpus_dir: Path, chunk_size: int, overlap: int) -> list[dict]:
    docs = sorted(corpus_dir.glob("*.md"))
    if not docs:
        raise SystemExit(f"语料目录为空: {corpus_dir}")
    chunks: list[dict] = []
    for doc in docs:
        text = clean(doc.read_text(encoding="utf-8"))
        for idx, part in enumerate(chunk_text(text, chunk_size, overlap)):
            chunks.append({
                "id": f"{doc.stem}#{idx:03d}",
                "source": doc.name,
                "text": part,
            })
    return chunks


def build_tfidf(chunks: list[dict]) -> tuple[list[str], dict[str, float], list[list[float]]]:
    docs_tokens = [tokenize(c["text"]) for c in chunks]
    df = Counter()
    for toks in docs_tokens:
        df.update(set(toks))
    vocab = [w for w, _ in df.most_common(MAX_VOCAB)]
    index = {w: i for i, w in enumerate(vocab)}
    n = len(chunks)
    idf = {w: math.log((1 + n) / (1 + df[w])) + 1 for w in vocab}
    vectors = []
    for toks in docs_tokens:
        tf = Counter(toks)
        vec = [0.0] * len(vocab)
        for w, count in tf.items():
            if w in index:
                vec[index[w]] = count * idf[w]
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        vectors.append([v / norm for v in vec])
    return vocab, idf, vectors


def try_bge(texts: list[str]) -> list[list[float]] | None:
    try:
        from sentence_transformers import SentenceTransformer  # type: ignore
    except Exception:
        return None
    model = SentenceTransformer("BAAI/bge-small-zh-v1.5")
    vecs = model.encode(texts, normalize_embeddings=True)
    return [list(map(float, v)) for v in vecs]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--chunk-size", type=int, default=500)
    ap.add_argument("--overlap", type=int, default=100)
    ap.add_argument("--corpus-dir", type=Path, default=CORPUS)
    ap.add_argument("--store", type=Path, default=STORE)
    args = ap.parse_args()

    chunks = load_chunks(args.corpus_dir, args.chunk_size, args.overlap)
    bge_vecs = try_bge([c["text"] for c in chunks])
    if bge_vecs:
        store = {
            "embedding": "bge-small-zh-v1.5",
            "params": {"chunk_size": args.chunk_size, "overlap": args.overlap},
            "chunks": [{**c, "vector": v} for c, v in zip(chunks, bge_vecs)],
        }
        print(f"[ingest] embedding=bge-small-zh-v1.5, chunks={len(chunks)}")
    else:
        vocab, idf, vectors = build_tfidf(chunks)
        store = {
            "embedding": "local-tfidf-dense",
            "params": {"chunk_size": args.chunk_size, "overlap": args.overlap},
            "vocab": vocab,
            "idf": idf,
            "chunks": [{**c, "vector": v} for c, v in zip(chunks, vectors)],
        }
        print(f"[ingest] embedding=local-tfidf-dense(vocab={len(vocab)}), chunks={len(chunks)}")
    args.store.parent.mkdir(parents=True, exist_ok=True)
    args.store.write_text(json.dumps(store, ensure_ascii=False), encoding="utf-8")
    try:
        shown = args.store.relative_to(BASE)
    except ValueError:
        shown = args.store
    print(f"[ingest] store -> {shown}")


if __name__ == "__main__":
    main()
