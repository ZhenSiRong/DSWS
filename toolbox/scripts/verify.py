#!/usr/bin/env python3
"""verify.py —— 教材可跟随性验收线（核心 v1：T0 / T1）

背景：教材修订后最怕「跟做断层」——页面里的命令/路径/关键输出和代码脱节。
本脚本把手写页面与机器可跑的契约绑在一起：

  T0（--fast，秒级，供 pre-commit 调）
      契约解析与字段校验 → 页面注解 ↔ 契约双向同步 → 静态存在性（路径/符号）
      → 证据文件存在。**不执行任何命令。**
  T1（默认，供 make verify 调）
      T0 + 按顺序执行 kind: offline 的命令，断言 exit / 关键行 / 正则；
      若块声明 page_contains，还要求这些关键输出在页面里可见、且在真实输出里出现
      （防「页面写 15 passed、实际跑出 14 passed」的假绿）。
      kind: manual 的块只做命令同步校验，不执行。
      证据文件 mtime 比页面旧 → warn（--strict 变 fail）。

契约目录：tutorial/verify/contracts/<page>.yaml
页面注解：在 ```bash 围栏前一行写 <!-- verify: <marker> -->（中间允许一个空行）。
可见输出绑定：在 ```text 围栏前一行写 <!-- verify-out: <marker> ... -->，
把 page_contains 的 token 锚定到该围栏（而不是全页任意位置）。
schema 与规则说明见 tutorial/verify/README.md。

命令归一化规则（页面块内容与契约 cmd 用同一规则比较）：
  1. 统一换行为 \\n（\\r\\n / \\r → \\n）；
  2. 每行去掉首尾空白；
  3. 行内连续空格 / 制表符折叠为单个空格；
  4. 丢弃空行；
  5. 剩余行按原顺序用 \\n 连接（因此空行数量不参与比较）。

用法：
    python3 toolbox/scripts/verify.py            # T1 = T0 + 执行 offline 命令
    python3 toolbox/scripts/verify.py --fast     # T0：只做静态验收
    python3 toolbox/scripts/verify.py --strict   # 证据缺失（T0）/ 证据过期（T1）从 warn 变 fail
    python3 toolbox/scripts/verify.py --page page-17   # 只验收一页（也接受 17）
    python3 toolbox/scripts/verify.py --list     # 列出契约（不验收）
    python3 toolbox/scripts/verify.py --json     # 机器可读汇总（stdout 只有 JSON）

退出码：0 通过 / 1 验收失败 / 2 契约或配置错误。
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import re
import signal
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
CONTRACTS_REL = Path("toolbox/verify/contracts")
MANUAL_REL = Path("tutorial")
DEFAULT_TIMEOUT_SEC = 120
OUTPUT_TAIL_LINES = 60
PAGE_RE = re.compile(r"^page-\d{2}$")
MARKER_TOKEN_RE = re.compile(r"^[A-Za-z0-9._-]+$")
ANNOTATION_RE = re.compile(r"<!--\s*verify:\s*([A-Za-z0-9._-]+)\s*-->")
ANNOTATION_LINE_RE = re.compile(r"^\s*<!--\s*verify:\s*([A-Za-z0-9._-]+)\s*-->\s*$")
OUT_ANNOTATION_RE = re.compile(r"<!--\s*verify-out:\s*([A-Za-z0-9._\- ]+?)\s*-->")
WHITESPACE_RE = re.compile(r"[ \t]+")

TOP_KEYS = {"page", "title", "blocks", "static", "evidence", "coverage"}
COVERAGE_KEYS = {"blocks", "static"}
BLOCK_KEYS = {"id", "marker", "kind", "cmd", "expect", "timeout_sec", "reason", "note", "page_contains"}
EXPECT_KEYS = {"exit", "contains", "regex"}
STATIC_KEYS = {"paths", "symbols"}
SYMBOL_KEYS = {"file", "pattern"}
EVIDENCE_KEYS = {"path", "note"}


# ---------------------------------------------------------------------------
# 基础工具
# ---------------------------------------------------------------------------
def normalize_cmd(text: Any) -> str:
    """按模块 docstring 的 5 条规则归一化命令文本。"""
    if not isinstance(text, str):
        return ""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines: list[str] = []
    for raw in text.split("\n"):
        line = WHITESPACE_RE.sub(" ", raw.strip())
        if line:
            lines.append(line)
    return "\n".join(lines)


def sanitize(text: str, root: Path) -> str:
    """输出清洗：不打印绝对仓库路径 / 家目录 / 用户名。"""
    if not text:
        return text
    for needle, repl in ((str(root), "<仓库根>"), (str(Path.home()), "<家目录>")):
        if needle and needle != "/":
            text = text.replace(needle, repl)
    try:
        user = getpass.getuser()
    except Exception:  # noqa: BLE001 - 取不到用户名不影响验收
        user = ""
    if user and len(user) >= 3:
        text = text.replace(user, "<用户>")
    return text


def _tail_lines(text: str, limit: int = OUTPUT_TAIL_LINES) -> list[str]:
    lines = text.splitlines()
    if len(lines) <= limit:
        return lines
    return lines[-limit:]


def _fmt_seconds(value: float) -> str:
    return f"{value:.1f}s"


# ---------------------------------------------------------------------------
# 数据结构
# ---------------------------------------------------------------------------
@dataclass(slots=True)
class PageBlock:
    """页面里一个 fenced block（目前只关心 ```bash）。"""

    marker: str | None
    fence_line: int
    cmd: str


@dataclass(slots=True)
class BlockSpec:
    id: str
    marker: str
    kind: str
    cmd: str
    reason: str = ""
    expect: dict[str, Any] | None = None
    timeout_sec: float = DEFAULT_TIMEOUT_SEC
    page_contains: list[str] = field(default_factory=list)
    note: str = ""


@dataclass(slots=True)
class Contract:
    path_rel: str
    page: str
    title: str
    blocks: list[BlockSpec]
    paths: list[str]
    symbols: list[tuple[str, str]]
    evidence: list[dict[str, str]]
    coverage: str = "blocks"  # blocks | static


@dataclass(slots=True)
class Issue:
    check: str
    message: str
    detail: list[str] = field(default_factory=list)


@dataclass(slots=True)
class Execution:
    block_id: str
    status: str = "pass"  # pass | fail
    duration_sec: float = 0.0
    exit_code: int | None = None
    failures: list[str] = field(default_factory=list)
    output_tail: list[str] = field(default_factory=list)


@dataclass(slots=True)
class PageResult:
    contract: Contract
    failures: list[Issue] = field(default_factory=list)
    warnings: list[Issue] = field(default_factory=list)
    executions: list[Execution] = field(default_factory=list)


def page_ok(result: PageResult, strict: bool) -> bool:
    if result.failures:
        return False
    if strict and result.warnings:
        return False
    return all(ex.status == "pass" for ex in result.executions)


# ---------------------------------------------------------------------------
# 契约加载与校验（任何不合法都退出码 2）
# ---------------------------------------------------------------------------
def _rel(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:  # 极端情况下（软链等）退回文件名
        return path.name


def _unsafe_rel(rel: str) -> bool:
    """相对路径不得逃出仓库根（绝对路径 / .. 段）。"""
    if Path(rel).is_absolute():
        return True
    return any(part == ".." for part in Path(rel).parts)


def _validate_contract(rel: str, stem: str, data: Any, root: Path) -> tuple[Contract | None, list[str]]:
    errors: list[str] = []

    def err(msg: str) -> None:
        errors.append(f"{rel}：{msg}")

    if not isinstance(data, dict):
        return None, [f"{rel}：顶层必须是映射（key: value）"]

    unknown = sorted(set(data) - TOP_KEYS)
    if unknown:
        err(f"未知顶层字段 {unknown}（允许：{sorted(TOP_KEYS)}）")

    page = data.get("page")
    if not isinstance(page, str) or not PAGE_RE.match(page):
        err("page 必须是 page-XX 形式的字符串")
    elif page != stem:
        err(f"page 字段 {page} 与文件名 {stem}.yaml 不一致")

    title = data.get("title", "")
    if title is None:
        title = ""
    if not isinstance(title, str):
        err("title 必须是字符串")
        title = ""

    coverage = data.get("coverage", "blocks")
    if not isinstance(coverage, str) or coverage not in COVERAGE_KEYS:
        err(f"coverage 必须是 {sorted(COVERAGE_KEYS)} 之一（实际 {coverage!r}；缺省为 blocks）")
        coverage = "blocks"

    blocks_raw = data.get("blocks")
    if coverage == "static":
        if blocks_raw not in (None, []):
            err("coverage: static 时 blocks 必须省略或为空（static 契约不执行任何块）")
        blocks_raw = []
    elif not isinstance(blocks_raw, list) or not blocks_raw:
        err("blocks 必须是非空列表（整栈页无法执行块时写 coverage: static）")
        blocks_raw = []

    blocks: list[BlockSpec] = []
    seen_ids: set[str] = set()
    seen_markers: set[str] = set()
    for index, raw_block in enumerate(blocks_raw):
        where = f"blocks[{index}]"
        if not isinstance(raw_block, dict):
            err(f"{where} 必须是映射")
            continue
        unknown_block = sorted(set(raw_block) - BLOCK_KEYS)
        if unknown_block:
            err(f"{where} 未知字段 {unknown_block}（允许：{sorted(BLOCK_KEYS)}）")

        block_id = raw_block.get("id")
        marker = raw_block.get("marker")
        kind = raw_block.get("kind")
        cmd = raw_block.get("cmd")

        ok_id = isinstance(block_id, str) and bool(block_id.strip())
        if not ok_id:
            err(f"{where}.id 缺失或不是非空字符串")
        elif block_id in seen_ids:
            err(f"{where}.id 重复：{block_id}")
        else:
            seen_ids.add(block_id)

        ok_marker = isinstance(marker, str) and bool(MARKER_TOKEN_RE.match(marker))
        if not ok_marker:
            err(f"{where}.marker 缺失或含非法字符（允许字母/数字/._-）")
        elif marker in seen_markers:
            err(f"{where}.marker 重复：{marker}")
        else:
            seen_markers.add(marker)

        if not isinstance(cmd, str) or not normalize_cmd(cmd):
            err(f"{where}.cmd 缺失或为空")

        expect: dict[str, Any] | None = None
        if kind == "offline":
            expect_raw = raw_block.get("expect")
            if not isinstance(expect_raw, dict):
                err(f"{where}.expect 缺失（offline 块必须声明 exit / contains / regex）")
            else:
                expect = _validate_expect(where, expect_raw, err)
            _validate_timeout(where, raw_block, err)
        elif kind == "manual":
            reason = raw_block.get("reason")
            if not isinstance(reason, str) or not reason.strip():
                err(f"{where}.reason 缺失（manual 块必须写明不执行的理由）")
            if "expect" in raw_block:
                err(f"{where} 是 manual 块，不执行，不应声明 expect")
            if "timeout_sec" in raw_block:
                err(f"{where} 是 manual 块，不执行，不应声明 timeout_sec")
        else:
            err(f"{where}.kind 必须是 offline 或 manual（实际 {kind!r}）")

        page_contains: list[str] = []
        if "page_contains" in raw_block:
            raw_tokens = raw_block["page_contains"]
            if kind != "offline":
                err(f"{where}.page_contains 只允许 offline 块（manual 块不执行，无法绑定真实输出）")
            elif not isinstance(raw_tokens, list) or not raw_tokens:
                err(f"{where}.page_contains 必须是非空字符串列表")
            else:
                for pos, token in enumerate(raw_tokens):
                    if not isinstance(token, str) or not token.strip():
                        err(f"{where}.page_contains[{pos}] 必须是非空字符串")
                    else:
                        page_contains.append(token)

        if isinstance(block_id, str) and isinstance(marker, str) and isinstance(cmd, str):
            reason = raw_block.get("reason") if isinstance(raw_block.get("reason"), str) else ""
            note = raw_block.get("note") if isinstance(raw_block.get("note"), str) else ""
            timeout = raw_block.get("timeout_sec", DEFAULT_TIMEOUT_SEC)
            timeout_sec = float(timeout) if isinstance(timeout, (int, float)) and not isinstance(timeout, bool) else DEFAULT_TIMEOUT_SEC
            blocks.append(
                BlockSpec(
                    id=block_id,
                    marker=marker,
                    kind=str(kind),
                    cmd=cmd,
                    reason=reason,
                    expect=expect,
                    timeout_sec=timeout_sec,
                    page_contains=page_contains,
                    note=note,
                )
            )

    paths, symbols, evidence = _validate_static(rel, data, err)
    if coverage == "static" and not paths and not symbols:
        err("coverage: static 的契约至少要有一条 static.paths 或 static.symbols（否则没有可验内容）")
    if errors:
        return None, errors
    assert isinstance(page, str) and isinstance(title, str)  # page_ok 已保证类型
    return (
        Contract(
            path_rel=rel,
            page=page,
            title=title,
            blocks=blocks,
            paths=paths,
            symbols=symbols,
            evidence=evidence,
            coverage=coverage,
        ),
        [],
    )


def _validate_expect(where: str, expect_raw: dict[str, Any], err) -> dict[str, Any]:
    unknown = sorted(set(expect_raw) - EXPECT_KEYS)
    if unknown:
        err(f"{where}.expect 未知字段 {unknown}（允许：{sorted(EXPECT_KEYS)}）")
    exit_code = expect_raw.get("exit")
    if not isinstance(exit_code, int) or isinstance(exit_code, bool):
        err(f"{where}.expect.exit 必须是整数（子进程退出码）")
        exit_code = 0
    contains_raw = expect_raw.get("contains", [])
    contains: list[str] = []
    if not isinstance(contains_raw, list):
        err(f"{where}.expect.contains 必须是字符串列表")
    else:
        for pos, item in enumerate(contains_raw):
            if not isinstance(item, str) or not item:
                err(f"{where}.expect.contains[{pos}] 必须是非空字符串")
            else:
                contains.append(item)
    regex_raw = expect_raw.get("regex", [])
    regexes: list[str] = []
    if not isinstance(regex_raw, list):
        err(f"{where}.expect.regex 必须是字符串列表")
    else:
        for pos, item in enumerate(regex_raw):
            if not isinstance(item, str) or not item:
                err(f"{where}.expect.regex[{pos}] 必须是非空字符串")
                continue
            try:
                re.compile(item)
            except re.error as exc:
                err(f"{where}.expect.regex[{pos}] 不是合法正则：{exc}")
            else:
                regexes.append(item)
    return {"exit": exit_code, "contains": contains, "regex": regexes}


def _validate_timeout(where: str, raw_block: dict[str, Any], err) -> None:
    timeout = raw_block.get("timeout_sec", DEFAULT_TIMEOUT_SEC)
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or timeout <= 0:
        err(f"{where}.timeout_sec 必须是正数（秒）")


def _validate_static(rel: str, data: dict[str, Any], err) -> tuple[list[str], list[tuple[str, str]], list[dict[str, str]]]:
    static = data.get("static", {})
    paths: list[str] = []
    symbols: list[tuple[str, str]] = []
    evidence: list[dict[str, str]] = []

    if static is None:
        static = {}
    if not isinstance(static, dict):
        err("static 必须是映射")
        static = {}
    unknown = sorted(set(static) - STATIC_KEYS)
    if unknown:
        err(f"static 未知字段 {unknown}（允许：{sorted(STATIC_KEYS)}）")

    paths_raw = static.get("paths", [])
    if not isinstance(paths_raw, list):
        err("static.paths 必须是字符串列表")
        paths_raw = []
    for pos, item in enumerate(paths_raw):
        if not isinstance(item, str) or not item.strip():
            err(f"static.paths[{pos}] 必须是非空字符串")
        elif _unsafe_rel(item):
            err(f"static.paths[{pos}] 必须是仓库内相对路径（不得绝对路径或含 ..）：{item}")
        else:
            paths.append(item)

    symbols_raw = static.get("symbols", [])
    if not isinstance(symbols_raw, list):
        err("static.symbols 必须是列表")
        symbols_raw = []
    for pos, item in enumerate(symbols_raw):
        if not isinstance(item, dict):
            err(f"static.symbols[{pos}] 必须是映射 {{file, pattern}}")
            continue
        unknown_symbol = sorted(set(item) - SYMBOL_KEYS)
        if unknown_symbol:
            err(f"static.symbols[{pos}] 未知字段 {unknown_symbol}")
        file_rel = item.get("file")
        pattern = item.get("pattern")
        if not isinstance(file_rel, str) or not file_rel.strip():
            err(f"static.symbols[{pos}].file 必须是非空字符串")
            continue
        if _unsafe_rel(file_rel):
            err(f"static.symbols[{pos}].file 必须是仓库内相对路径（不得绝对路径或含 ..）：{file_rel}")
            continue
        if not isinstance(pattern, str) or not pattern:
            err(f"static.symbols[{pos}].pattern 必须是非空字符串")
            continue
        try:
            re.compile(pattern)
        except re.error as exc:
            err(f"static.symbols[{pos}].pattern 不是合法正则：{exc}")
            continue
        symbols.append((file_rel, pattern))

    evidence_raw = data.get("evidence", [])
    if not isinstance(evidence_raw, list):
        err("evidence 必须是列表")
        evidence_raw = []
    for pos, item in enumerate(evidence_raw):
        if not isinstance(item, dict):
            err(f"evidence[{pos}] 必须是映射 {{path, note}}")
            continue
        unknown_evidence = sorted(set(item) - EVIDENCE_KEYS)
        if unknown_evidence:
            err(f"evidence[{pos}] 未知字段 {unknown_evidence}")
        path = item.get("path")
        note = item.get("note", "")
        if not isinstance(path, str) or not path.strip():
            err(f"evidence[{pos}].path 必须是非空字符串")
            continue
        if _unsafe_rel(path):
            err(f"evidence[{pos}].path 必须是仓库内相对路径（不得绝对路径或含 ..）：{path}")
            continue
        if note is None:
            note = ""
        if not isinstance(note, str):
            err(f"evidence[{pos}].note 必须是字符串")
            note = ""
        evidence.append({"path": path, "note": note})

    return paths, symbols, evidence


def discover_contract_files(root: Path, page_filter: str | None) -> tuple[list[Path], list[str]]:
    contracts_dir = root / CONTRACTS_REL
    if not contracts_dir.is_dir():
        return [], []
    files = sorted(p for p in contracts_dir.glob("*.yaml") if p.is_file())
    if page_filter:
        wanted = normalize_page_arg(page_filter)
        matches = [p for p in files if p.stem == wanted]
        if not matches:
            return [], [f"找不到页面 {wanted} 的契约：{CONTRACTS_REL.as_posix()}/{wanted}.yaml"]
        return matches, []
    return files, []


def normalize_page_arg(value: str) -> str:
    text = value.strip()
    if re.fullmatch(r"\d{1,2}", text):
        return f"page-{int(text):02d}"
    return text


def load_contracts(root: Path, files: list[Path]) -> tuple[list[Contract], list[str]]:
    contracts: list[Contract] = []
    errors: list[str] = []
    for path in files:
        rel = _rel(root, path)
        try:
            raw = path.read_text(encoding="utf-8")
        except OSError as exc:
            errors.append(f"{rel}：读取失败（{exc}）")
            continue
        try:
            data = yaml.safe_load(raw)
        except yaml.YAMLError as exc:
            detail = " ".join(str(exc).split())
            errors.append(f"{rel}：YAML 解析失败（{detail}）")
            continue
        contract, contract_errors = _validate_contract(rel, path.stem, data, root)
        if contract_errors:
            errors.extend(contract_errors)
        elif contract is not None:
            contracts.append(contract)
    return contracts, errors


# ---------------------------------------------------------------------------
# 页面解析：bash 围栏 + 紧邻注解
# ---------------------------------------------------------------------------
def _marker_before(lines: list[str], fence_line: int) -> str | None:
    """fence_line 是 1-based 的围栏行号；向前找注解（中间最多允许一个空行）。"""
    previous = fence_line - 1
    for _ in range(2):
        if previous < 1:
            return None
        line = lines[previous - 1]
        if not line.strip():
            previous -= 1
            continue
        match = ANNOTATION_LINE_RE.match(line)
        return match.group(1) if match else None
    return None


def parse_page(text: str) -> tuple[list[PageBlock], list[tuple[int, str]], dict[str, list[str]], bool]:
    """返回 (bash 块列表, 页面 verify 注解 [(行号, marker)], verify-out 的 marker→text 围栏内容, 围栏是否未闭合)。"""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")
    blocks: list[PageBlock] = []
    annotations: list[tuple[int, str]] = []
    out_map: dict[str, list[str]] = {}
    pending_out: list[str] = []
    in_fence = False
    fence_info = ""
    fence_line = 0
    buffer: list[str] = []

    for lineno, raw in enumerate(lines, start=1):
        if not in_fence:
            match = ANNOTATION_RE.search(raw)
            if match:
                annotations.append((lineno, match.group(1)))
            out_match = OUT_ANNOTATION_RE.search(raw)
            if out_match:
                pending_out = out_match.group(1).split()
            stripped = raw.strip()
            if stripped.startswith("```"):
                in_fence = True
                fence_info = stripped[3:].strip()
                fence_line = lineno
                buffer = []
            continue
        if raw.strip() == "```":
            in_fence = False
            language = fence_info.split()[0].lower() if fence_info else ""
            if language == "bash":
                blocks.append(
                    PageBlock(
                        marker=_marker_before(lines, fence_line),
                        fence_line=fence_line,
                        cmd="\n".join(buffer),
                    )
                )
            elif language == "text" and pending_out:
                body = "\n".join(buffer)
                for marker in pending_out:
                    out_map.setdefault(marker, []).append(body)
            pending_out = []
            continue
        buffer.append(raw)

    return blocks, annotations, out_map, in_fence


# ---------------------------------------------------------------------------
# T0：契约 ↔ 页面双向同步 + 静态存在性 + 证据存在
# ---------------------------------------------------------------------------
def check_page(root: Path, contract: Contract, strict: bool, fast: bool) -> PageResult:
    result = PageResult(contract=contract)
    page_rel = f"{MANUAL_REL.as_posix()}/{contract.page}.md"
    page_path = root / page_rel
    if not page_path.is_file():
        result.failures.append(Issue("page", f"页面文件不存在：{page_rel}"))
        return result

    try:
        text = page_path.read_text(encoding="utf-8")
    except OSError as exc:
        result.failures.append(Issue("page", f"页面读取失败：{page_rel}（{exc}）"))
        return result

    blocks, annotations, out_map, unclosed = parse_page(text)
    if unclosed:
        result.failures.append(Issue("sync", f"{page_rel}：代码围栏未闭合（缺少结尾的 ```）"))

    adjacent_markers = [block.marker for block in blocks if block.marker]
    contract_markers = {spec.marker for spec in contract.blocks}
    block_mode = contract.coverage == "blocks"

    # 0) static 覆盖的页：不执行、不同步块；页面上不应留 <!-- verify: --> 注解
    if not block_mode and annotations:
        lineno, marker = annotations[0]
        result.failures.append(
            Issue(
                "sync",
                f"{page_rel}：coverage: static 的页不得写 <!-- verify: {marker} --> 注解（第 {lineno} 行）；"
                "只有 coverage: blocks 的页才挂块注解",
            )
        )

    # 1) 覆盖：该页已有契约时，所有 ```bash 块都必须有紧邻注解
    for block in (blocks if block_mode else []):
        if block.marker is None:
            result.failures.append(
                Issue(
                    "sync",
                    f"第 {block.fence_line} 行 ```bash 块缺少紧邻的 <!-- verify: <marker> --> 注解"
                    "（该页已有契约，所有 bash 块都必须覆盖）",
                )
            )

    # 2) 页面注解不得重复
    for marker in sorted({m for m in adjacent_markers if adjacent_markers.count(m) > 1}):
        result.failures.append(Issue("sync", f"页面注解重复：{marker}"))

    # 3) 双向：页面注解必须是契约里的块
    for lineno, marker in (annotations if block_mode else []):
        if marker not in contract_markers:
            result.failures.append(
                Issue("sync", f"第 {lineno} 行注解 {marker} 不在契约块里（页面注解不得有契约不存在的 id）")
            )

    # 4) 注解必须紧邻 bash 围栏（存在但飘在别处）
    for lineno, marker in (annotations if block_mode else []):
        if marker not in adjacent_markers:
            result.failures.append(
                Issue(
                    "sync",
                    f"第 {lineno} 行注解 {marker} 没有紧邻任何 ```bash 块"
                    "（注解要写在围栏前一行，中间最多允许一个空行）",
                )
            )

    # 5) 双向：每个契约块都要在页面找到对应注解与命令
    blocks_by_marker: dict[str, list[PageBlock]] = {}
    for block in blocks:
        if block.marker:
            blocks_by_marker.setdefault(block.marker, []).append(block)

    for spec in contract.blocks:
        found = blocks_by_marker.get(spec.marker, [])
        if not found:
            result.failures.append(
                Issue(
                    "sync",
                    f"契约块 {spec.id}：页面缺少注解 <!-- verify: {spec.marker} -->，或注解没紧邻 ```bash 块",
                )
            )
            continue
        if len(found) > 1:
            result.failures.append(
                Issue("sync", f"契约块 {spec.id}：页面里注解 {spec.marker} 出现了 {len(found)} 次")
            )
            continue
        page_cmd = found[0].cmd
        if normalize_cmd(spec.cmd) != normalize_cmd(page_cmd):
            result.failures.append(
                Issue(
                    "sync",
                    f"契约块 {spec.id}（marker {spec.marker}）：页面 bash 块命令与契约不一致（归一化后比较）",
                    _cmd_diff_detail(spec.cmd, page_cmd),
                )
            )

    # 6) 页面可见关键输出绑定：page_contains 必须锚定到 <!-- verify-out: ... --> 的 text 围栏
    for spec in contract.blocks:
        if not spec.page_contains:
            continue
        contents = out_map.get(spec.marker)
        if not contents:
            result.failures.append(
                Issue(
                    "out",
                    f"契约块 {spec.id}：页面缺少 <!-- verify-out: {spec.marker} --> 注解（或后面没有 text 围栏），"
                    "无法把 page_contains 锚定到页面可见输出",
                )
            )
            continue
        joined = "\n".join(contents)
        for token in spec.page_contains:
            if token not in joined:
                result.failures.append(
                    Issue(
                        "out",
                        f"契约块 {spec.id}：verify-out 围栏里找不到关键输出 {token!r}"
                        "（页面可见输出与契约绑定失败；改输出前先改契约并重跑）",
                    )
                )

    # 7) 静态存在性：paths / symbols
    for path_rel in contract.paths:
        if not (root / path_rel).exists():
            result.failures.append(Issue("static", f"路径不存在：{path_rel}"))
    for file_rel, pattern in contract.symbols:
        file_path = root / file_rel
        if not file_path.is_file():
            result.failures.append(Issue("static", f"符号文件不存在：{file_rel}"))
            continue
        try:
            content = file_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            result.failures.append(Issue("static", f"符号文件读取失败：{file_rel}（{exc}）"))
            continue
        try:
            matched = re.search(pattern, content, re.MULTILINE) is not None
        except re.error as exc:  # 理论上契约校验已挡住
            result.failures.append(Issue("static", f"符号正则非法：{file_rel} /{pattern}/（{exc}）"))
            continue
        if not matched:
            result.failures.append(Issue("static", f"符号未命中：{file_rel} 里找不到正则 /{pattern}/"))

    # 7) 证据存在；T1 额外查过期（mtime 比页面旧）
    page_mtime: float | None = None
    for evidence in contract.evidence:
        evidence_rel = evidence["path"]
        evidence_path = root / evidence_rel
        note = f"（{evidence['note']}）" if evidence.get("note") else ""
        if not evidence_path.is_file():
            result.warnings.append(
                Issue(
                    "evidence",
                    f"证据文件缺失：{evidence_rel}{note}（默认只 warn）",
                )
            )
            continue
        if fast:
            continue
        if page_mtime is None:
            page_mtime = page_path.stat().st_mtime
        try:
            evidence_mtime = evidence_path.stat().st_mtime
        except OSError:
            continue
        if evidence_mtime < page_mtime:
            result.warnings.append(
                Issue(
                    "evidence",
                    f"证据过期：{evidence_rel} 比 {page_rel} 旧（页面改过但证据没重拍）",
                )
            )

    return result


def _cmd_diff_detail(contract_cmd: str, page_cmd: str) -> list[str]:
    expected = normalize_cmd(contract_cmd).split("\n")
    actual = normalize_cmd(page_cmd).split("\n")
    detail: list[str] = []
    for index in range(max(len(expected), len(actual))):
        left = expected[index] if index < len(expected) else "（无）"
        right = actual[index] if index < len(actual) else "（无）"
        if left != right:
            detail.append(f"契约第 {index + 1} 行：{left}")
            detail.append(f"页面第 {index + 1} 行：{right}")
            break
    if len(expected) != len(actual):
        detail.append(f"命令行数：契约 {len(expected)} 行 / 页面 {len(actual)} 行")
    return detail


# ---------------------------------------------------------------------------
# T1：执行 offline 块
# ---------------------------------------------------------------------------
def _run_shell(cmd: str, root: Path, timeout_sec: float) -> tuple[int | None, str, str]:
    """跑一条契约命令；超时返回 (None, 已捕获输出, err 标记)。"""
    process = subprocess.Popen(  # noqa: S602 - 契约命令来自人工评审过的 YAML
        cmd,
        shell=True,
        cwd=str(root),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        start_new_session=True,
    )
    try:
        stdout, stderr = process.communicate(timeout=timeout_sec)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(os.getpgid(process.pid), signal.SIGKILL)
        except ProcessLookupError:
            process.kill()
        stdout, stderr = process.communicate()
        return None, stdout or "", stderr or ""
    return process.returncode, stdout or "", stderr or ""


def execute_offline_blocks(root: Path, result: PageResult) -> None:
    page_rel = f"{MANUAL_REL.as_posix()}/{result.contract.page}.md"
    for spec in result.contract.blocks:
        if spec.kind != "offline" or spec.expect is None:
            continue
        execution = Execution(block_id=spec.id)
        started = time.monotonic()
        exit_code, stdout, stderr = _run_shell(spec.cmd, root, spec.timeout_sec)
        execution.duration_sec = time.monotonic() - started
        execution.exit_code = exit_code
        combined = stdout
        if stdout and stderr:
            combined += "\n"
        combined += stderr

        if exit_code is None:
            execution.failures.append(f"超时（{spec.timeout_sec:g} 秒）")
        else:
            if exit_code != spec.expect["exit"]:
                execution.failures.append(f"exit 期望 {spec.expect['exit']}，实际 {exit_code}")
            for needle in spec.expect["contains"]:
                if needle not in combined:
                    execution.failures.append(f'contains 未命中："{needle}"')
            for pattern in spec.expect["regex"]:
                try:
                    matched = re.search(pattern, combined, re.MULTILINE) is not None
                except re.error:  # 契约校验已挡住，这里只防御
                    matched = False
                if not matched:
                    execution.failures.append(f"regex 未命中：/{pattern}/")
            for token in spec.page_contains:
                if token not in combined:
                    execution.failures.append(f'页面可见关键输出与真实输出不一致："{token}" 未在真实输出中出现')

        if execution.failures:
            execution.status = "fail"
            execution.output_tail = _tail_lines(sanitize(combined, root))
        result.executions.append(execution)


# ---------------------------------------------------------------------------
# 输出渲染
# ---------------------------------------------------------------------------
def _emit_contract_line(result: PageResult, strict: bool) -> str:
    ok = page_ok(result, strict)
    tag = "  [static]" if result.contract.coverage == "static" else ""
    if ok:
        return f"  {result.contract.page}  PASS{tag}"
    failures = len(result.failures) + sum(len(ex.failures) for ex in result.executions)
    if strict:
        failures += len(result.warnings)
    return f"  {result.contract.page}  FAIL({failures}){tag}"


def render_human(
    results: list[PageResult],
    *,
    fast: bool,
    strict: bool,
    duration: float,
    contract_dir_rel: str,
    config_errors: list[str],
    no_contracts_message: str | None = None,
) -> str:
    mode = "T0" if fast else "T1"
    lines: list[str] = []
    if no_contracts_message is not None:
        lines.append(no_contracts_message)
        lines.append("")
        lines.append("T0 PASS（无契约，跳过验收）" if fast else "T1 PASS（无契约，跳过验收）")
        return "\n".join(lines)

    if config_errors:
        lines.append(f"== 契约错误（{mode} 未执行，退出码 2）==")
        for item in config_errors:
            lines.append(f"  ✗ {item}")
        lines.append(f"契约错误 {len(config_errors)} 处：先修契约再跑验收")
        return "\n".join(lines)

    total_offline = sum(1 for r in results for b in r.contract.blocks if b.kind == "offline")
    total_manual = sum(1 for r in results for b in r.contract.blocks if b.kind == "manual")
    if fast:
        lines.append("== T0 契约跟随性验收（--fast：解析 + 双向同步 + 静态存在性，不执行命令）==")
    else:
        lines.append(f"== T1 契约跟随性验收（T0 + 按顺序执行 {total_offline} 个 offline 块，不执行 manual 块）==")
    lines.append(f"契约目录：{contract_dir_rel}（{len(results)} 个）")

    exec_failures = 0
    warning_count = 0
    failure_count = 0
    for result in results:
        lines.append(_emit_contract_line(result, strict))
        for issue in result.failures:
            lines.append(f"    ✗ [{issue.check}] {issue.message}")
            for item in issue.detail:
                lines.append(f"        {item}")
        for issue in result.warnings:
            warning_count += 1
            label = "（--strict 下为失败）" if strict else ""
            lines.append(f"    WARN [{issue.check}] {issue.message}{label}")
        failure_count += len(result.failures)
        for execution in result.executions:
            lines.append(f"    [T1] {result.contract.page} / {execution.block_id} ... {execution.status.upper()} ({_fmt_seconds(execution.duration_sec)})")
            if execution.failures:
                exec_failures += 1
                failure_count += 1
                for message in execution.failures:
                    lines.append(f"      断言失败：{message}")
                if execution.output_tail:
                    lines.append(f"--- 真实输出（截断到 {OUTPUT_TAIL_LINES} 行）---")
                    for out_line in execution.output_tail:
                        lines.append(out_line)

    failed_pages = sum(1 for r in results if not page_ok(r, strict))
    passed_pages = len(results) - failed_pages
    if strict:
        failure_count += warning_count
    exec_total = sum(len(r.executions) for r in results)
    lines.append(
        f"页：{passed_pages}/{len(results)} 通过；块：{total_offline + total_manual}"
        f"（offline {total_offline} / manual {total_manual}）"
    )
    static_pages = sum(1 for r in results if r.contract.coverage == "static")
    if static_pages:
        lines.append(f"静态页：{static_pages}（coverage: static，只做 T0 路径/符号检查，无 offline 块）")
    if not fast and exec_total:
        lines.append(f"执行：{exec_total - exec_failures}/{exec_total} 个 offline 块通过")
    if warning_count:
        lines.append(f"警告：{warning_count}（--strict 下升级为失败）")
    ok = failed_pages == 0
    if ok:
        lines.append(f"{mode} PASS（耗时 {duration:.2f}s）")
    else:
        lines.append(f"{mode} FAIL（耗时 {duration:.2f}s；失败项 {failure_count}，失败页 {failed_pages}）")
    return "\n".join(lines)


def build_json_payload(
    results: list[PageResult],
    *,
    fast: bool,
    strict: bool,
    duration: float,
    exit_code: int,
    config_errors: list[str] | None = None,
    no_contracts: bool = False,
    contract_dir_rel: str = CONTRACTS_REL.as_posix(),
) -> dict[str, Any]:
    mode = "T0" if fast else "T1"
    if config_errors is not None:
        return {"mode": mode, "strict": strict, "contract_errors": config_errors, "exit_code": exit_code}
    if no_contracts:
        return {
            "mode": mode,
            "strict": strict,
            "no_contracts": True,
            "message": "无契约：tutorial/verify/contracts/ 不存在或为空",
            "contract_dir": contract_dir_rel,
            "exit_code": exit_code,
        }
    contracts_payload: list[dict[str, Any]] = []
    warning_count = 0
    executed = 0
    exec_failures = 0
    for result in results:
        blocks_total = len(result.contract.blocks)
        blocks_offline = sum(1 for b in result.contract.blocks if b.kind == "offline")
        blocks_manual = sum(1 for b in result.contract.blocks if b.kind == "manual")
        warning_count += len(result.warnings)
        executed += len(result.executions)
        exec_failures += sum(1 for ex in result.executions if ex.status != "pass")
        contracts_payload.append(
            {
                "page": result.contract.page,
                "title": result.contract.title,
                "path": result.contract.path_rel,
                "coverage": result.contract.coverage,
                "status": "pass" if page_ok(result, strict) else "fail",
                "blocks": {"total": blocks_total, "offline": blocks_offline, "manual": blocks_manual},
                "failures": [{"check": issue.check, "message": issue.message, "detail": issue.detail} for issue in result.failures],
                "warnings": [{"check": issue.check, "message": issue.message} for issue in result.warnings],
                "executions": [
                    {
                        "id": execution.block_id,
                        "status": execution.status,
                        "duration_sec": round(execution.duration_sec, 3),
                        "exit_code": execution.exit_code,
                        "failures": execution.failures,
                    }
                    for execution in result.executions
                ],
            }
        )
    pages = len(results)
    passed = sum(1 for result in results if page_ok(result, strict))
    blocks = sum(len(result.contract.blocks) for result in results)
    offline = sum(1 for result in results for b in result.contract.blocks if b.kind == "offline")
    manual = sum(1 for result in results for b in result.contract.blocks if b.kind == "manual")
    static_pages = sum(1 for result in results if result.contract.coverage == "static")
    return {
        "mode": mode,
        "strict": strict,
        "duration_sec": round(duration, 3),
        "contract_dir": contract_dir_rel,
        "contracts": contracts_payload,
        "summary": {
            "pages": pages,
            "passed": passed,
            "failed": pages - passed,
            "blocks": blocks,
            "offline": offline,
            "manual": manual,
            "static_pages": static_pages,
            "executed": executed,
            "execution_failures": exec_failures,
            "warnings": warning_count,
        },
        "exit_code": exit_code,
    }


def list_contracts_human(contracts: list[Contract], contract_dir_rel: str) -> str:
    lines = [f"契约（{len(contracts)} 个，目录 {contract_dir_rel}）"]
    for contract in contracts:
        offline = sum(1 for b in contract.blocks if b.kind == "offline")
        manual = sum(1 for b in contract.blocks if b.kind == "manual")
        title = contract.title or "（无 title）"
        if contract.coverage == "static":
            lines.append(
                f"  {contract.page}  {title}  [static]  static.paths={len(contract.paths)}"
                f"  static.symbols={len(contract.symbols)}  evidence={len(contract.evidence)}"
            )
            continue
        lines.append(
            f"  {contract.page}  {title}  blocks={len(contract.blocks)}"
            f"（offline={offline} / manual={manual}）  static.paths={len(contract.paths)}"
            f"  static.symbols={len(contract.symbols)}  evidence={len(contract.evidence)}"
        )
        for spec in contract.blocks:
            reason = f"  # {spec.reason}" if spec.reason else ""
            note = f"  note: {spec.note}" if getattr(spec, "note", "") else ""
            bound = f"  page_contains={len(spec.page_contains)}" if spec.page_contains else ""
            lines.append(f"    - {spec.id}  {spec.kind}{reason}{bound}{note}")
    return "\n".join(lines)


def list_contracts_json(contracts: list[Contract], contract_dir_rel: str) -> dict[str, Any]:
    return {
        "contract_dir": contract_dir_rel,
        "contracts": [
            {
                "page": contract.page,
                "title": contract.title,
                "path": contract.path_rel,
                "coverage": contract.coverage,
                "blocks": [
                    {"id": spec.id, "marker": spec.marker, "kind": spec.kind, "reason": spec.reason}
                    for spec in contract.blocks
                ],
            }
            for contract in contracts
        ],
        "exit_code": 0,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="verify.py",
        description="教材可跟随性验收线：页面 ↔ 契约双向同步 + 静态存在性 + 可选执行 offline 命令",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例：\n"
            "  python3 toolbox/scripts/verify.py --fast\n"
            "  python3 toolbox/scripts/verify.py\n"
            "  python3 toolbox/scripts/verify.py --strict --page page-17\n"
            "  python3 toolbox/scripts/verify.py --list\n"
            "退出码：0 通过 / 1 验收失败 / 2 契约或配置错误"
        ),
    )
    parser.add_argument("--fast", action="store_true", help="T0：只做静态验收，不执行命令（pre-commit 用）")
    parser.add_argument("--strict", action="store_true", help="证据缺失（T0）/ 过期（T1）从警告升级为失败")
    parser.add_argument("--page", metavar="page-XX", help="只验收某一页（也接受 17）")
    parser.add_argument("--list", action="store_true", dest="list_only", help="列出契约，不做验收")
    parser.add_argument("--json", action="store_true", dest="json_out", help="输出机器可读 JSON（stdout 只有 JSON）")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None, root: Path | None = None) -> int:
    args = parse_args(argv)
    repo = Path(root).resolve() if root is not None else ROOT
    contracts_rel = CONTRACTS_REL.as_posix()
    started = time.monotonic()

    files, discovery_errors = discover_contract_files(repo, args.page)
    if discovery_errors:
        payload = build_json_payload([], fast=args.fast, strict=args.strict, duration=0.0, exit_code=2, config_errors=discovery_errors)
        _emit_output(args.json_out, render_human([], fast=args.fast, strict=args.strict, duration=0.0, contract_dir_rel=contracts_rel, config_errors=discovery_errors), payload)
        return 2

    if not files:
        message = "无契约：tutorial/verify/contracts/ 不存在或为空，跳过验收。"
        payload = build_json_payload(
            [], fast=args.fast, strict=args.strict, duration=time.monotonic() - started,
            exit_code=0, no_contracts=True, contract_dir_rel=contracts_rel,
        )
        _emit_output(args.json_out, render_human([], fast=args.fast, strict=args.strict, duration=0.0, contract_dir_rel=contracts_rel, config_errors=[], no_contracts_message=message), payload)
        return 0

    contracts, config_errors = load_contracts(repo, files)
    if config_errors:
        payload = build_json_payload([], fast=args.fast, strict=args.strict, duration=0.0, exit_code=2, config_errors=config_errors)
        _emit_output(args.json_out, render_human([], fast=args.fast, strict=args.strict, duration=0.0, contract_dir_rel=contracts_rel, config_errors=config_errors), payload)
        return 2

    if args.list_only:
        if args.json_out:
            print(json.dumps(list_contracts_json(contracts, contracts_rel), ensure_ascii=False, indent=2))
        else:
            print(list_contracts_human(contracts, contracts_rel))
        return 0

    results = [check_page(repo, contract, strict=args.strict, fast=args.fast) for contract in contracts]
    if not args.fast:
        for result in results:
            execute_offline_blocks(repo, result)

    duration = time.monotonic() - started
    failed_pages = sum(1 for result in results if not page_ok(result, args.strict))
    exit_code = 0 if failed_pages == 0 else 1
    payload = build_json_payload(
        results,
        fast=args.fast,
        strict=args.strict,
        duration=duration,
        exit_code=exit_code,
        contract_dir_rel=contracts_rel,
    )
    human = render_human(
        results,
        fast=args.fast,
        strict=args.strict,
        duration=duration,
        contract_dir_rel=contracts_rel,
        config_errors=[],
    )
    _emit_output(args.json_out, human, payload)
    return exit_code


def _emit_output(json_out: bool, human: str, payload: dict[str, Any]) -> None:
    if json_out:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(human)


if __name__ == "__main__":
    raise SystemExit(main())
