#!/usr/bin/env python3
"""把 PRD 的三类交付物分别整理成独立目录，并各自打 zip。

用法：python3 toolbox/scripts/build_deliverables.py
产物（gitignored）：
  deliverables/design-doc/    设计文档（78 页完整 + 30 图精选 32 页）
  deliverables/source-code/   可部署源码（system/ + Makefile + .env.example）
  deliverables/tutorial-doc/  教程文档（tutorial/ 正典 + HTML/PDF 成书）
  deliverables/packages/{design-doc,source-code,tutorial-doc}.zip
每个目录内写 MANIFEST.md / SHA256SUMS；不移动正典，只做可交付快照。
"""
from __future__ import annotations
import hashlib
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "deliverables"
PACKAGES = OUT / "packages"
TUTORIAL_BOOK = ROOT / "materials" / "deliverable" / "tutorial-book"

IGNORE_SOURCE = shutil.ignore_patterns(
    ".venv", "node_modules", "__pycache__", ".pytest_cache", ".mypy_cache",
    ".ruff_cache", ".DS_Store", "*.pyc", ".env", ".env.*", ".git",
    ".lab", "*.log", "*.tmp",
)
IGNORE_TUTORIAL = shutil.ignore_patterns(
    ".DS_Store", "__pycache__", "*.pyc", "archive", "review", "rebuild",
    "designs", "shots", "verify",
)


def git_head() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return "unknown"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def copy(src: Path, dest: Path, ignore=None) -> None:
    if not src.exists():
        print(f"  ! missing {src}")
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    if src.is_dir():
        shutil.copytree(src, dest, ignore=ignore, dirs_exist_ok=True)
    else:
        shutil.copy2(src, dest)


def manifest(cat: Path, title: str, notes: list[str]) -> None:
    files = sorted(p for p in cat.rglob("*") if p.is_file())
    total = sum(p.stat().st_size for p in files)
    lines = [
        f"# {title}",
        "",
        f"- 来源 commit：`{git_head()}`",
        f"- 生成时间：{datetime.now().isoformat(timespec='seconds')}",
        f"- 文件数：{len(files)}",
        f"- 总计：{total / 1024 / 1024:.1f} MB",
        "", "## 说明", *[f"- {n}" for n in notes],
        "", "## 文件清单", "",
        "| 文件 | 大小 |", "|---|---:|",
    ]
    for p in files:
        lines.append(f"| `{p.relative_to(cat)}` | {p.stat().st_size} B |")
    (cat / "MANIFEST.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    sums = [f"{sha256(p)}  {p.relative_to(cat)}" for p in files if p.name != "SHA256SUMS"]
    (cat / "SHA256SUMS").write_text("\n".join(sums) + "\n", encoding="utf-8")


def build_design() -> None:
    cat = OUT / "design-doc"
    copy(ROOT / "materials" / "design" / "design-doc.pdf", cat / "design-doc.pdf")
    manifest(cat, "设计文档 · DSWS 电商问数智能体", [
        "`design-doc.pdf`：决策生长版（A 类 5 链渐进稿 + A 类图页 + 速查/claims/汇总，≥30 页）",
        "B/C 类图页与旧 `design-doc-30.pdf` 精选版按 D56 不入卷（2026-11-27）",
        "已移除 `dsws-design-atlas.pdf`：它是废弃的教程/图集文档，不是设计文档",
    ])


def build_source() -> None:
    cat = OUT / "source-code"
    copy(ROOT / "Makefile", cat / "Makefile")
    copy(ROOT / "compose.yaml", cat / "compose.yaml")
    copy(ROOT / "compose.lab-ui.yaml", cat / "compose.lab-ui.yaml")
    copy(ROOT / ".env.example", cat / ".env.example")
    copy(ROOT / "system" / "README.md", cat / "SYSTEM-README.md")
    copy(ROOT / "system", cat / "system", IGNORE_SOURCE)
    manifest(cat, "源代码 · 电商问数智能体", [
        "`system/`：backend / frontend / contracts / fixtures / docker / deploy / compose",
        "根 `Makefile` + `compose.yaml` + `.env.example`：按原仓库路径可直接跑",
        "已排除 .venv / node_modules / 缓存 / .env；首次运行按 TRAPS/README 装依赖",
    ])


def build_tutorial() -> None:
    cat = OUT / "tutorial-doc"
    copy(ROOT / "tutorial", cat / "tutorial", IGNORE_TUTORIAL)
    copy(TUTORIAL_BOOK / "tutorial-book.pdf", cat / "tutorial-book.pdf")
    copy(TUTORIAL_BOOK / "tutorial-book.html", cat / "tutorial-book.html")
    manifest(cat, "教程文档 · 电商问数工程手册", [
        "`tutorial/`：24 章 md 正典 + images + read + appendix + OVERVIEW/SPEC/TRAPS/ACCEPTANCE",
        "`tutorial-book.pdf` / `.html`：当前成书（157 页 / 自包含 HTML）",
        "已排除 symlink（toolbox/materials 的 tools、review 等）和旧漫画 archive",
    ])


def zip_cat(name: str) -> Path:
    src = OUT / name
    dst = PACKAGES / f"{name}.zip"
    PACKAGES.mkdir(parents=True, exist_ok=True)
    dst.unlink(missing_ok=True)
    subprocess.run(["zip", "-r", "-q", str(dst), name], cwd=OUT, check=True)
    return dst


def main() -> int:
    OUT.mkdir(exist_ok=True)
    PACKAGES.mkdir(exist_ok=True)
    for sub in ("design-doc", "source-code", "tutorial-doc"):
        shutil.rmtree(OUT / sub, ignore_errors=True)
    print("构建 设计文档 ..."); build_design()
    print("构建 源代码 ..."); build_source()
    print("构建 教程文档 ..."); build_tutorial()
    print("打包 ...")
    for name in ("design-doc", "source-code", "tutorial-doc"):
        z = zip_cat(name)
        print(f"  {z}  {z.stat().st_size/1024/1024:.1f} MB")
    (OUT / "README.md").write_text(
        "# PRD 三类交付物\n\n"
        "| 目录 | 内容 | 单独打包 |\n|---|---|---|\n"
        "| `design-doc/` | 决策生长版设计文档（A 类 5 链渐进稿，≥30 页） | `deliverables/packages/design-doc.zip` |\n"
        "| `source-code/` | `system/` + Makefile + `.env.example` | `deliverables/packages/source-code.zip` |\n"
        "| `tutorial-doc/` | 24 章教程 md + 成书 HTML/PDF | `deliverables/packages/tutorial-doc.zip` |\n\n"
        "生成：`make deliverables`；三个目录互不依赖，可分别拷走/压缩。\n",
        encoding="utf-8",
    )
    print(f"完成：{OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
