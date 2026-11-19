# TRAPS · 环境陷阱表（重放报告实测）

> 每行 = 一个会让人卡住 >1 分钟的环境坑；出处写 `review/replay-page-XX.md:行`，路径相对本目录（`manual/`）。
> 新坑按同一格式追加；grep 不到出处的不收。页面正文不复述这些解释。

| 现象 | 原因 | 修法 | 证据来源 |
|---|---|---|---|
| 1. `uv run` 按本机镜像源重写 `backend/uv.lock`，工作区变脏、`lab reset` 也回不来 | `make stage4/5/6-ui/7` 里的 `uv run` 重写锁文件（lab 白名单不含它） | 跑完 `git checkout -- backend/uv.lock`；Makefile 改用 `uv run --frozen` | `review/replay-page-15.md:27,68`、`review/replay-page-19.md:22`、`review/replay-page-20.md:25`、`review/replay-page-21.md:25` |
| 2. `cd backend && ...` 跑完 shell 停在 `backend/`，后续 `scripts/lab`、`backend/.venv/...` 全 exit 127 | `&&` 不回退目录；页面命令块没有 `cd ..` 回仓库根 | 一律写子 shell `(cd backend && ...)`；整段跑完 `pwd` 必须在仓库根 | `review/replay-page-11.md:25` |
| 3. 门禁明明红，`echo $?` 却是 0 | 管道末尾的命令是 `tail`，`$?` 拿到的是它的 0 | 看 `${PIPESTATUS[0]}`，或命令后加 `; echo "gate=${PIPESTATUS[0]}"` | `review/replay-page-19.md:23` |
| 4. 磁盘 ≥85% 时 ES 报 `low disk watermark`（副本不分配）；盘再紧，init 建索引与整栈验收会撞水位 | ES 默认低/高水位 85%/90%；一套 build + 索引再吃数 GB | 隔离栈临时关 watermark（`compose.lab-ui.yaml` 有先例）或清盘；85%+ 不跑整栈 | `review/replay-page-14.md:69`、`review/replay-page-13.md:49` |
| 5. 起栈报端口占用、smoke 连不上 | 3306/9200/6333/8100/8080 常被既有栈占（`make doctor` 只查 3307/8000/8081） | 改 `.env` 的 `*_HOST_PORT`（含 `FRONTEND_BIND`），别改 `compose.yaml` 的默认 | `review/replay-page-13.md:29,44` |
| 6. DB 被改（如 `GRANT ALL`）、`uv.lock` 被改，`lab reset` 后仍红/仍脏 | 快照只覆盖白名单文件；数据库、容器、卷、`uv.lock` 都不在内 | DB 重灌 `fixtures/`（`make docker-reset` 后重灌）；`uv.lock` 用 git checkout | `review/replay-page-18.md:16,17`、`review/replay-page-19.md:15`（边界见 `docs/lab.md` §限制） |
| 7. `record_sse --check` 红后照提示重录，`--check` 变绿但判据失效 | 重录 = 用当前坏代码覆盖夹具，噪音被写成「基线」→ 假绿 | 不重录；`scripts/lab reset <快照> --yes` 还原代码后重跑 `--check` | `review/replay-page-20.md:25` |
| 8. 拆一刀红得比页面多，或实验结论失真 | 同名代码/公式在多处（`policy.py:460` 也有一行同款；GMV 公式还出现在 AOV、件单价） | 页面写文件名+行号；只改那一行，禁用全局替换/模糊搜索 | `review/replay-page-16.md:31`、`review/replay-page-15.md:33` |
| 9. 本页一开头就红，且红法与本页判据不符 | 上一页「拆一刀」没还原（P16→17、P19→20、P20→21） | 每页开头给一条可执行检查（`grep`/`--check`）；不对先 `scripts/lab reset <上一页>-before --yes` | `review/replay-page-17.md:33`、`review/replay-page-20.md:24`、`review/replay-page-21.md:27` |
| 10. 首次 `make docker-up` 十几分钟、`ps` 迟迟不 healthy，像卡死 | 首次构建/拉镜像约 8 分钟；ES 重启约 20–22s 才 healthy | 等 `docker compose ps` 出现 `(healthy)` 再跑下一步；失败看 `ERROR` 行与 `docker compose logs` | `review/replay-page-13.md:28,45`、`review/replay-page-14.md:32` |
| 11. `lab save` 报「名字要以字母或数字开头」或「同名快照已存在」；换名后 reset 回错快照 | 快照名只允许字母/数字/点/下划线/短横线且须字母数字开头；同名拒绝覆盖；换名后下文 reset 没跟着换 | 换新名重做，并把后续 `reset <旧名>` 一起换；旧快照没有删除命令 | `review/replay-page-10.md:36`、`review/replay-page-15.md:28`、`review/replay-page-17.md:34` |
| 12. 跨页同词不同义（`L1`、`黄金集` 有 20/10 题两说），读者对不上 | 术语没有单一定义位 | 查 `GLOSSARY.md` 流程术语；`L1–L4`/`A0–A9` 口径看 `manual/README.md` 与 D44 | `review/replay-page-11.md:22`、`review/replay-page-15.md:31` |
