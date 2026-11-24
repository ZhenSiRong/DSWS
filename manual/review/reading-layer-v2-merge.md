# 阅读层 v2 合并验收（2026-11-24）

> 合并对象：`reading-layer-v2`（`29b8899`，基于 `73db8b5` checkpoint + A/B/C 四批 + 24 页阅读版 HTML）
> 目标分支：`continue-iterate`；合并提交：`8552187`（`--no-ff`）
> 备份：清理前的本地重叠副本在 `/tmp/reading-merge-backup-20261124-151726.tgz`（合并前 tar，含 p17/p21 WIP、阅读版 HTML、漫画、assets、11–14 文档）

## 合并后闸门（root 真跑）

```
python3 manual/shots/audit_book.py   → 页面：24/24 通过；README 坏链：0
python3 scripts/verify.py --fast     → T0 PASS（0.01s）
make verify                          → T1 PASS（10.71s，4/4 offline，证据 WARN×2）
make audit                           → AUDIT PASS：5/5 全绿
python3 scripts/tests/test_verify.py → 33 tests OK
manual/shots/render_read.py --all    → 24 页 HTML，幂等（无 diff）
```

## 内容验收

- 24 页阅读版 HTML 已入库（`manual/read/page-00.html` … `page-23.html`）
- 保护区脚本核对 20 个改动页：代码围栏 / 六段标题 / 图片引用 / 粗体判据 / 数字 → **0 异常**
- 四批报告：`manual/review/reading-layer-batch-{A,B,C1,C2}-report.md`；台账 `r1–r4` 已按报告与 root 复核收口

## 残留（第二轮细修候选）

独立复测：仍有 **24 处 >200 字符单元**（7 页：p10×5、p15×4、p16×4、p19×4、p20×3、p23×3、p18×1），主要是：
- 单行过长的 `>` 前置引用（如 p20 416 字第一行）
- 很长的 bullet（p10 362/359/338 字等）
- 长编号步骤行（p16 317 字等）

处理建议：只加断行/拆 bullet（不改字、不删内容），跑 audit+verify+render 即可；预计 20–30 分钟。

## 下一步

1. 第二轮细修（24 处，可选）
2. 漫画推广到所有页面（`arkcli` 已装，Seedream 5.0 Flash；先出 2–3 张预览再批量）
3. `v1.1.0` tag/push/release
