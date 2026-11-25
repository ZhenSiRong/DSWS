# 教材可跟随性验收线 · T2 级考核自动线

> T0/T1 是**逐页**的静态/离线契约核对（`docs/verify-line.md`，实现 `scripts/verify.py`）；T2 是**按级**的全栈考核：把 `manual/ACCEPTANCE.md` 的 L1–L5 拆成「脚本能安全自动跑的部分」+「必须人工/有破坏性的 MANUAL 步骤」。术语口径见 `GLOSSARY.md`「验收线术语」，决策见 `docs/adr/0002-followability-line.md`。

## 什么时候跑

- **栈已起（T2 本线）**：第 13 页 `make docker-up` 完成、`docker compose ps` 5 个长驻服务（mysql / elasticsearch / qdrant / backend / frontend）healthy 后，跑 **L1 / L2 / L5**。栈没起不会有半截绿：一律 `SKIP`（退出码 2），脚本绝不自己起栈。
- **任意时刻（离线）**：**L3 / L4** 不需要栈、不改文件，随时可跑，也是 p13 起栈前的回归门。
- 级考核（p13 / p17 / p22 / p23 的「拆一刀」）一律人工：脚本只打印步骤，不执行。

## 前置

- 仓库根、Docker + Compose v2、`backend/.venv`（`make install`）；L4/L5 的前端单测还要 `frontend/node_modules`（缺了记**可选 SKIP + WARN**，不阻塞）。
- 只读栈检查要 `.env`（`make docker-env`）；L1/L2/L5 会 source `scripts/export-docker-env.sh` 校验凭据，**不写文件**。
- 可在任意 cwd 调用：脚本自己定位仓库根。

## 用法与退出码

```bash
make accept-l1        # … accept-l5（Makefile 目标；未就绪时直接调脚本）
bash scripts/acceptance/level-l3.sh
```

| 退出码 | 末行 | 含义 |
|---|---|---|
| 0 | `LEVEL Lx PASS` | 自动检查全过；**MANUAL 仍需人做**，不代表整级验收完成 |
| 1 | `LEVEL Lx FAIL` | 自动检查有红；失败明细在末行之前 |
| 2 | `LEVEL Lx SKIP` | 前置缺失/栈没起，无法判定；**SKIP 不是通过** |

- 输出统一以 `LEVEL <级> PASS/FAIL/SKIP` 结尾，前面是每条检查的 OK/FAIL/SKIP 和失败明细；栈没起时能看到 `SKIP: … 需要先按第 13 页起栈（make docker-up）`。
- `SKIP(可选)` 是子项（如 8088 成熟版没起），只记 WARN，不改变本级判定——它不会被当成通过。

## 每级自动 / MANUAL 对照

| 级 | 脚本自动（只读/安全） | MANUAL（脚本只打印） |
|---|---|---|
| L1 p00–p09 | `make doctor`（12/12）、`audit_book.py`（24/24）、T2 栈 `/api/health` | p01–p09 逐页判据、建成证明海报；手工 lab 栈（3307/8000/8081） |
| L2 p10–p13 | 栈预检（5 服务 running/healthy）、`make docker-smoke`（≤240s）、结构审计 | p13 级考核：`make docker-down` / 删 init / 改 `compose.yaml` / `lab reset` |
| L3 p14–p17 | 离线 pytest（recall / generate / test_correct）、`failures --check`（S6）、`probe_correction`（mismatch 0） | p17 级考核：关纠错（改代码）+ `lab reset` |
| L4 p18–p22 | 离线 `security --check`（S5、36/36）、cancel 测试、`record_sse --check`（S7）、前端 `npm test`（40 passed） | p22 级考核：抢窗口给 `dw_reader` 注入 `GRANT ALL` + 还原 |
| L5 p23 | 栈预检、前端 `npm test`、教学版 `POST /api/query` 含 `41099.5`；8088 成熟版在则探活（未起为可选 SKIP） | p23 级考核：删 `lab-mature` / 写 17 行 HTML / 还原；浏览器渲染、标题、12 节点流程图 |

## 安全边界（脚本绝不做的）

启动/停止/重建栈、`docker compose down`、删卷/删容器、改代码、写数据库或权限、`lab reset`、真 LLM 调用。破坏性步骤只在 MANUAL 里列出并写明还原命令。
注意 `make docker-smoke` 内部第 1 步是幂等的 `docker compose up -d --build`（p13 判据的一部分）；栈预检不过时脚本直接 SKIP，不会执行到它。

## 与其它门的关系

- `manual/ACCEPTANCE.md`：判据原文唯一正典；本线只是它可自动化的子集，不替代逐页对账和 MANUAL 级考核，失败先按该文件 §8「失败时看哪」。
- `make verify`（T1，`scripts/verify.py`）：逐页契约的离线核对，fail-closed；T2 是跨页/栈级的级考核，两者互补、不互相替代。
- `make audit` / `make docker-smoke`：能复用的直接调用，不复制实现。

## 失败排查

- `SKIP`：先 `docker compose ps -a`；按第 13 页起栈（或补 `make install` / `make docker-env`）。
- `FAIL`：脚本已回显命令与真实输出；按 `manual/ACCEPTANCE.md` 对应页的「你应该看到」和 §8 定位；`make verify` 先排掉页面契约层的断层。
- 别在别人的栈上跑级考核/注入类步骤；并行验收用仓库副本 + 独立 compose 项目名 + 端口覆盖（page-13、`manual/review/replay-page-14.md`）。
