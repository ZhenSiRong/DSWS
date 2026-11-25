# T8 · 运维 / 测试 / 附录（opencode）

## 角色与工作树

你是 DSWS 重建手册的作者之一。工作树：

```text
/home/zhensirong/VM-Share/DSWS-design
```

先读：

1. `design/WBS.md`
2. `design/STYLEGUIDE.md`
3. `design/inventory/facts.md`
4. `compose.yaml`
5. `Makefile` 的 `docker-*`、`stage*`、`baseline`
6. `docs/DOCKER-DEPLOY.md`、`docs/DOCKER-HANDOFF.md`
7. `docs/SETUP-FROM-SCRATCH.md` §2.12、§3、§4、§5、§6、§7
8. `scripts/docker-env.sh`、`docker-reset.sh`、`docker-smoke.sh`、`smoke_checks.py`
9. `contracts/errors.yaml`、`steps.yaml`、`sse.schema.json`
10. `backend/tests/` 目录结构

## 目标

写两章：

1. `design/book/chapters/40-ops.md`：部署、运维、测试、故障排查。
2. `design/book/chapters/90-appendix.md`：速查表、术语、文件索引、命令卡。

## 必须产出 A：`40-ops.md`（5,000–7,000 汉字）

结构：

```markdown
# 第五部分 · 部署、测试与故障排查

## 1. 两条启动路径：本地开发 vs Docker
（表：用途 / 命令 / 端口 / 前置 / 适用场景）

## 2. Docker Compose 拓扑
（图 25 + 服务表 + 卷 + 网络 + 健康检查）

## 3. 环境变量与凭据
（表：变量 / 谁读 / 缺了会怎样；强调密码不进仓库）

## 4. 启动顺序与失败定位
（图 27；三存储 healthy → init completed → backend healthy → frontend）

## 5. 隔离：旧系统 / rebuild
（图 28；`*_rebuild` 命名、5273 vs 5173、8100、不要 down -v）

## 6. 测试金字塔与阶段门禁
（图 29 / 30；哪些阶段不需要三存储；782 tests 的证据等级）

## 7. 失败注入矩阵
（图 31；6 类失败 → 错误码 → UI 表现 → 测试文件）

## 8. 故障排查表
（症状 / 先查什么 / 命令 / 修复 / 证据）

## 9. 本机边界与未验证清单
（Docker socket、dw_reader、LLM、浏览器；标 ⚪）

## 10. 上线前检查清单
（20 项，可勾选）
```

## 必须产出 B：`90-appendix.md`（4,000–6,000 汉字）

结构：

```markdown
# 附录

## A. 32 张图索引
（编号 / 标题 / 角度 / 源文件 / 一句话）

## B. 12 个步骤
（id / label / 条件执行 / 证据）

## C. 16 个错误码
（code / label / class / retryable / 用户看到什么）

## D. 5 表 24 列 6 指标
（表名 / 粒度 / 关键列；指标 / 公式 / 粒度）

## E. 命令速查
（make stage0–stage7、docker-*、常用诊断）

## F. 术语表
（契约、构建时、查询时、召回、值域、manifest、SSE、幂等、只读执行器……）

## G. 文件地图
（路径 / 作用 / 什么时候读）

## H. 证据台账
（✅ / 🟡 / ⚪ 三类，逐条列）
```

要求：

- 表格优先；每张表不超过 20 行，超出拆表。
- 命令必须逐字准确；端口、服务名、卷名与 `compose.yaml` 一致。
- 错误码表必须覆盖 16/16，class 与 `contracts/errors.yaml` 一致。
- 不要声称 Docker 全栈已跑通；本机未验证的标 ⚪。
- 图引用用相对路径；附录 A 只列路径，不嵌图。

## 约束

- 只写 `design/book/chapters/40-ops.md` 与 `design/book/chapters/90-appendix.md`。
- 不要改源码、契约、其他章节、图源。
- 中文教学语气；表格清晰；不要营销词。

## 验收

- 两个文件存在；`40-ops.md` ≥5,000 汉字，`90-appendix.md` ≥4,000 汉字。
- 错误码 16/16；步骤 12/12；图索引 32/32。
- 所有命令能在 `Makefile` / `docs/` 找到出处。
