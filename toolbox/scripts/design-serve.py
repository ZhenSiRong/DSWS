#!/usr/bin/env python3
"""页首图编辑服务：静态文件 + /api/save（覆盖保存并重建 PNG/WebP/阅读版）。

用法： scripts/design-serve.py [PORT]   # 默认 8788
入口：http://127.0.0.1:8788/manual/designs/
"""
from __future__ import annotations
import json, re, signal, subprocess, sys, shutil
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parents[2]
DESIGNS = ROOT / "toolbox" / "page-visuals"
PAGE_RE = re.compile(r"^\d{2}$")
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8788


def run(args: list[str], timeout: int = 180) -> tuple[int, str]:
    try:
        p = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, timeout=timeout)
        return p.returncode, (p.stdout + p.stderr).strip()
    except subprocess.TimeoutExpired:
        return 124, "超时"
    except Exception as e:  # noqa: BLE001
        return 1, str(e)


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(ROOT), **kw)

    def log_message(self, fmt, *args):  # quieter
        return

    def _json(self, code: int, payload: dict) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("content-type", "application/json; charset=utf-8")
        self.send_header("content-length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):  # noqa: N802
        if not self.path.startswith("/api/save"):
            self._json(404, {"ok": False, "error": "not found"}); return
        try:
            n = int(self.headers.get("content-length", "0"))
            payload = json.loads(self.rfile.read(n) or b"{}")
            page = str(payload.get("page", ""))
            html = payload.get("html", "")
            if not PAGE_RE.match(page):
                self._json(400, {"ok": False, "error": "page 必须是 00–23"}); return
            if not isinstance(html, str) or '<div class="poster"' not in html:
                self._json(400, {"ok": False, "error": "HTML 不像页首图（缺 .poster）"}); return
            proj = DESIGNS / f"page-{page}"
            index = proj / "index.html"
            if not proj.is_dir():
                self._json(404, {"ok": False, "error": f"设计目录不存在：page-{page}"}); return
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            (proj / "out").mkdir(exist_ok=True)
            if index.is_file():
                shutil.copy(index, proj / "out" / f"index.{stamp}.bak.html")
            index.write_text(html, encoding="utf-8")
            messages = []
            rc, out = run(["node", str(Path.home()/".agents/skills/editable-design/scripts/wire-editor.mjs"), str(index)])
            if rc != 0: messages.append("editor 重建失败：" + out[-200:])
            rc, out = run([sys.executable, str(DESIGNS/"inject_save_ui.py"), page])
            rc, out = run([sys.executable, str(DESIGNS/"render_existing.py"), page])
            if rc != 0: messages.append("PNG/WebP 渲染失败：" + out[-300:])
            rc, out = run([sys.executable, str(ROOT/"toolbox/shots/render_read.py"), page])
            rc, out = run([sys.executable, str(ROOT/"toolbox/shots/audit_book.py")])
            messages.append("audit：" + (out.splitlines()[-1] if out else "?"))
            self._json(200, {"ok": True, "messages": messages})
        except Exception as e:  # noqa: BLE001
            self._json(500, {"ok": False, "error": str(e)})


if __name__ == "__main__":
    srv = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"页首图编辑服务： http://127.0.0.1:{PORT}/manual/designs/")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
