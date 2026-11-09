#!/usr/bin/env python3
"""给 61s 演示片叠加「右上角功能角标 + 底部字幕」。

风格对齐 v1：右上角深色圆角感角标（PRD 编号 · 功能名），底部深色条 + 标题/说明。
不重录，只在成片上按时间轴叠加，保留现有剪辑。

用法：
    python3 deliverable/v2/make_demo_overlay.py
产物：
    deliverable/v2/demo-overlay.ass
    deliverable/v2/DSWS-v2-original-ui-demo.annotated.mp4
"""
from __future__ import annotations

import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "DSWS-v2-original-ui-demo.mp4"
ASS = HERE / "demo-overlay.ass"
OUT = HERE / "DSWS-v2-original-ui-demo.annotated.mp4"

SEGMENTS = [
    (0.0, 3.8, "PRD 总览 · 电商问数", "原版界面 + LangGraph 12 节点 + 真实问数"),
    (3.8, 7.7, "PRD 2 · LangGraph 12 节点 / 10 步", "步骤目录来自 /api/steps，不硬编码"),
    (7.7, 11.8, "PRD 1 · 自然语言问数 NL2SQL", "中文提问 → 生成 SQL → 只读执行"),
    (11.8, 18.6, "PRD 1 · 真实结果", "5 行，来自 MySQL 只读账号 dw_reader"),
    (18.6, 22.7, "PRD 3 · 自校验 + 自纠错", "不是每次都需要校正"),
    (22.7, 30.2, "PRD 1 · 结果表", "数字列按类型渲染，不用字符串冒充"),
    (30.2, 37.0, "PRD 3 · 自校验", "校验SQL 先跑，不合格才进校正"),
    (37.0, 41.5, "PRD 3 · correct_sql 接管", "最多一次；校正后重新过 guard + policy"),
    (41.5, 45.2, "PRD 3 · 校正成功", "重新校验通过，执行返回结果"),
    (45.2, 50.0, "PRD 4 · 安全边界", "构造一条 UNION 查询"),
    (50.0, 55.6, "PRD 4 · SQL_REJECTED", "危险构造不校正，直接拒绝"),

    (55.6, 57.4, "PRD 4 · 校正未触发", "策略拒绝不送回模型"),
    (57.4, 61.27, "DSWS v2 · 验收完成", "12 节点 · 校正闭环 · 安全拒绝"),
]

HEAD = """[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Badge,Noto Sans CJK SC,38,&H00FFFFFF,&H00FFFFFF,&H00111111,&H00111111,-1,0,0,0,100,100,0,0,3,10,0,9,40,40,20,1
Style: Sub,Noto Sans CJK SC,34,&H00FFFFFF,&H00FFFFFF,&H00111111,&H00111111,0,0,0,0,100,100,0,0,1,2,0,2,60,60,28,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def ts(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int(seconds % 3600 // 60)
    s = seconds % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def main() -> int:
    lines = [HEAD]
    for start, end, badge, sub in SEGMENTS:
        lines.append(f"Dialogue: 0,{ts(start)},{ts(end)},Badge,,0,0,0,,{badge}\n")
        lines.append(f"Dialogue: 0,{ts(start)},{ts(end)},Sub,,0,0,0,,{sub}\n")
    ASS.write_text("".join(lines), encoding="utf-8")
    print(f"wrote {ASS}")

    vf = (
        "drawbox=x=0:y=ih-92:w=iw:h=92:color=black@0.88:t=fill,"
        "drawbox=x=0:y=ih-95:w=iw:h=3:color=0xf0b429@1:t=fill,"
        f"subtitles={ASS}:fontsdir=/usr/share/fonts"
    )
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(SRC),
        "-vf", vf,
        "-c:v", "libx264", "-crf", "20", "-preset", "medium",
        "-pix_fmt", "yuv420p", "-r", "30", "-an",
        str(OUT),
    ]
    subprocess.run(cmd, check=True)
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
