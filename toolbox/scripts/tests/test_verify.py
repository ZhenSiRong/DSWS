#!/usr/bin/env python3
"""test_verify.py —— scripts/verify.py 的单元测试（离线、临时沙箱目录）

覆盖：
  * 命令归一化（空白 / 空行 / CRLF，等价与不等价）
  * marker 缺失、注解不在契约、契约块不在页面（双向同步）
  * 命令不一致（任意一边改动）
  * 静态路径缺失 / 符号未命中 / 绝对路径拒绝
  * expect 解析与字段校验（退出码 2）
  * T1 真执行 offline 块：通过 / 断言失败 / exit 不符 / 超时
  * manual 块只同步不执行
  * 证据缺失（T0 warn，strict fail）与证据过期（T1 warn，strict fail）
  * --json / --list / --page / 无契约退出 0

用法：
    python3 scripts/tests/test_verify.py
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
VERIFY_PATH = REPO_ROOT / "toolbox" / "scripts" / "verify.py"


def _load_verify_module():
    spec = importlib.util.spec_from_file_location("verify_under_test", VERIFY_PATH)
    assert spec is not None and spec.loader is not None, "找不到 scripts/verify.py"
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


verify = _load_verify_module()


def echo_contract(
    *,
    cmd: str = "echo hello",
    contains: str = '["hello"]',
    exit_code: int = 0,
    kind: str = "offline",
    reason: str | None = None,
    with_expect: bool = True,
    page_contains: list[str] | None = None,
    extra: str = "",
) -> str:
    """最小合法契约：一个块，marker 固定 p17-echo。"""
    lines = [
        "page: page-17",
        "blocks:",
        "  - id: p17-echo",
        "    marker: p17-echo",
        f"    kind: {kind}",
        "    cmd: |",
    ]
    for cmd_line in cmd.split("\n"):
        lines.append(f"      {cmd_line}")
    if kind == "offline" and with_expect:
        lines.append("    expect:")
        lines.append(f"      exit: {exit_code}")
        lines.append(f"      contains: {contains}")
    if page_contains is not None:
        lines.append("    page_contains: [" + ", ".join(f'\"{t}\"' if False else repr(t) for t in page_contains) + "]")
    if reason is not None:
        lines.append(f"    reason: {reason}")
    return "\n".join(lines) + "\n" + extra


class VerifyCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="verify-test-")
        self.root = Path(self._tmp.name)
        (self.root / "toolbox" / "verify" / "contracts").mkdir(parents=True)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    # ---- 写 fixture -----------------------------------------------------
    def write(self, rel: str, text: str) -> Path:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def make_page(self, body_lines: list[str], page: str = "page-17") -> Path:
        lines = ["# 第 17 页 · 测试页", "", "## 动手", ""]
        lines.extend(body_lines)
        lines.append("")
        return self.write(f"tutorial/{page}.md", "\n".join(lines))

    def make_block(self, marker: str | None, cmd_lines: list[str], *, blank_line: bool = False) -> list[str]:
        lines = [] if marker is None else [f"<!-- verify: {marker} -->"]
        if blank_line:
            lines.append("")
        lines.extend(["```bash", *cmd_lines, "```"])
        return lines

    def make_out_fence(self, markers: list[str], text_lines: list[str]) -> list[str]:
        return [f"<!-- verify-out: {' '.join(markers)} -->", "```text", *text_lines, "```"]

    def make_contract(self, text: str, page: str = "page-17") -> Path:
        return self.write(f"toolbox/verify/contracts/{page}.yaml", text)

    def happy_fixture(self, *, cmd: str = "echo hello") -> None:
        self.make_page(self.make_block("p17-echo", [cmd]))
        self.make_contract(echo_contract(cmd=cmd))

    def run_verify(self, *args: str) -> tuple[int, str, str]:
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = verify.main(list(args), root=self.root)
        return code, stdout.getvalue(), stderr.getvalue()

    # ---- 归一化 ---------------------------------------------------------
    def test_normalize_cmd(self) -> None:
        self.assertEqual(verify.normalize_cmd("  echo   hello  \n\n"), "echo hello")
        self.assertEqual(verify.normalize_cmd("a\r\nb"), "a\nb")
        self.assertEqual(verify.normalize_cmd("a\n\nb"), "a\nb")
        self.assertEqual(verify.normalize_cmd("a\n \t b"), "a\nb")
        # 行序保留：两行命令不能压成一行
        self.assertNotEqual(verify.normalize_cmd("a\nb"), verify.normalize_cmd("a b"))
        self.assertNotEqual(verify.normalize_cmd("echo hello"), verify.normalize_cmd("echo bye"))

    def test_whitespace_normalized_block_matches(self) -> None:
        # 注解与围栏之间允许一个空行；页面块的多余缩进/空格归一化后与契约相等
        self.make_page(self.make_block("p17-echo", ["  echo    hello   "], blank_line=True))
        self.make_contract(echo_contract())
        code, out, _ = self.run_verify("--fast")
        self.assertEqual(code, 0, out)

    # ---- 双向同步 -------------------------------------------------------
    def test_marker_missing_fails(self) -> None:
        self.make_page(self.make_block(None, ["echo hello"]))
        self.make_contract(echo_contract())
        code, out, _ = self.run_verify("--fast")
        self.assertEqual(code, 1)
        self.assertIn("缺少紧邻", out)
        self.assertIn("page-17  FAIL", out)

    def test_annotation_not_in_contract_fails(self) -> None:
        self.make_page(self.make_block("p17-extra", ["echo hello"]))
        self.make_contract(echo_contract())
        code, out, _ = self.run_verify("--fast")
        self.assertEqual(code, 1)
        self.assertIn("不在契约块里", out)

    def test_contract_block_missing_on_page_fails(self) -> None:
        self.make_page(self.make_block("p17-echo", ["echo hello"]))
        extra_block = (
            "  - id: p17-missing\n"
            "    marker: p17-missing\n"
            "    kind: manual\n"
            "    reason: 测试：只同步不执行\n"
            "    cmd: |\n"
            "      echo missing\n"
        )
        self.make_contract(echo_contract(extra=extra_block))
        code, out, _ = self.run_verify("--fast")
        self.assertEqual(code, 1)
        self.assertIn("页面缺少注解", out)

    def test_cmd_mismatch_fails(self) -> None:
        self.make_page(self.make_block("p17-echo", ["echo bye"]))
        self.make_contract(echo_contract(cmd="echo hello"))
        code, out, _ = self.run_verify("--fast")
        self.assertEqual(code, 1)
        self.assertIn("命令与契约不一致", out)
        self.assertIn("契约第 1 行：echo hello", out)
        self.assertIn("页面第 1 行：echo bye", out)

    def test_annotation_duplicate_fails(self) -> None:
        self.make_page(
            self.make_block("p17-echo", ["echo hello"]) + self.make_block("p17-echo", ["echo hello"])
        )
        self.make_contract(echo_contract())
        code, out, _ = self.run_verify("--fast")
        self.assertEqual(code, 1)
        self.assertIn("页面注解重复", out)

    def test_unclosed_fence_fails(self) -> None:
        self.make_page(["<!-- verify: p17-echo -->", "```bash", "echo hello"])
        self.make_contract(echo_contract())
        code, out, _ = self.run_verify("--fast")
        self.assertEqual(code, 1)
        self.assertIn("代码围栏未闭合", out)

    # ---- 静态存在性 -----------------------------------------------------
    def test_static_path_missing_fails(self) -> None:
        self.happy_fixture()
        self.make_contract(echo_contract(extra="\nstatic:\n  paths:\n    - backend/not-there.py\n"))
        code, out, _ = self.run_verify("--fast")
        self.assertEqual(code, 1)
        self.assertIn("路径不存在", out)

    def test_static_symbol_hit_and_miss(self) -> None:
        self.write("backend/app/correct.py", "def propose_correction():\n    pass\n")
        self.happy_fixture()
        hit = (
            "\nstatic:\n  symbols:\n"
            '    - {file: backend/app/correct.py, pattern: "def propose_correction"}\n'
        )
        self.make_contract(echo_contract(extra=hit))
        code, out, _ = self.run_verify("--fast")
        self.assertEqual(code, 0, out)

        miss = (
            "\nstatic:\n  symbols:\n"
            '    - {file: backend/app/correct.py, pattern: "def missing_symbol"}\n'
        )
        self.make_contract(echo_contract(extra=miss))
        code, out, _ = self.run_verify("--fast")
        self.assertEqual(code, 1)
        self.assertIn("符号未命中", out)

    def test_path_traversal_rejected(self) -> None:
        self.happy_fixture()
        self.make_contract(echo_contract(extra="\nstatic:\n  paths:\n    - ../outside.txt\n"))
        code, out, _ = self.run_verify("--fast")
        self.assertEqual(code, 2)
        self.assertIn("仓库内相对路径", out)

    def test_page_contains_missing_verify_out_fails(self) -> None:
        # 页面正文里有 hello，但没有 verify-out 围栏 → T0 必须红（不允许全页任意位置命中）
        self.make_page(["hello"] + self.make_block("p17-echo", ["echo hello"]))
        self.make_contract(echo_contract(page_contains=["hello"]))
        code, out, _ = self.run_verify("--fast")
        self.assertEqual(code, 1)
        self.assertIn("verify-out", out)

    def test_page_contains_anchored_to_out_fence(self) -> None:
        self.make_page(self.make_out_fence(["p17-echo"], ["hello"]) + self.make_block("p17-echo", ["echo hello"]))
        self.make_contract(echo_contract(page_contains=["hello"]))
        code, out, _ = self.run_verify("--fast")
        self.assertEqual(code, 0, out)

    def test_page_contains_out_fence_changed_fails(self) -> None:
        # 关键输出只在别处出现不算；verify-out 围栏里没有就红
        self.make_page(
            ["hello (正文别处)"] + self.make_out_fence(["p17-echo"], ["bye"]) + self.make_block("p17-echo", ["echo hello"])
        )
        self.make_contract(echo_contract(page_contains=["hello"]))
        code, out, _ = self.run_verify("--fast")
        self.assertEqual(code, 1)
        self.assertIn("verify-out", out)

    def test_page_contains_output_mismatch_fails_t1(self) -> None:
        # verify-out 围栏写 bye（T0 通过），但命令只输出 hello → T1 必须抓到
        self.make_page(self.make_out_fence(["p17-echo"], ["bye"]) + self.make_block("p17-echo", ["echo hello"]))
        self.make_contract(echo_contract(page_contains=["bye"]))
        code, out, _ = self.run_verify("--fast")
        self.assertEqual(code, 0, out)
        code, out, _ = self.run_verify()
        self.assertEqual(code, 1)
        self.assertIn("页面可见关键输出与真实输出不一致", out)

    def test_expect_regex_multiline(self) -> None:
        self.make_page(self.make_block("p17-echo", ["printf 'hello\\n'"]))
        self.make_contract(echo_contract(cmd="printf 'hello\\n'", extra="\n"))
        self.make_contract(
            "page: page-17\nblocks:\n  - id: p17-echo\n    marker: p17-echo\n    kind: offline\n"
            "    cmd: |\n      printf 'hello\\n'\n    expect:\n      exit: 0\n"
            "      contains: []\n      regex: ['^hello$']\n"
        )
        code, out, _ = self.run_verify()
        self.assertEqual(code, 0, out)

    def test_absolute_path_rejected(self) -> None:
        self.happy_fixture()
        self.make_contract(echo_contract(extra="\nstatic:\n  paths:\n    - /tmp/not-allowed\n"))
        code, out, _ = self.run_verify("--fast")
        self.assertEqual(code, 2)
        self.assertIn("仓库内相对路径", out)

    # ---- expect / 字段校验（退出码 2）-----------------------------------
    def test_expect_validation_errors(self) -> None:
        cases = {
            "缺 expect": echo_contract(with_expect=False),
            "kind 非法": echo_contract(kind="sometimes"),
            "manual 缺 reason": echo_contract(kind="manual"),
            "坏 YAML": "page: page-17\nblocks: [\n",
            "未知字段": echo_contract(extra="\nunknown_field: 1\n"),
        }
        # manual 块带 expect（不执行，不应声明）
        cases["manual 带 expect"] = (
            "page: page-17\n"
            "blocks:\n"
            "  - id: p17-echo\n"
            "    marker: p17-echo\n"
            "    kind: manual\n"
            "    reason: 测试\n"
            "    cmd: |\n"
            "      echo hello\n"
            "    expect:\n"
            "      exit: 0\n"
            '      contains: ["hello"]\n'
        )
        # contains 类型错：expect.contains 是字符串而不是列表
        cases["contains 类型错"] = (
            "page: page-17\n"
            "blocks:\n"
            "  - id: p17-echo\n"
            "    marker: p17-echo\n"
            "    kind: offline\n"
            "    cmd: |\n"
            "      echo hello\n"
            "    expect:\n"
            "      exit: 0\n"
            '      contains: "hello"\n'
        )
        for name, contract_text in cases.items():
            with self.subTest(name=name):
                self.make_page(self.make_block("p17-echo", ["echo hello"]))
                self.make_contract(contract_text)
                code, out, _ = self.run_verify("--fast")
                self.assertEqual(code, 2, f"{name} 应为配置错误：{out}")

    def test_invalid_regex_in_expect_is_config_error(self) -> None:
        self.make_page(self.make_block("p17-echo", ["echo hello"]))
        contract_text = (
            "page: page-17\n"
            "blocks:\n"
            "  - id: p17-echo\n"
            "    marker: p17-echo\n"
            "    kind: offline\n"
            "    cmd: |\n"
            "      echo hello\n"
            "    expect:\n"
            "      exit: 0\n"
            '      contains: ["hello"]\n'
            '      regex: ["("]\n'
        )
        self.make_contract(contract_text)
        code, out, _ = self.run_verify("--fast")
        self.assertEqual(code, 2)
        self.assertIn("不是合法正则", out)

    def test_page_filter_no_match_is_config_error(self) -> None:
        self.happy_fixture()
        code, out, _ = self.run_verify("--fast", "--page", "page-18")
        self.assertEqual(code, 2)
        self.assertIn("找不到页面", out)

    def test_page_filter_accepts_number(self) -> None:
        self.happy_fixture()
        code, out, _ = self.run_verify("--fast", "--page", "17")
        self.assertEqual(code, 0, out)

    # ---- T1 执行 --------------------------------------------------------
    def test_t1_executes_offline_and_passes(self) -> None:
        self.make_page(self.make_block("p17-echo", ["printf '14 passed\\n'"]))
        self.make_contract(echo_contract(cmd="printf '14 passed\\n'", contains='["14 passed"]'))
        code, out, _ = self.run_verify()
        self.assertEqual(code, 0, out)
        self.assertIn("[T1] page-17 / p17-echo ... PASS", out)

    def test_t1_contains_mismatch_fails_with_real_output(self) -> None:
        self.make_page(self.make_block("p17-echo", ["printf '14 passed\\n'"]))
        self.make_contract(echo_contract(cmd="printf '14 passed\\n'", contains='["99 passed"]'))
        code, out, _ = self.run_verify()
        self.assertEqual(code, 1)
        self.assertIn("contains 未命中", out)
        self.assertIn("真实输出（截断到 60 行）", out)
        self.assertIn("14 passed", out)

    def test_t1_exit_mismatch_fails(self) -> None:
        self.make_page(self.make_block("p17-echo", ["exit 3"]))
        self.make_contract(echo_contract(cmd="exit 3", contains="[]"))
        code, out, _ = self.run_verify()
        self.assertEqual(code, 1)
        self.assertIn("exit 期望 0，实际 3", out)

    def test_t1_timeout_fails(self) -> None:
        slow = (
            "page: page-17\n"
            "blocks:\n"
            "  - id: p17-echo\n"
            "    marker: p17-echo\n"
            "    kind: offline\n"
            "    cmd: |\n"
            "      sleep 2\n"
            "    expect:\n"
            "      exit: 0\n"
            '      contains: []\n'
            "    timeout_sec: 0.2\n"
        )
        self.make_page(self.make_block("p17-echo", ["sleep 2"]))
        self.make_contract(slow)
        started = time.monotonic()
        code, out, _ = self.run_verify()
        elapsed = time.monotonic() - started
        self.assertEqual(code, 1)
        self.assertIn("超时", out)
        self.assertLess(elapsed, 2.0, "超时后应立刻结束，不应等命令自己跑完")

    def test_manual_block_not_executed(self) -> None:
        self.make_page(self.make_block("p17-echo", ["touch should-not-exist"]))
        self.make_contract(echo_contract(cmd="touch should-not-exist", kind="manual", reason="测试：只同步不执行"))
        code, out, _ = self.run_verify()
        self.assertEqual(code, 0, out)
        self.assertFalse((self.root / "should-not-exist").exists(), "manual 块不应该被执行")

    # ---- 证据 -----------------------------------------------------------
    def test_evidence_missing_warn_then_strict_fail(self) -> None:
        self.happy_fixture()
        self.make_contract(
            echo_contract(extra='\nevidence:\n  - {path: tutorial/images/missing.png, note: "截图"}\n')
        )
        code, out, _ = self.run_verify("--fast")
        self.assertEqual(code, 0, out)
        self.assertIn("WARN", out)
        self.assertIn("证据文件缺失", out)

        code, out, _ = self.run_verify("--fast", "--strict")
        self.assertEqual(code, 1, out)
        self.assertIn("证据文件缺失", out)

    def test_evidence_stale_t1_warn_then_strict_fail(self) -> None:
        self.happy_fixture()
        self.write("tutorial/images/shot.png", "fake-png")
        self.make_contract(echo_contract(extra='\nevidence:\n  - {path: tutorial/images/shot.png, note: "截图"}\n'))
        now = time.time()
        os.utime(self.root / "tutorial/images/shot.png", (now - 1000, now - 1000))
        os.utime(self.root / "tutorial/page-17.md", (now, now))

        # T0（--fast）不查过期（按约定只在 T1 查）
        code, out, _ = self.run_verify("--fast")
        self.assertEqual(code, 0, out)
        self.assertNotIn("证据过期", out)

        code, out, _ = self.run_verify()
        self.assertEqual(code, 0, out)
        self.assertIn("证据过期", out)
        code, out, _ = self.run_verify("--strict")
        self.assertEqual(code, 1, out)

    # ---- CLI 形态 -------------------------------------------------------
    def test_no_contracts_exit_0(self) -> None:
        code, out, _ = self.run_verify("--fast")
        self.assertEqual(code, 0, out)
        self.assertIn("无契约", out)
        self.assertIn("PASS", out)

    def test_json_output(self) -> None:
        self.happy_fixture()
        code, out, _ = self.run_verify("--fast", "--json")
        self.assertEqual(code, 0, out)
        payload = json.loads(out)
        self.assertEqual(payload["mode"], "T0")
        self.assertEqual(payload["exit_code"], 0)
        self.assertEqual(payload["summary"]["pages"], 1)
        self.assertEqual(payload["summary"]["offline"], 1)
        self.assertEqual(payload["contracts"][0]["status"], "pass")

    def test_json_on_config_error(self) -> None:
        self.make_page(self.make_block("p17-echo", ["echo hello"]))
        self.make_contract("page: page-17\nblocks: [\n")
        code, out, _ = self.run_verify("--fast", "--json")
        self.assertEqual(code, 2)
        payload = json.loads(out)
        self.assertEqual(payload["exit_code"], 2)
        self.assertTrue(payload["contract_errors"])

    def test_list_contracts(self) -> None:
        self.happy_fixture()
        code, out, _ = self.run_verify("--list")
        self.assertEqual(code, 0, out)
        self.assertIn("page-17", out)
        self.assertIn("p17-echo", out)

        code, out, _ = self.run_verify("--list", "--json")
        self.assertEqual(code, 0, out)
        payload = json.loads(out)
        self.assertEqual(payload["contracts"][0]["page"], "page-17")
        self.assertEqual(payload["contracts"][0]["blocks"][0]["kind"], "offline")

    def test_output_has_no_absolute_path(self) -> None:
        self.happy_fixture()
        code, out, _ = self.run_verify("--fast")
        self.assertEqual(code, 0, out)
        self.assertNotIn(str(self.root), out)

    # ---- coverage: static（整栈页只挂静态断言，不执行块）-------------------
    def static_contract(self, *, paths: str = '["fixtures/dw.sql"]', symbols: str = "") -> str:
        text = (
            "page: page-17\n"
            "title: 第 17 页 · 测试页\n"
            "coverage: static\n"
            "static:\n"
            f"  paths: {paths}\n"
        )
        if symbols:
            text += "  symbols:\n" + symbols
        return text

    def test_static_coverage_passes_without_blocks(self) -> None:
        self.write("fixtures/dw.sql", "CREATE TABLE t (id INT);\n")
        self.make_page(["整栈页：块不挂注解也不执行", *self.make_block(None, ["docker run --rm mysql"])])
        self.make_contract(self.static_contract())
        code, out, _ = self.run_verify("--fast")
        self.assertEqual(code, 0, out)
        self.assertIn("[static]", out)
        code, out, _ = self.run_verify()
        self.assertEqual(code, 0, out)
        self.assertIn("静态页：1", out)

    def test_static_coverage_allows_missing_blocks_key(self) -> None:
        self.write("fixtures/dw.sql", "SELECT 1;\n")
        self.make_page(self.make_block(None, ["docker compose up -d"]))
        self.make_contract(self.static_contract())
        code, _, _ = self.run_verify("--fast")
        self.assertEqual(code, 0)

    def test_static_coverage_rejects_blocks(self) -> None:
        self.write("fixtures/dw.sql", "SELECT 1;\n")
        self.make_page(self.make_block("p17-echo", ["echo hello"]))
        contract = self.static_contract() + (
            "blocks:\n"
            "  - id: p17-echo\n"
            "    marker: p17-echo\n"
            "    kind: offline\n"
            "    cmd: echo hello\n"
            "    expect:\n"
            "      exit: 0\n"
            "      contains: [hello]\n"
        )
        self.make_contract(contract)
        code, out, _ = self.run_verify("--fast")
        self.assertEqual(code, 2, out)
        self.assertIn("coverage: static 时 blocks 必须省略或为空", out)

    def test_static_coverage_requires_paths_or_symbols(self) -> None:
        self.make_page(self.make_block(None, ["docker run --rm mysql"]))
        self.make_contract("page: page-17\ntitle: 第 17 页\ncoverage: static\n")
        code, out, _ = self.run_verify("--fast")
        self.assertEqual(code, 2, out)
        self.assertIn("至少要有一条 static.paths 或 static.symbols", out)

    def test_static_coverage_rejects_marker_annotation(self) -> None:
        self.write("fixtures/dw.sql", "SELECT 1;\n")
        self.make_page(self.make_block("p17-echo", ["docker run --rm mysql"]))
        self.make_contract(self.static_contract())
        code, out, _ = self.run_verify("--fast")
        self.assertEqual(code, 1, out)
        self.assertIn("coverage: static 的页不得写", out)

    def test_static_coverage_still_checks_symbols(self) -> None:
        self.write("compose.yaml", "services:\n  mysql:\n    image: mysql:8.0\n")
        self.make_page(self.make_block(None, ["docker compose up -d"]))
        symbols = "    - file: compose.yaml\n      pattern: 'mysql:8\\.0'\n"
        self.make_contract(self.static_contract(paths='["compose.yaml"]', symbols=symbols))
        code, out, _ = self.run_verify("--fast")
        self.assertEqual(code, 0, out)
        self.write("compose.yaml", "services:\n  mysql:\n    image: mysql:9.0\n")
        code, out, _ = self.run_verify("--fast")
        self.assertEqual(code, 1, out)
        self.assertIn("符号未命中", out)


if __name__ == "__main__":
    unittest.main(verbosity=2)
