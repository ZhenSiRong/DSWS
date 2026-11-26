# Workflow · 任务生命周期（task-lifecycle）

> 一个 loop 的规格：工作区里**每一项原子工作**都沿同一条受门禁的生命周期推进
> （`todo → doing → done`，在 worktree 内做，done 必过 review）。
> 本文件是真相源规格；实现者照此建造，**不应再需要问任何问题**。
> 决策来源：/loop-me grilling Q1–Q12（见文末决策日志）。借鉴 OpenSpec 的
> 「带 ID 台账 + 显式依赖链 + status 报 blocked」模型，但**不安装 OpenSpec**；
> 执行层复用本机 Orca（`orca-ide orchestration`），不可用时降级 `git worktree`。

---

## 1. 这个 loop 是什么

反复出现的模式：**派一项活 → 在隔离 worktree 里做 → 做完先过独立 review → 才许标 done → 解锁后继**。
它把"工作区每项工作的开始/结束"变成结构化、可核对、不许跳步的台账，而不是靠"记得更新甘特"。

### loop 词汇映射（仅在需要时取用）

- **Trigger（事件，非定时）**：用户派活，或 agent 取下一个 `ready` 任务。状态只在离散点变，
  不做后台轮询守护进程（承接 14 文档「hooks 不是 daemon」结论）。
- **Checkpoint**：唯一人工介入点 = **review 门禁**。默认由 review agent 自动把关；
  只有审出 `blocker`、或用户要 `--force` 越过时才把人拉进来。
- **Push right**：review 推迟到 `done` 那一刻才介入——先把活干完、证据备齐，再一次性请人/请审，
  不在中途反复打断。
- **Brief**：review 呈现给人的是**一行 `VERDICT: pass|blocker` + 报告链接**
  （`toolbox/workflows/reviews/<id>.md`），不是原始 diff。人读 brief，不读草稿。

---

## 2. 真相源：`toolbox/workflows/ledger.yaml`

**唯一持久真相源**，可 git 提交、跨会话/跨 Orca Run 长存。**唯一合法写入口 = `toolbox/scripts/task.py` CLI**
（chokepoint）。手改 YAML 视为非法，由 `task.py check` 兜底揪出。

```yaml
meta:
  host: Zhensirong-thinkpad          # 本机身份（hostname）
  repo: /home/zhensirong/VM-Share/DSWS-design-lab
  updated_at: 2026-11-23T16:40+08:00 # 每次 CLI 写入刷新
tasks:
  - id: G3                           # 稳定 ID（沿用甘特 s/m/c/g/r 前缀；新任务=组前缀+序号）
    title: GrapesJS 试点 editor.html 骨架
    group: grapesjs-pilot            # 对应甘特 section
    depends_on: [G1, G2]             # 依赖边；start 闸=全部 done 才解锁；add 时拒环
    status: doing                    # todo | doing | done（三态，见 §3）
    blocked_reason: null             # 旁注：卡住原因（不改 status）
    failed_reason: null              # 旁注：失败原因（fail 时 status 回 todo）
    started_at: 2026-11-23T16:10+08:00   # ISO8601 本地 +08:00，分钟精度
    ended_at: null
    approx: false                    # 迁移来的历史时间戳标 true（git 证据时间近似）
    worktree: /home/zhensirong/VM-Share/DSWS-design-lab-G3
    branch: task/G3
    agent: opencode2                 # 干活的 agent（Orca worker 或 manual）
    session_id: <orca dispatch id>   # worker-start --json 回填；manual 时记实际会话标识
    provenance: "Zhensirong-thinkpad@~/VM-Share/DSWS-design-lab-G3&opencode2 -s <id>"
    evidence:                        # done 钉证据（承接 check_progress 的声明→现场）
      - { kind: file, path: tutorial/rebuild/editor.html, criterion: 存在且含 8 块注册 }
      - { kind: cmd,  run: "python3 tutorial/shots/audit_book.py", criterion: exit 0 且 24/24 }
    review:
      verdict: null                  # pass | blocker | null
      reviewer: codebuddy            # 跨模型 agent；兜底 builtin-codereview
      report: toolbox/workflows/reviews/G3.md
      at: null
      overridden: false              # --force 越过 review 时 true
      override_reason: null
```

字段约定（消除歧义）：
- 时间戳：`date +%Y-%m-%dT%H:%M%:z`（分钟精度，带 +08:00）。
- `provenance` 渲染式：`<host>@<worktree>&<agent> -s <session_id>`。
- `evidence[].kind` ∈ `file|cmd`；`file` 验存在+ criterion 文本命中，`cmd` 验 exit 0 + criterion。
- 空值用 `null`，不用空串。

---

## 3. 状态机（三态 + 旁注，Q9=A）

```
        start(deps 全 done)            done(review pass 或 --force)
 todo ───────────────────────▶ doing ───────────────────────────▶ done(终态)
  ▲                              │  ▲
  │        fail(reason)          │  │ unblock / 继续做
  └──────────────────────────────┘  │
        block(reason)：doing 不变，只写 blocked_reason（旁注，非独立态）
        reopen(reason)：done → doing，清 ended_at（需 reason）
```

- **三态**：`todo / doing / done`。`blocked`/`failed` 是**旁注字段**而非独立态（避免状态机膨胀）。
- **并行允许**（Q4=B）：可同时多个 `doing`，**不设全局单 doing 约束**。
- **唯一硬闸 = 依赖**：`start X` 要求 `X.depends_on` 全部 `done`（done 已含 review pass）。
  这就是"未开始/前驱未完成就不许推进"的确切含义。
- `done` 是终态；要重开用 `reopen`（留 reason）。

---

## 4. CLI chokepoint：`toolbox/scripts/task.py`

唯一写入口。吸收 `check_progress.py`（已转为兼容转发壳，旧入口仍可用）；渲染复用
`render_progress_gantt.py` 抽出的 `render_to_png()`（见 §9/§10）。依赖：**PyYAML**（唯一第三方
依赖，本机已装）+ 调用 `orca-ide`/`git`；渲染另需 google-chrome + ImageMagick + 本地 mermaid.min.js。

| 命令 | 作用 | 门禁/副作用 |
|---|---|---|
| `add <id> --title T [--group G] [--deps a,b]` | 注册新任务 | 拒重复 ID；**拒依赖环**；status=todo |
| `start <id> [--agent A]` | 开工 | status 必须 todo；**deps 全 done 否则拒绝**；建 worktree(§5)；盖 started_at；→doing |
| `done <id> [--force --reason R]` | 收工 | status 必须 doing；备 review brief、置 verdict=pending、**退码 2**（Orca 可用则派 worker）；`--force` 需 `--reason`，跳过 review 直接 done+overridden=true |
| `verdict <id> [--report PATH]` | review 定案 | 读报告末行 `VERDICT:`；pass→done+ended_at 退码 0；blocker→留 doing 退码 1 |
| `block <id> --reason R` / `unblock <id>` | 卡住/解卡 | 写/清 blocked_reason，status 不变 |
| `fail <id> --reason R` | 失败 | status→todo，写 failed_reason，**保留 worktree** 供重试 |
| `reopen <id> --reason R` | 重开 | done→doing，清 ended_at，写 reason |
| `evidence <id> --kind file\|cmd (--path P\|--run R) [--criterion C]` / `--clear` | 钉/清证据 | done 后拒改（须 reopen）；`check` 据此验真（§9.1） |
| `list [--ready] [--status S]` | 台账视图 | `--ready`=deps 已满足的 todo；报 `blocked-by`（借 OpenSpec status） |
| `show <id>` | 单任务详情 | 含 provenance/review/evidence |
| `check [--quick]` | 一致性校验(§9) | 漂移退码 1；`--quick` 跳过 audit_book |
| `render` | 投影甘特(§8) | ledger→mermaid→PNG→meta |
| `board [--out PATH] [--no-check]` | 投影浏览器看板(§8.1) | ledger→单文件 HTML+meta；默认 `toolbox/workflows/board.html`（或 `meta.render.board`）；`--no-check` 跳过写后身份自检 |
| `migrate-from-gantt` | 一次性迁移(§10) | 从 14 文档灌入现有任务 |

**chokepoint 强制力**：所有门禁在 CLI 内执行，**与 git 解耦**——每次 start/done 都触发，
不依赖 commit（正面回答 14 文档 L112「没有 commit 呢？」：主网是 CLI，commit hook 只是兜底）。

**退出码**：0 成功；1 门禁拒绝/漂移/blocker；2 review 待派（`done` 后需 `verdict` 定案）。

---

## 5. worktree 绑定（Q7=B：worktree 硬要求，创建者可 Orca 可 git）

`start` 必须把任务放进一个隔离 worktree。**worktree 路径约定**：`<repo.parent>/<repo.name>-<id>`
（如 `…/DSWS-design-lab-G3`）；**分支约定**：`task/<id>`。

- **Orca 可用**（`orca-ide orchestration run-current` 返回 ok）：
  `orca-ide orchestration worker-start --task <id> --worktree new-child --agent <A> --base-branch <当前分支> --json`
  → 解析 receipt 回填 `worktree`/`branch`/`session_id`(dispatch id)/`agent`。
  worker 受 Orca 监管（`worker-read/stop/show` 可用）。
- **Orca 不可用**（`runtime_unavailable`，如当前 app 未开）：降级
  `git worktree add <path> -b task/<id>`；`agent` 记 `manual`（或用户实际跑的），
  `session_id` 记手动会话标识。**状态机/时间戳/review 照常**，不因 app 没开而失效。
- 探测可用性：CLI 先跑 `run-current --json`，按 `ok` 字段分流；不假装 Orca 在跑。

---

## 6. review 门禁（Q5=a+丙乙甲+Ⅰ，Q8=C）

`done <id>` 触发独立 review，**blocker 阻断 done**。实现为**两段式**（因内置 CodeReview 是 IDE
子代理，Python 脚本无法直接派发它；CLI 只管状态闸口，review 智能可插拔）：

**第一段 `done`**：status 必须 doing → 写 review brief 到 `toolbox/workflows/reviews/<id>.request.md`
（含 worktree/branch/声明证据/审查顺序）→ 置 `review.verdict=pending`、选 reviewer → **退码 2**，
打印「该派谁审、审完跑 `task.py verdict <id>`」。Orca 可用时同时 `worker-start --spec-file <request>
--agent <reviewer> --worktree <task.worktree>` 派 worker 审。`--force --reason R` 跳过这一切直接 done。

**第二段 `verdict`**：读 `toolbox/workflows/reviews/<id>.md` 末行 `VERDICT:` 定案。

1. **选 reviewer（跨模型独立）**：从 `{opencode2, codebuddy, qoder}` 选 **≠ task.agent** 者；
   Orca 不可用 → `reviewer=builtin-codereview`（由主会话派 CodeReview subagent 审 worktree diff）。
2. **审什么（丙→乙→甲）**：① done 的**证据/判据真成立吗**（声明→现场）；② 页面/文档改动；③ 代码改动（按需）。
3. **结论格式**：reviewer 写 `toolbox/workflows/reviews/<id>.md`，**最后一非空行**必须 `VERDICT: pass|blocker`。
4. **判定**：pass→done+ended_at+review 落盘（退码 0）；blocker→**留 doing**+review.verdict=blocker（退码 1，打印报告路径=brief）；
   `--force`→done+overridden=true+override_reason（**永远留痕**）。

---

## 7. 依赖闸与并行（Q4=B）

- 依赖边存 `depends_on`；`add` 时做**环检测**（DFS），有环拒绝。
- `start` 闸：所有前驱 `done` 才解锁；否则报 `blocked-by: [前驱 id…]` 并拒绝。
- **允许并行**：独立任务（无依赖关系）可同时 `doing`，各在自己的 worktree。
- `list --ready` 给出当前可开工集合（deps 已满足的 todo），供 agent 取下一项。

---

## 8. 甘特投影（Q11=A：单一真相源，甘特是派生物）

`render` 从 `ledger.yaml` 生成，**手不再改甘特行**；甘特暂时只有「mermaid 源 + PNG」这一种形态，不做甘特 HTML。

1. 读 ledger → 生成 mermaid gantt：`section`=group；每条任务一行，
   `done`→`done`、`doing`→`active`、`todo`→普通；`depends_on`→`after <dep>`；
   milestone（如 g4）保留 `milestone`。todayMarker 跟系统日期。
2. 把生成的 mermaid 写回 `meta.render.doc`（本仓库=`materials/humen-desicions/14-progress-gantt.md`；
   独立工具默认 `toolbox/workflows/gantt.md`）的 ```mermaid``` 块（**生成物**）。PNG 路径同理走 `meta.render.png`。
3. 复用现有离线渲染管线（本地 `materials/design/assets/mermaid.min.js` + google-chrome headless + ImageMagick trim）
   出 `materials/humen-desicions/progress-gantt.png`。**gantt 配置必须 `useMaxWidth:false` + `useWidth:1600`**
   （否则 SVG 塌缩到 340x183、放大模糊——已踩过的坑）。
4. 写 `progress-gantt.png.meta` = **ledger.yaml 的 sha256**（身份对账，不用 mtime）。

### 8.1 浏览器看板（人类入口）

`render`（甘特：md 内 mermaid 源 + PNG）与 `board`（任务表格/汇总视图）都是 `ledger.yaml` 的投影，
两者并列；**甘特暂时只有 mermaid 源 + PNG 这一种形态，不做甘特 HTML；board 是任务视图，不替代甘特**：

- **用途**：给不泡终端的人、投屏、截图汇报。产出单文件静态 HTML，`file://` 双击即看，不用起服务。
- **默认路径**：`meta.render.board`，未配置则 `toolbox/workflows/board.html`；同目录写 `board.html.meta`
  （JSON：`ledger_sha256` / `generated_at` / `task_count`）。
- **内容**：头部仓库 basename、分支（`git rev-parse` 尽力）、生成时间、台账 sha 前 12 位、`updated_at`；
  汇总条 todo/doing/done、blocked-by、里程碑；按 `group` 分区表格（状态徽章、标题+里程碑、
  blocked-by 前驱、证据数量+种类缩略、review verdict+报告文件名、起止时间）；
  依赖全 done 的 todo 行标「可开始」并高亮。
- **单文件自包含**：CSS/JS 内联，无外链/CDN/网络请求；状态筛选 + 标题搜索是渐进增强，禁用 JS 仍可完整阅读。
- **安全**：不写绝对路径（报告只给仓库内相对链接或文件名），`title`/证据等展示文本做 HTML 转义。
- **与 check 的关系**：board 存在时，`check` 比对 `board.html.meta.ledger_sha256` 与当前
  `sha256(ledger.yaml)`；不一致记 `board 身份对账` 漂移并提示重跑 `task.py board`。
  没有 board 文件则跳过，不新增失败。

---

## 9. 校验：`task.py check`（吸收 check_progress.py）

`check` 逐项核对，任一漂移退码 1：
1. **每个 done 任务的 evidence 真成立**（file 存在+criterion 命中 / cmd exit 0+criterion）——治假 done。
2. **台账一致性**：doing/done 的 deps 全 done；无环；started_at≤ended_at；done 必有 review.pass 或 overridden。
3. **投影身份对账（甘特 + board）**：`sha256(ledger.yaml)` == `progress-gantt.png.meta`（否则需 `render`）；
   若 `board.html` 存在，还须 == `board.html.meta.ledger_sha256`（否则需 `board`）；无 board 文件则跳过——不引入新失败。
4. **全局闸门**：`audit_book.py` exit 0 且 24/24、README 坏链 0（`--quick` 跳过，因 pre-commit 第 1 项已跑）。

> 现有 check_progress.py 的硬编码三查（grill 落定/GLOSSARY 词条/ADR）迁移为 s1/s2 任务的 evidence 条目，
> 不再硬编码在脚本里——证据随台账走。

---

## 10. 迁移（Q12=A：全量导入）与文件改动

`migrate-from-gantt` 解析 14 文档现有 mermaid + 证据表，灌入 ledger.yaml：

| 甘特行 | id | group | depends_on | 迁移 status | 备注 |
|---|---|---|---|---|---|
| grill 选型 12/13 | s1 | closed | [] | done | evidence: 12/13 含「落定」 |
| GLOSSARY+ADR | s2 | closed | [] | done | evidence: 词条命中+ADR 存在 |
| 进度看板 | s3 | closed | [] | done | evidence: PNG 存在 |
| 进度护栏接入 hooks | s4 | closed | [] | done | evidence: core.hooksPath 已设 |
| flatpak 安装 0.23.0 | m1 | marktext | [] | **doing + blocked_reason** | **甘特标 active 但实测下载已死**→纠为卡住，需重下 |
| 五条验收 | m2 | marktext | [m1] | todo | |
| 用户肉眼裁决 | m3 | marktext | [m2] | todo + blocked_reason=等用户裁决 | 原 crit |
| read-serve.sh | c1 | css-iteration | [] | todo | |
| read.css 首轮调优 | c2 | css-iteration | [c1] | todo | |
| editor.html+8 块 | g1 | grapesjs-pilot | [] | todo | |
| p17 导入点选重构 | g2 | grapesjs-pilot | [g1] | todo | |
| 六条判据验收 | g3 | grapesjs-pilot | [g2] | todo | |
| 闸门 G4 转正/回退 | g4 | grapesjs-pilot | [g3] | todo | milestone |
| p21 余 8 处长段 | r1 | reading-layer | [] | todo | 暂停待恢复 |
| A13/A18 并行支路 | r2 | reading-layer | [r1] | todo | |
| B 批 5 页 | r3 | reading-layer | [r2] | todo | |
| C 快通 12 页 | r4 | reading-layer | [r3] | todo | |

历史 done 项时间戳用 git 证据时间近似，`approx:true`。

**文件改动清单**：
- 新建 `toolbox/workflows/ledger.yaml`、`toolbox/workflows/reviews/`（懒建）、`toolbox/scripts/task.py`。
- `toolbox/scripts/check_progress.py`、`toolbox/scripts/render_progress_gantt.py` → 由 task.py 吸收；
  保留为薄壳转发（`check_progress.py --quick` → `task.py check --quick`）以不破坏现有 hook/Makefile，
  或直接改 hook/Makefile 指向 task.py（二选一，实现时取后者更干净）。
- `.githooks/pre-commit` 第 4 项、`Makefile` audit 第 5 项 → 改调 `task.py check --quick`。
- `materials/humen-desicions/14-progress-gantt.md` mermaid 块 → 标为生成物，由 `task.py render` 写。
- `AGENTS.md` 硬规则 3 增补（见 §11）。
- `NOTES.md` 记录新术语（任务台账/chokepoint/review 门禁/worktree 绑定/依赖闸）。

---

## 11. 强制点（三层，主网与 git 解耦）

1. **CLI chokepoint（主）**：start/done 门禁在每次调用时执行，**不依赖 commit**。这是"不许跳步"的真正强制力。
2. **pre-commit hook（兜底）**：`task.py check --quick` 揪手改 YAML/忘 render 的漂移，挡进历史前。
3. **AGENTS 硬规则 3 增补（纪律）**：
   > 先落盘再收尾——结论先写回文件。**任务状态变更只经 `toolbox/scripts/task.py`；任务在 worktree 内推进；
   > done 必过 review（或 `--force` 留痕）；收尾跑 `task.py check` + `render`。**

---

## 12. 实现验收（这个 spec 的 DoD）

实现者交付后，下列必须真跑通过：
- `task.py add X --deps Y` 造环 → 拒绝。
- `task.py start X`（Y 未 done）→ 拒绝并报 blocked-by；Y done 后 → 成功建 worktree、盖 started_at。
- 两个无依赖任务可同时 doing（并行）。
- `task.py done X`：review pass→done+ended_at；blocker→留 doing 退码 1；`--force --reason`→done+overridden 留痕。
- Orca 没开时 start 走 git worktree 降级、done 走内置 CodeReview，全程不报错。
- `task.py render` 出的 PNG 清晰（≥1600 宽不糊），meta==ledger sha。
- `task.py board` 出的 HTML 单文件可离线读、无外链/绝对路径，title 已转义，依赖满足的 todo 标「可开始」；
  改台账不重 board → `check` 报 `board 身份对账` 漂移。
- `task.py check` 对假 done/漂移退码 1；`make audit` 仍 5/5 全绿。
- `migrate-from-gantt` 后 ledger 含全部 s1–r4，m1 标 blocked_reason。

---

## 13. 决策日志（grilling Q1–Q12）

| # | 决定 |
|---|---|
| Q1 | 单位=原子可验收任务；台账带 host+worktree+agent 会话源；**YAML** 格式；任务在 worktree 内推进 |
| Q2 | CLI chokepoint 为唯一写入口（A） |
| Q3 | 三态+双时间戳（A） |
| Q4 | **显式依赖边 + 允许并行**（B，否决了全局单 doing） |
| Q5 | done 自动派 review，丙→乙→甲，blocker 阻断（a+Ⅰ） |
| Q6 | **YAML 唯一持久真相源 + Orca 当执行器**（A） |
| Q7 | worktree 硬要求；Orca 不可用降级 git worktree（B） |
| Q8 | review 跨模型 Orca worker 优先、内置 CodeReview 兜底（C） |
| Q9 | 三态 + blocked/failed 旁注字段（A） |
| Q10 | review 阻断有 `--force` 留痕逃生口（B） |
| Q11 | 甘特从 YAML 派生，单一真相源（A） |
| Q12 | 全量迁移现有 s1–r4（A） |

**借鉴而非采用**：OpenSpec v2.1.1 实测确认其 `tasks.md+status+instructions --json` 提供
「带 ID 台账+依赖链+blocked 报告」模型，但缺进行中态/时间戳/任务级硬门禁/自动 review，
且为 Run 作用域不持久——故只借模型，真相源与门禁自建，执行层用 Orca。