#!/usr/bin/env python3
"""为 32 张设计图生成“读图地图”（机器数据 + 人类目录）。

用法：
    python3 design/scripts/build_reading_paths.py

产物：
    design/diagrams/reading-paths.json
    design/diagrams/reading-paths.yaml
    design/inventory/diagram-catalog.md
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
DIAGRAMS = ROOT / "diagrams"

TRACKS = {
    "01-architecture": ("架构", [
        "先看系统边界与参与者",
        "再沿主箭头看模块/容器调用",
        "最后看灰色边与单点：哪些不在主链路",
    ], "失败：箭头断开或灰色边表示不在主链路，不是故障；真正的失败回到对应章节看错误码。"),
    "02-runtime": ("运行时", [
        "先看触发者（谁发起）",
        "沿编号/箭头走一遍主路径",
        "最后看失败分支与回退边",
    ], "失败：看红色分支与回退边；没有回退边的步骤失败即终止。"),
    "03-data": ("数据", [
        "先看实体与 grain（一行代表什么）",
        "再看主键/外键与关系",
        "最后看约束、值域与口径",
    ], "失败：越界时间、缺列、错 grain 会在校验阶段被拒。"),
    "04-security": ("安全", [
        "先看信任边界在哪",
        "再按顺序看拦截点",
        "最后看被拒绝的路径与出口",
    ], "失败：策略拒绝不进入校正，直接 SQL_REJECTED。"),
    "05-deployment": ("部署", [
        "先看服务与端口",
        "再看启动依赖顺序",
        "最后看健康检查与失败停点",
    ], "失败：前置服务未健康则后续不启动，停点写在健康检查里。"),
    "06-testing": ("测试", [
        "先看层级（单元/集成/端到端）",
        "再看阶段门禁顺序",
        "最后看失败注入覆盖了哪些码",
    ], "失败：任一阶段门禁红，不能进入下一阶段。"),
}


def grab(pattern: str, text: str) -> str:
    m = re.search(pattern, text)
    return m.group(1).strip() if m else ""


def main() -> int:
    entries = []
    for folder in sorted(TRACKS):
        track, path, failure = TRACKS[folder]
        for md in sorted((DIAGRAMS / folder).glob("*.md")):
            text = md.read_text(encoding="utf-8")
            title = next((ln[2:].strip() for ln in text.splitlines() if ln.startswith("# ")), md.stem)
            one = grab(r"\*\*一句话(?:结论)?\*\*[：:]\s*(.+)", text)
            question = grab(r"\*\*这张图回答\*\*[：:]\s*(.+)", text)
            num = md.name.split("-")[0]
            entries.append({
                "id": num,
                "title": title,
                "track": track,
                "one_liner": one,
                "question": question,
                "path": path,
                "failure": failure,
                "md": str(md.relative_to(ROOT)),
                "svg": str(md.with_suffix(".svg").relative_to(ROOT)),
            })

    (DIAGRAMS / "reading-paths.json").write_text(
        json.dumps(entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (DIAGRAMS / "reading-paths.yaml").write_text(
        yaml.safe_dump(entries, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )

    lines = [
        "# 32 张图的地图目录",
        "",
        "> 每张图先回答一个问题，再按 3 步读。完整说明见同名 `.md`。",
        "",
        "| # | 图 | 回答什么 | 读图 1→2→3 | 文件 |",
        "|---|---|---|---|---|",
    ]
    for e in entries:
        q = e["question"] or e["one_liner"]
        if len(q) > 64:
            q = q[:62] + "…"
        path = " → ".join(f"{i + 1} {p}" for i, p in enumerate(e["path"]))
        lines.append(f"| {e['id']} | {e['title']} | {q} | {path} | `{e['svg']}` |")
    (ROOT / "inventory/diagram-catalog.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps({"figures": len(entries), "tracks": sorted({e["track"] for e in entries})}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
