"""把 14 组实验结果画成 SVG（纯标准库，无第三方依赖）。"""
import json
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
data = json.loads((BASE / "evidence" / "experiment_results.json").read_text(encoding="utf-8"))
rows = data["rows"]
W, H = 900, 80 + len(rows) * 34
bars = []
for i, r in enumerate(rows):
    y = 60 + i * 34
    w = int(r["hit_rate"] * 620)
    color = "#1565C0" if r["group"] == "B" else "#4E79A7"
    bars.append(f'<text x="20" y="{y+14}" font-family="sans-serif" font-size="13">{r["group"]} {r["variable"]}</text>')
    bars.append(f'<rect x="250" y="{y}" width="{w}" height="20" fill="{color}"/>')
    bars.append(f'<text x="{260+w}" y="{y+14}" font-family="sans-serif" font-size="12">{r["hit_rate"]:.2%}</text>')
svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">
<rect width="100%" height="100%" fill="#FFFFFF"/>
<text x="20" y="32" font-family="sans-serif" font-size="18" font-weight="bold" fill="#212121">14 组对照实验命中率（{data["run_at"]}）</text>
<text x="20" y="50" font-family="sans-serif" font-size="12" fill="#616161">命中率 = Top-k 含正确来源文档的题数 / 30；蓝色为基线 B</text>
{''.join(bars)}
</svg>'''
out = BASE / "evidence" / "experiment_hit_rate.svg"
out.write_text(svg, encoding="utf-8")
print("evidence/experiment_hit_rate.svg")
