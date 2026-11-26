# 截图框架（render_page_shots.py）——为什么抽、怎么用、和旧脚本什么关系

## 为什么抽

旧四套脚本 `render_l2_pages.py` / `render_l3_pages.py` / `render_l4_pages.py` /
`term_render.py` 合计 **5741 行**，每套都重写「建副本 → 起栈 → PTY 抓输出 → 渲 HTML →
Chrome 截图 → OCR/对账 → 清栈」。抽成一个 **587 行**框架 + 每页一份 JSON 配置：
公共能力只维护一份，一页要什么写成数据。旧脚本**不删、不改**，留作历史与重栈页实现。

## 配置 schema（`tutorial/shots/captures/<page>.json`）

```json
{
  "page": "page-19", "title": "第 19 页 · …",
  "output": "/tmp/shots-demo/page-19-policy.png",
  "stack": {"mode": "none|mysql|full", "project": "shots-page-19",
            "env_ports": {"MYSQL_HOST_PORT": 13337}, "exec_replace": [["127.0.0.1:8080", "127.0.0.1:18077"]]},
  "embed": {"path": "tutorial/page-19.md", "image": "images/page-19-policy.png",
            "alt": "…", "anchor": "## 对账", "position": "before", "mode": "verify|replace|off"},
  "ocr_keywords": ["36/36", "S5 PASS"],
  "panels": [{"heading": "终端 · 第 2 步：…",
              "commands": ["<页面原文命令>", {"run": "<执行替身>", "show": false}],
              "expect_lines": ["真跑输出里必须有的行", "… 当通配"],
              "display": "all|matched", "timeout": 300, "allow_exit": [0]}]
}
```

- `panels`：一段 = 一块终端窗口；`display=matched` 只把命中 `expect_lines` 的真实行上图。
- `expect_lines`：页面「你应该看到」样例行，逐行对账 + `…` 通配；`#` 注释行跳过。
- `stack=none` 不启容器；`mysql` 起临时容器（`rm -f`）；`full` 用 `docker compose -p` + `.env` 端口覆盖，等健康后跑页、跑完 `down -v`。
- `embed.mode=verify` 只核对页面已有同一行；`replace` 幂等写页（已有则替换/去重，无则按锚点插入）。

## 新增一页要做的 3 步

1. 从 `tutorial/page-NN.md`「## 动手」抄命令原文、「## 你应该看到」抄期望行，写
   `tutorial/shots/captures/page-NN.json`（离线页 `stack.mode=none`，输出先指 `/tmp`）。
2. `python3 tutorial/shots/render_page_shots.py page-NN --dry-run` 查步骤与执行替身，再真跑去掉 `--dry-run`。
3. 自检全绿后把 `output` 改回 `tutorial/images/page-NN-<slug>.png`、`embed` 改 `replace`，重跑并提交。
## 与旧脚本的关系

`term_render.py` 仍被本框架 import，复用 CSS/字体/HTML 行渲染；`render_l2/l3/l4_pages.py`
保留为历史，重栈页（整套 compose + 初始化 + 拆一刀）仍以它们跑出的已提交图为准——框架抽走
了公共能力，但不替换它们的特殊编排。

## 已知限制

- 重栈（`full`）页本次未端到端演练：旧脚本编排更成熟，仍建议**单栈串行**跑，别并行占端口。
- 页面命令与「## 动手」的逐字比对不在自检内（靠配置作者抄原文 + 人工复核）；OCR 只认
  英文/数字（tesseract 无中文包），中文靠渲染前原文逐行对账。
- 一页一图（多图页拆多份配置）；`--all` 顺序执行，重栈页不要 `--all`。
