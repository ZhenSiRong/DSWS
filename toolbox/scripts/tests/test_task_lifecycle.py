#!/usr/bin/env python3
"""task.py 生命周期验收测试（隔离：monkeypatch 把 REPO/LEDGER 指到临时 git 仓库）。

覆盖 toolbox/workflows/task-lifecycle.md §12：环拒/依赖闸/并行/review 三态/降级/check/render/board/migrate。
跑：system/backend/.venv/bin/python -m pytest toolbox/scripts/tests/test_task_lifecycle.py -q
渲染测试需 google-chrome + ImageMagick + MERMAID_JS（fixture 自动指向仓库本地副本）。
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
REAL_REPO = SCRIPTS.parent
sys.path.insert(0, str(SCRIPTS))
import task  # noqa: E402
import render_progress_gantt  # noqa: E402,F401  (预缓存，供 cmd_render import)


def git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


@pytest.fixture()
def repo(tmp_path, monkeypatch):
    r = tmp_path / "repo"
    r.mkdir()
    git(r, "init", "-q")
    (r / "README.md").write_text("# sandbox\n", encoding="utf-8")
    git(r, "add", "-A")
    git(r, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init")
    (r / "scripts").mkdir()
    shutil.copy(SCRIPTS / "render_progress_gantt.py", r / "scripts" / "render_progress_gantt.py")
    monkeypatch.setattr(task, "REPO", r)
    monkeypatch.setattr(task, "LEDGER", r / "workflows" / "ledger.yaml")
    monkeypatch.setattr(task, "REVIEWS", r / "workflows" / "reviews")
    monkeypatch.setattr(task, "DEFAULT_DOC", r / "workflows" / "gantt.md")
    monkeypatch.setattr(task, "DEFAULT_PNG", r / "workflows" / "gantt.png")
    for cand in (REAL_REPO / "design" / "assets" / "mermaid.min.js",
                 REAL_REPO / "assets" / "mermaid.min.js"):
        if cand.exists():
            monkeypatch.setenv("MERMAID_JS", str(cand))
            break
    return r


def add(tid, title="t", deps=None, group="g"):
    return task.cmd_add(NS(id=tid, title=title, group=group, deps=deps))


def start(tid, agent=None):
    return task.cmd_start(NS(id=tid, agent=agent))


def done(tid, force=False, reason=None):
    return task.cmd_done(NS(id=tid, force=force, reason=reason))


def verdict(tid, verdict_value, repo):
    rp = repo / "workflows" / "reviews" / f"{tid}.md"
    rp.parent.mkdir(parents=True, exist_ok=True)
    rp.write_text(f"# review {tid}\n\n结论。\n\nVERDICT: {verdict_value}\n", encoding="utf-8")
    return task.cmd_verdict(NS(id=tid, report=None))


def status(repo, tid):
    return task.tmap(task.load_ledger())[tid]["status"]


# --------------------------------------------------------------------------- #
def test_add_rejects_cycle(repo):
    add("A", deps="B")
    with pytest.raises(SystemExit):
        add("B", deps="A")


def test_add_rejects_duplicate(repo):
    add("A")
    with pytest.raises(SystemExit):
        add("A")


def test_start_dep_gate(repo):
    add("P")
    add("Q", deps="P")
    with pytest.raises(SystemExit):  # P 未 done
        start("Q")
    start("P")
    assert status(repo, "P") == "doing"
    with pytest.raises(SystemExit):  # P 仍 doing
        start("Q")
    done("P", force=True, reason="ok")
    start("Q")  # P done → 解锁
    assert status(repo, "Q") == "doing"


def test_start_creates_worktree_git_degrade(repo):
    add("W")
    start("W")  # Orca 不可用 → git worktree 降级
    t = task.tmap(task.load_ledger())["W"]
    assert Path(t["worktree"]).exists()
    assert t["branch"] == "task/W"
    assert t["agent"] == "manual"
    assert t["provenance"] and "&manual -s manual-W" in t["provenance"]
    assert t["started_at"]


def test_parallel_doing(repo):
    add("X")
    add("Y")
    start("X")
    start("Y")
    assert status(repo, "X") == "doing"
    assert status(repo, "Y") == "doing"


def test_done_review_pass(repo):
    add("X")
    start("X")
    assert done("X") == 2  # review 待派
    assert task.tmap(task.load_ledger())["X"]["review"]["verdict"] == "pending"
    assert verdict("X", "pass", repo) == 0
    t = task.tmap(task.load_ledger())["X"]
    assert t["status"] == "done" and t["ended_at"] and t["review"]["verdict"] == "pass"


def test_done_review_blocker(repo):
    add("Y")
    start("Y")
    assert done("Y") == 2
    assert verdict("Y", "blocker", repo) == 1
    t = task.tmap(task.load_ledger())["Y"]
    assert t["status"] == "doing" and t["review"]["verdict"] == "blocker"


def test_done_force_overrides(repo):
    add("Z")
    start("Z")
    with pytest.raises(SystemExit):  # --force 缺 reason
        done("Z", force=True)
    assert done("Z", force=True, reason="误判，强推") == 0
    t = task.tmap(task.load_ledger())["Z"]
    assert t["status"] == "done"
    assert t["review"]["overridden"] is True
    assert t["review"]["override_reason"] == "误判，强推"


def test_fail_block_unblock_reopen(repo):
    add("F")
    start("F")
    task.cmd_block(NS(id="F", reason="卡"))
    assert task.tmap(task.load_ledger())["F"]["blocked_reason"] == "卡"
    task.cmd_unblock(NS(id="F"))
    assert task.tmap(task.load_ledger())["F"]["blocked_reason"] is None
    task.cmd_fail(NS(id="F", reason="崩"))
    assert status(repo, "F") == "todo"
    start("F")
    done("F", force=True, reason="ok")
    task.cmd_reopen(NS(id="F", reason="重做"))
    assert status(repo, "F") == "doing"


def test_check_catches_fake_done(repo):
    add("D")
    data = task.load_ledger()
    t = task.tmap(data)["D"]
    t["status"] = "done"  # 无 review、无时间戳 → 假 done
    t["ended_at"] = task.now()
    task.save_ledger(data)
    assert task.cmd_check(NS(quick=True)) == 1


def test_render_then_check_pass(repo):
    add("R1")
    start("R1")
    done("R1", force=True, reason="ok")
    assert task.cmd_render(NS(width=1200)) == 0
    png = repo / "workflows" / "gantt.png"
    assert png.exists() and png.stat().st_size > 0
    meta = png.with_suffix(".png.meta")
    assert meta.read_text().strip() == task.ledger_sha()
    doc = repo / "workflows" / "gantt.md"
    assert "```mermaid" in doc.read_text()
    assert task.cmd_check(NS(quick=True)) == 0


def test_gen_mermaid_sanitizes_ascii_colon_in_title(repo):
    add("R1", title="契约全覆盖: coverage: static + 24 页")
    mmd = task.gen_mermaid(task.load_ledger())
    line = [ln for ln in mmd.splitlines() if "R1" in ln][0]
    label, _, _rest = line.strip().partition(":")
    assert "coverage" in label
    assert "coverage: static" not in line
    assert "coverage： static" in line


def test_check_gantt_drift(repo):
    add("R1")
    start("R1")
    done("R1", force=True, reason="ok")
    task.cmd_render(NS(width=1200))
    # 改台账但不重渲 → 身份对账漂移
    data = task.load_ledger()
    task.tmap(data)["R1"]["title"] = "改标题"
    task.save_ledger(data)
    assert task.cmd_check(NS(quick=True)) == 1


def test_migrate_parses_gantt(repo):
    h = repo / "humen-desicions"
    h.mkdir()
    (h / "14-progress-gantt.md").write_text(
        "# board\n\n```mermaid\ngantt\n    title t\n"
        "    section 已收口\n    任务甲        :done, s1, 2026-11-23, 1d\n"
        "    section 试点\n    任务乙        :g1, 2026-11-24, 1d\n"
        "    任务丙        :g2, after g1, 1d\n```\n",
        encoding="utf-8",
    )
    assert task.cmd_migrate(NS()) == 0
    tm = task.tmap(task.load_ledger())
    assert tm["s1"]["status"] == "done"
    assert tm["g2"]["depends_on"] == ["g1"]
    assert tm["g1"]["group"] == "试点" or tm["g1"]["group"]  # 非空组名


def test_evidence_attach_and_verify(repo):
    add("E")
    start("E")
    # file 证据：存在 + 判据命中；cmd 证据：exit 0 + 判据命中
    task.cmd_evidence(NS(id="E", kind="file", path="README.md", run=None,
                         criterion="sandbox", clear=False))
    task.cmd_evidence(NS(id="E", kind="cmd", run="echo marktext-v0.23.0", path=None,
                         criterion="v0.23.0", clear=False))
    t = task.tmap(task.load_ledger())["E"]
    assert len(t["evidence"]) == 2
    ok, _ = task.check_evidence(t)
    assert ok
    # 判据不命中 → 验证失败
    task.cmd_evidence(NS(id="E", kind="file", path="README.md", run=None,
                         criterion="绝无此串", clear=False))
    ok2, _ = task.check_evidence(task.tmap(task.load_ledger())["E"])
    assert not ok2
    # done 后拒改证据（保护已钉证据）
    done("E", force=True, reason="ok")
    with pytest.raises(SystemExit):
        task.cmd_evidence(NS(id="E", kind="cmd", run="true", path=None,
                             criterion="", clear=False))
    # reopen 后可 --clear
    task.cmd_reopen(NS(id="E", reason="重钉"))
    task.cmd_evidence(NS(id="E", kind=None, path=None, run=None, criterion=None, clear=True))
    assert task.tmap(task.load_ledger())["E"]["evidence"] == []


def test_board_generates_html(repo):
    add("B1", title="含 <b>标签</b> 的标题", group="看板")
    start("B1")
    done("B1", force=True, reason="ok")
    add("B2", title="待开始", deps="B1")
    assert task.cmd_board(NS(out=None, no_check=True)) == 0
    board = repo / "workflows" / "board.html"
    meta_path = repo / "workflows" / "board.html.meta"
    assert board.exists() and meta_path.exists()
    html_text = board.read_text(encoding="utf-8")
    assert "B1" in html_text and "B2" in html_text
    assert 'class="badge st-done"' in html_text
    assert 'class="badge st-todo"' in html_text
    assert "<b>标签</b>" not in html_text
    assert "&lt;b&gt;标签&lt;/b&gt;" in html_text
    assert "可开始" in html_text
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    assert meta["ledger_sha256"] == task.ledger_sha()
    assert meta["task_count"] == 2
    assert "http://" not in html_text and "https://" not in html_text
    assert "<script src" not in html_text and "<link " not in html_text
    assert str(repo) not in html_text  # 不泄露绝对路径


def test_check_board_drift(repo, capsys):
    add("BD")
    start("BD")
    done("BD", force=True, reason="ok")
    assert task.cmd_board(NS(out=None, no_check=True)) == 0

    task.cmd_check(NS(quick=True))
    board_line = next(
        line for line in capsys.readouterr().out.splitlines() if "board 身份对账" in line
    )
    assert "OK" in board_line

    data = task.load_ledger()
    task.tmap(data)["BD"]["title"] = "改标题但不重生成看板"
    task.save_ledger(data)
    assert task.cmd_check(NS(quick=True)) == 1
    board_line = next(
        line for line in capsys.readouterr().out.splitlines() if "board 身份对账" in line
    )
    assert "DRIFT" in board_line
    assert "task.py board" in board_line


def test_check_skips_board_when_absent(repo, capsys):
    add("NB")
    start("NB")
    done("NB", force=True, reason="ok")
    task.cmd_check(NS(quick=True))
    assert "board 身份对账" not in capsys.readouterr().out


def test_board_report_href_relative(repo):
    add("BR")
    start("BR")
    done("BR", force=True, reason="ok")
    data = task.load_ledger()
    report = repo / "workflows" / "reviews" / "BR.md"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text("# review\n\nVERDICT: pass\n", encoding="utf-8")
    task.tmap(data)["BR"]["review"]["report"] = str(report)  # 台账里是绝对路径
    task.save_ledger(data)
    assert task.cmd_board(NS(out=None, no_check=True)) == 0
    html_text = (repo / "workflows" / "board.html").read_text(encoding="utf-8")
    assert str(repo) not in html_text
    assert 'href="reviews/BR.md"' in html_text

