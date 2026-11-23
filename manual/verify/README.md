# 教材可跟随性验收线（`manual/verify/`）

> 一句话：页面里写给学生敲的命令、路径、关键输出，和仓库里的代码/证据**用契约绑死**；
> 任何一边改了另一边没改，验收就会红。防止教材修订后「跟做断层」。

本目录只放**契约**与规则，执行器是 `scripts/verify.py`。

## 两级验收（T0 / T1）

| 级别 | 入口 | 目标耗时 | 做什么 | 不做什么 |
|---|---|---|---|---|
| **T0** | `python3 scripts/verify.py --fast` | < 2s | 契约解析/字段校验；页面注解 ↔ 契约**双向同步**；静态存在性（路径 / 符号）；证据文件存在 | **不执行任何命令** |
| **T1** | `python3 scripts/verify.py`（默认） | < 2min | T0 + 按顺序**真执行** `kind: offline` 命令，断言 exit / 关键行 / 正则；证据过期检查 | 不执行 `kind: manual` |
| T2 | （另一条线：按级考核脚本） | — | 级考核的整体复跑 | 不在本目录范围 |

推荐接法：提交前护栏调 `--fast`（T0），本地/整栈验收调默认（T1）。
具体接入口（`Makefile` 目标、`.githooks/pre-commit`）由各自文件维护，本目录只提供
`scripts/verify.py` 与契约。

## 目录与文件

```
scripts/verify.py                     # 执行器（T0/T1 核心 v1）
scripts/tests/test_verify.py          # 执行器单测（归一化 / 同步 / 静态 / expect 校验）
manual/verify/README.md               # 本文件：schema 与规则
manual/verify/contracts/page-17.yaml  # 第 17 页契约（参考样例）
manual/page-17.md                     # 对应页面：bash 围栏前写 <!-- verify: <marker> -->
```

## 用法与退出码

```bash
python3 scripts/verify.py                 # T1：T0 + 执行 offline 块
python3 scripts/verify.py --fast          # T0：只做静态验收（pre-commit 用）
python3 scripts/verify.py --strict        # 证据缺失（T0）/ 过期（T1）从 warn 变 fail
python3 scripts/verify.py --page page-17  # 只验收一页（也接受 17）
python3 scripts/verify.py --list          # 列契约（不验收）
python3 scripts/verify.py --json          # 机器可读汇总（stdout 只有 JSON）
```

退出码统一为：**0 通过 / 1 验收失败 / 2 契约或配置错误**。
`manual/verify/contracts/` 不存在或没有任何 `*.yaml` 时退出 0，并提示「无契约」。

依赖：执行器与单测都用**宿主 `python3`**（`PyYAML`，本机 6.0.1）；
只有 T1 执行契约命令时才调用 `backend/.venv/bin/...`，`--fast` 不碰 venv、不碰网络。

`--list` 输出示例（节选）：

```
契约（1 个，目录 manual/verify/contracts）
  page-17  第 17 页 · 审纠错：一次重试能修好什么、修不好什么  blocks=8（offline=4 / manual=4）  ...
    - p17-pytest-correct  offline
    - p17-lab-save  manual  # 会往 .lab/snapshots/ 写白名单文件快照 ...
```

`--json` 顶层字段：`mode`（`T0`/`T1`）、`strict`、`duration_sec`、`contracts[]`
（每页的 `status` / `blocks` / `failures` / `warnings` / `executions`）、`summary`
（`pages` / `passed` / `failed` / `blocks` / `offline` / `manual` / `executed` /
`execution_failures` / `warnings`）、`exit_code`。契约错误时顶层为 `contract_errors`；
无契约时顶层为 `no_contracts: true`。

## 契约 schema

一个页面一个契约文件：`manual/verify/contracts/<page>.yaml`（`<page>` 形如 `page-17`，
必须与 `page` 字段、页面文件名一致）。完整样例见 `contracts/page-17.yaml`：

```yaml
page: page-17
title: 第 17 页 · 审纠错
blocks:
  - id: p17-pytest-correct          # 契约内部唯一 id（消息里用它定位）
    marker: p17-pytest-correct      # 必须等于页面里 <!-- verify: <marker> -->
    kind: offline                   # offline | manual
    cmd: |                          # 必须与页面 fenced block 内容一致（归一化后）
      backend/.venv/bin/python -m pytest backend/tests/agent/test_correct.py -q
    expect:                         # offline 必填；manual 必须不写
      exit: 0                       # 子进程退出码（整数）
      contains: ["14 passed"]       # 关键行：stdout+stderr 里必须出现的子串
      regex: []                     # 可选：Python re.search 模式列表（MULTILINE）
    page_contains: ["14 passed"]    # 可选：页面可见输出绑定（锚定到 verify-out 围栏，见下）
    timeout_sec: 60                 # 可选，默认 120；超时 → fail
  - id: p17-viztracer
    marker: p17-viztracer
    kind: manual
    reason: 打开浏览器 GUI，不适合 T1 无人值守   # manual 必填：为什么不执行
    cmd: |
      uv pip install --python backend/.venv/bin/python viztracer
static:
  paths:                            # 必须存在（相对仓库根，文件或目录）
    - backend/tests/agent/test_correct.py
    - contracts/errors.yaml
  symbols:                          # 文件必须存在，且正则在内容里 re.search 命中
    - {file: backend/app/agent/correct.py, pattern: "def propose_correction"}
    - {file: contracts/errors.yaml, pattern: "max_attempts: 1"}
evidence:
  - {path: manual/images/page-17-correct.png, note: "14 passed + S6 PASS 截图"}
```

### 字段规则

| 字段 | 必填 | 说明 |
|---|---|---|
| `page` | 是 | `page-XX`，与文件名/页面文件一致，否则退出码 2 |
| `title` | 否 | 仅展示用（`--list` / JSON） |
| `blocks` | 是 | 非空列表；`id` / `marker` 在契约内不得重复 |
| `blocks[].id` | 是 | 契约内部唯一 id |
| `blocks[].marker` | 是 | 页面注解 token（字母/数字/`._-`） |
| `blocks[].kind` | 是 | `offline`（T1 真跑）或 `manual`（只同步、不跑） |
| `blocks[].cmd` | 是 | 页面 bash 块内容；归一化后必须与页面一致 |
| `blocks[].expect` | offline 必填 | `exit`（整数，必填）、`contains`（字符串列表）、`regex`（正则列表） |
| `blocks[].page_contains` | 否 | 字符串列表；页面里必须可见，且 T1 真实输出也必须出现（见「反假绿」） |
| `blocks[].timeout_sec` | 否 | 正数秒，默认 120；仅 offline |
| `blocks[].reason` | manual 必填 | 为什么不执行（要具体，不能写「不方便」） |
| `blocks[].note` | 否 | 给人看的补充说明 |
| `static.paths` | 否 | 仓库内相对路径；绝对路径或含 `..` → 退出码 2 |
| `static.symbols` | 否 | `{file, pattern}`；`pattern` 是 Python 正则 |
| `evidence` | 否 | `{path, note}`；路径相对仓库根 |

**未知字段一律报错（退出码 2），防止拼错字段名造成假绿**；例如把 `contains` 写到块顶层
而不是 `expect` 下面，会直接红。

## 页面注解与双向同步

页面里每个 ` ```bash ` 块**前一行**写：

````markdown
<!-- verify: p17-pytest-correct -->
```bash
backend/.venv/bin/python -m pytest backend/tests/agent/test_correct.py -q
```
````

（注解与围栏之间允许**一个**空行；注解行本身是 HTML 注释，渲染后不可见，不改正文文字。）

T0 对每页做**双向**检查：

1. **页面 → 契约**：页面里的每个 `verify:` 注解 id 都必须出现在契约里。
2. **契约 → 页面**：每个契约块都必须能在页面里找到紧邻 ` ```bash ` 围栏的同名注解。
3. **块内容一致**：注解绑定块的命令与契约 `cmd` 归一化后必须逐行相等；不一致给出
   第一处差异（契约第 N 行 / 页面第 N 行）。
4. **全覆盖**：一个页面只要有了契约，该页**所有** ` ```bash ` 块都必须注解；
   漏标一个也 FAIL（防止新增命令绕过验收）。
5. **页面可见输出绑定**（`page_contains` + `verify-out`）：块声明了 `page_contains` 时，
   页面必须有 `<!-- verify-out: <marker> -->` 注解，且 token 必须出现在它绑定的
   `text` 围栏里、以及该块真实输出里——只改被锚定的页面文字（如 `14 passed` → `15 passed`）
   会让 T0 红；只改真实输出会让 T1 红。

## 页面可见输出绑定（`page_contains` + `verify-out`）

`page_contains` 的 token **不能**只要"页面里任意位置出现"就算数——那样改一处、别处还命中会假绿。
页面里要用第二类注解把 token **锚定到具体的 ` ```text ` 围栏**：

````markdown
<!-- verify-out: p17-pytest-correct p17-failures-check -->
```text
14 passed in 0.11s
S6 PASS
```
````

规则：
- 一个 `verify-out` 注解可写多个 marker（空格分隔），把后面这个 `text` 围栏同时绑给多个块。
- 同一个 marker 可以绑多个 `text` 围栏（token 只要出现在其中任一处）；T1 仍要求 token 在**该块真实输出**里出现。
- 契约块声明了 `page_contains` 但页面没有对应 `verify-out` 围栏 → T0 FAIL；围栏里 token 缺失 → T0 FAIL；真实输出缺 token → T1 FAIL。

## 反假绿与已知边界（v1）

- **绑定是逐 token 的**：只有 `page_contains` 声明的关键行才和页面/真实输出绑定；
  没有声明 token 的 `text` 围栏整段不自动比对（避免秒数、端口等易变值造成假红）。
  想让某行受保护，就把它写进对应块的 `page_contains` + 页面 `verify-out`。
- **拆一刀块在干净仓库验的是"干净态"**：`contracts/page-17.yaml` 的
  `p17-ablation-commands` 页内紧随的是消融后输出（`5 failed`），T1 在干净仓库只断言
  干净态关键行（`14 passed` / `S6 PASS` / `mismatch 0`）；消融态由 T2/人工复核。
  `--list` 会显示该块的 `note`。
- **证据过期**：默认只 warn（`--strict` 升 fail）；CI 新 clone 的 mtime 会被 checkout
  抹平，所以证据新鲜度主要在本地/维护者环境有意义。
5. 注解不得重复；注解必须真的紧贴 bash 围栏（飘在正文里的注解也 FAIL）。

` ```text ` / ` ```python ` 等其他围栏不参与覆盖（页面里的「你应该看到」输出块不需要注解）。

## 命令归一化规则

比较页面块与契约 `cmd` 前，两边都做同一套归一化（`normalize_cmd`）：

1. 换行统一为 `\n`（`\r\n` / `\r` → `\n`）；
2. 每行去掉首尾空白（空格、制表符）；
3. 行内连续空格/制表符折叠为**一个**空格；
4. 丢掉空行；
5. 剩余行按原顺序用 `\n` 连接（空行数量、缩进量不参与比较）。

例：`"  echo  hello \\n\\n"` 与 `"echo hello"` 归一化后相等；
`"a\\nb"` 与 `"a\\n b"` 相等；`"echo hello"` 与 `"echo bye"` 不相等（FAIL）。

## T0 / T1 检查清单

T0（`--fast`）逐页检查：

1. 契约能解析、字段合法（不合法 → 退出码 2）；
2. 页面文件存在；双向同步（上节 1–5）；
3. `static.paths` 存在、`static.symbols` 正则命中；
4. `evidence` 文件存在 —— **缺失只 warn**，`--strict` 下 fail。

T1（默认）在 T0 之上：

5. 按契约里的顺序执行 `kind: offline` 块：
   `subprocess` 在仓库根目录用 shell 执行，`timeout_sec` 超时即 FAIL（会杀整个进程组）；
6. 断言 `expect.exit`、`expect.contains`（在 stdout+stderr 合并文本里找）、`expect.regex`；
   失败时打印 `--- 真实输出（截断到 60 行）---` 与失败断言；
7. 证据文件 mtime **比页面 md 旧** → warn（`--strict` 下 fail）：页面改过但截图没重拍；
8. `kind: manual` 的块**只做命令同步校验，绝不执行**。

输出末尾固定汇总「页：M/N 通过；块：…；执行：…；警告：…」+ `T0/T1 PASS/FAIL（耗时 …）`。

## 反假绿约定

契约不是「记录页面上写了什么」，而是「代码必须还能支撑页面上的承诺」：

- **命令必须两边一致**：页面块改了、契约没改 → T0 FAIL；反之亦然。
- **关键行存稳定值**：只存不会因机器而变的数字/文字（如 `14 passed`、
  `S6 PASS`、`11 "expect": "corrected"`）；**不要存秒数**（`14 passed in 0.11s`
  会变）这类易变内容。
- **offline 块必须可无人值守、幂等、无破坏性**：不联网、不写业务数据、不依赖模型 key
  与本机 GUI；需要这些的块标 `manual` 并写清 `reason`。
- **证据过期是警告**：截图类证据不参与断言，但页面改过而截图没重拍会 warn；
  需要强约束的仓库/CI 用 `--strict` 升级为失败。
- **T1 只证明「命令还能跑出关键行」**，不证明截图内容正确 —— 截图仍由重放/级考核复核。

## 给新页面接验收（步骤）

1. 页面里给每个 ` ```bash ` 块前一行加 `<!-- verify: <page>-<slug> -->`（只加注释，不改正文）；
2. 复制 `contracts/page-17.yaml` 为 `contracts/<page>.yaml`，改 `page` / `title`；
3. 每个块填 `id`（建议与 marker 相同）、`marker`、`kind`、`cmd`（**从页面块原样复制**）；
4. offline 块补 `expect`：`exit` + `contains`（挑稳定的关键行/数字，别放秒数）；manual 块写 `reason`；
5. 补 `static.paths` / `static.symbols`（页面前提的代码、契约、语料文件）与 `evidence`；
6. 跑 `python3 scripts/verify.py --fast`（秒级）→ 修到 PASS；再跑默认 T1 真执行；
7. 新增/修改页面后跑 `python3 manual/shots/audit_book.py`，保证全书结构审计仍 24/24。

## 已知边界（v1）

- 只识别 ` ```bash ` 围栏；其他语言围栏不纳入覆盖。
- 一个页面一个契约文件；跨页共享命令需要在各页契约里分别声明。
- 超时会杀进程组，但极端情况下（命令自行 daemon 化）不保证回收所有后代进程；
  offline 块本就禁止后台常驻命令。
- 输出经清洗：不打印绝对仓库路径 / 家目录 / 用户名；契约里的路径必须相对仓库根
  （绝对路径直接退出码 2）。
- T2 级考核脚本不在本目录范围；本目录只管「页面跟随性」，不管业务正确性。
