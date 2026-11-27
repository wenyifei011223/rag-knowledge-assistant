#!/usr/bin/env bash
# 一键复现：入库 -> 检索对比 -> RAG 链 -> 14 组实验 -> 图表
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p evidence

echo "=== 1/5 ingest ==="
python3 ingest.py | tee evidence/ingest.log

echo "=== 2/5 retrieve compare ==="
{
  echo "# 四种检索方式对比（同一问题）"
  echo
  for m in vector bm25 hybrid rerank; do
    echo "## mode=$m"
    python3 retrieve.py "对照实验中的命中率如何定义" --mode "$m" --top-k 4
    echo
  done
} > evidence/retrieve_compare.txt

echo "=== 3/5 rag chain evidence ==="
python3 rag_chain.py "混合检索的权重应该如何确定" --top-k 4 > evidence/rag_answer_in_domain.json
python3 rag_chain.py "广州明天适合穿什么衣服" --top-k 4 > evidence/domain_rejection.json
python3 rag_chain.py "它为什么这么做" --history '["为什么要使用混合检索"]' --top-k 4 > evidence/query_rewrite.json

echo "=== 4/5 experiment ==="
python3 experiment.py 2>&1 | tee evidence/experiment_console.log

echo "=== 5/5 chart ==="
python3 scripts/make_chart.py

echo "All artifacts ready in ./evidence"
