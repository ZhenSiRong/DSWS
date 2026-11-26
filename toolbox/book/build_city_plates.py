#!/usr/bin/env python3
"""把城市全景大图拆成 A4 书内图版（不把 3200×2000 原图直接塞进页面）。

输入：
  tutorial/images/city-4stages.png   （五级横排（L1–L5），每级一块）
  tutorial/images/city-map-24.png    （24 页城市设施全景）

输出（toolbox/book/.plates/，gitignore）：
  stage-L1-top/bottom.png … stage-L5-top/bottom.png   10 张阶段图版
  map-overview.png                                    带 A1–B4 网格的总览
  map-A1.png … map-B4.png                             8 张分区放大图版
  plates.json                                         caption/来源/尺寸清单
"""
from __future__ import annotations
import hashlib, json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
TUTORIAL = ROOT / "tutorial" / "images"
OUT = Path(__file__).resolve().parent / ".plates"
STAGES = TUTORIAL / "city-5stages.png"
MAP = TUTORIAL / "city-map-24.png"

STAGE_META = [
    ("L1", "荒地工地", "城市俯瞰与阶段说明", "横切系统、学生动作与判据"),
    ("L2", "通水电网", "城市俯瞰与阶段说明", "横切系统、学生动作与判据"),
    ("L3", "智慧城市", "城市俯瞰与阶段说明", "横切系统、学生动作与判据"),
    ("L4", "城市安防", "城市俯瞰与阶段说明", "横切系统、学生动作与判据"),
    ("L5", "装修", "入口与承重墙说明", "体验层、学生动作与判据"),
]
# city-5stages.png 由 toolbox/book/build_city_stages.py 生成：1600×1000 设计画布 @2x。
# 五列：x=80/692/1304/1916/2528，列宽 592；上/下两半在 y=280/1000 处重叠切。
STAGE_X = [80, 692, 1304, 1916, 2528]
STAGE_W = 592
STAGE_TOP = (280, 760)      # y, height
STAGE_BOTTOM = (1000, 700)  # y, height; 与 top 重叠 40px，切页不丢行

# 语义图版：不按 4×2 均分切；每个区域是一张可独立阅读的图版。
# 坐标是 design canvas（1600×1000），CROP 时乘 2 到 3200×2000。
MAP_PLATES = [
    ("map-02-municipal", "市政配套区：P0 场地 / 3307 · 8000 · 8081", (20, 96, 420, 214)),
    ("map-03-storage", "仓储区：P1 / P2 / P10 / P18 / 数据底座", (20, 300, 420, 644)),
    ("map-04-service-north", "服务区北：查询 / 生成 / 执行（P3–P7 / P11 / P12）", (432, 96, 732, 540)),
    ("map-05-service-south", "服务区南：审计 / 安防 / 观测（P14–P22）", (432, 610, 732, 336)),
    ("map-06-portal", "门户区：P9 / P13 / P23 / 成熟前端", (1154, 96, 428, 430)),
    ("map-07-registry", "改造层登记处：14 件交付物 + 设施索引", (1154, 520, 428, 440)),
]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def font(size: int):
    for candidate in (
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    ):
        if Path(candidate).is_file():
            try:
                return ImageFont.truetype(candidate, size)
            except Exception:
                pass
    return ImageFont.load_default()


def overview_with_grid(src: Path, dst: Path) -> None:
    im = Image.open(src).convert("RGB")
    dr = ImageDraw.Draw(im, "RGBA")
    f = font(42)
    # 4 列 × 2 行的分区网格（与手工切图坐标一致）
    for i in range(1, 4):
        x = 20 + i * 790
        dr.line([(x, 0), (x, im.height)], fill=(204, 48, 48, 120), width=4)
    y = 970
    dr.line([(0, y), (im.width, y)], fill=(204, 48, 48, 120), width=4)
    for label, _, x, y0 in MAP_LABELS:
        X = x + 18
        Y = y0 + 12
        tw = dr.textlength(label, font=f)
        dr.rectangle([(X - 8, Y - 6), (X + tw + 8, Y + 50)], fill=(204, 48, 48, 190))
        dr.text((X, Y), label, font=f, fill=(255, 255, 255, 255))
    im.save(dst)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    plates: list[dict] = []
    stage_img = Image.open(STAGES).convert("RGB")
    for i, (level, name, top_part, bottom_part) in enumerate(STAGE_META):
        x = STAGE_X[i]
        top = stage_img.crop((x, 280, x + STAGE_W, 1000))
        top_path = OUT / f"stage-{level}-top.png"
        top.save(top_path)
        bottom = stage_img.crop((x, 1000, x + STAGE_W, 1700))
        bottom_path = OUT / f"stage-{level}-bottom.png"
        bottom.save(bottom_path)
        plates.append({
            "file": top_path.name, "kind": "stage", "level": level,
            "caption": f"{level} {name}（一）：{top_part}",
            "source": "tutorial/images/city-5stages.png", "sha256": sha(top_path),
        })
        plates.append({
            "file": bottom_path.name, "kind": "stage", "level": level,
            "caption": f"{level} {name}（二）：{bottom_part}",
            "source": "tutorial/images/city-5stages.png", "sha256": sha(bottom_path),
        })

    stage_plates = [p for p in plates if p["kind"] == "stage"]
    plates = [{
        "file": "map-01-overview.png", "kind": "overview",
        "caption": "24 页城市设施全景总览（分区图版见 D-12–D-17）",
        "source": "tutorial/images/city-map-24.png", "sha256": sha(MAP),
    }]
    plates.extend(stage_plates)
    map_img = Image.open(MAP).convert("RGB")
    for idx, (name, desc, rect) in enumerate(MAP_PLATES):
        if rect is None:
            path = OUT / f"{name}.png"
            map_img.save(path)
        else:
            x, y, w, h = (int(v * 2) for v in rect)
            path = OUT / f"{name}.png"
            map_img.crop((x, y, min(x + w, map_img.width), min(y + h, map_img.height))).save(path)
        plates.append({
            "file": path.name, "kind": "map", "label": name,
            "caption": f"{desc}",
            "source": "tutorial/images/city-map-24.png", "sha256": sha(path),
        })

    for i, plate in enumerate(plates, 1):
        plate["caption"] = f"图 D-{i} · {plate['caption']}"
    manifest = {
        "source_stages": {"path": "tutorial/images/city-5stages.png", "sha256": sha(STAGES)},
        "source_map": {"path": "tutorial/images/city-map-24.png", "sha256": sha(MAP)},
        "plates": plates,
    }
    (OUT / "plates.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"city plates: {len(plates)} → {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
