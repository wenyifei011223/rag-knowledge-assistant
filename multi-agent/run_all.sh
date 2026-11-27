#!/usr/bin/env bash
# 项目二一键复现：工具校验 -> ReAct闭环 -> 三类Agent -> HTTP服务(curl) -> 留证
set -e
cd "$(dirname "$0")"
mkdir -p evidence

echo "[1/6] 工具 Schema 与校验/重试"
python3 tools.py > evidence/tools_check.txt 2>&1

echo "[2/6] ReAct 完整消息链（知识类：走工具）"
python3 react_agent.py "混合检索为什么要用BM25" > evidence/react_message_chain.json

echo "[3/6] ReAct 闲聊路径（不调用工具）"
python3 react_agent.py "你好" > evidence/react_no_tool.json

echo "[4/6] 三类 Agent 编排 + 上下文压缩"
python3 agents.py "混合检索和分块策略分别怎么做" --thread user-001 > evidence/multi_agent_output.json

echo "[5/6] 状态流转图（Mermaid）"
python3 -c "
from react_agent import build_react_graph
from agents import MultiAgentGraph
open('evidence/state_graph_mermaid.md','w',encoding='utf-8').write(
    '# ReAct 状态流转图\n\`\`\`mermaid\n'+build_react_graph().get_graph().draw_mermaid()+'\n\`\`\`\n\n'
    '# 三类 Agent 编排图\n\`\`\`mermaid\n'+MultiAgentGraph().draw_mermaid()+'\n\`\`\`\n')
"

echo "[6/6] HTTP 服务 + curl 测通"
python3 server.py --port 8765 > evidence/server.log 2>&1 &
PID=$!
sleep 2
{
  echo '=== GET /health ==='
  curl -s http://127.0.0.1:8765/health
  echo
  echo '=== GET /docs ==='
  curl -s http://127.0.0.1:8765/docs
  echo
  echo '=== POST /ask (knowledge) ==='
  curl -s -X POST http://127.0.0.1:8765/ask -H 'Content-Type: application/json' \
    -d '{"question":"混合检索为什么要用BM25","thread_id":"user-001"}'
  echo
  echo '=== POST /ask (invalid: empty question) ==='
  curl -s -X POST http://127.0.0.1:8765/ask -H 'Content-Type: application/json' \
    -d '{"question":""}'
  echo
} > evidence/curl_results.txt 2>&1
kill $PID 2>/dev/null || true
wait $PID 2>/dev/null || true

echo "=== 证据清单 ==="
ls -la evidence/
echo "[done] 项目二全部证据已生成"
