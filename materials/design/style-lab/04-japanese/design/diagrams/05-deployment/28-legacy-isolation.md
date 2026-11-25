# 28 · 旧系统与 rebuild 的隔离边界

**一句话**：旧系统与 rebuild 共用同一批存储进程，但靠库名、索引名、collection 名与向量维度隔离；S2/S3 的默认目标一律带 `_rebuild`。

**这张图回答**：旧系统的 `meta` / `value_index` / `5173` / `3306` 与 rebuild 的 `*_rebuild` / `5273` / `8100` 在哪一层分开？哪些东西其实是共用的？

**图例**：蓝色=可配置的目标名（契约式入口）；青色=存储与目标；紫色=服务；灰色=旧系统边界。

**关键元素**：
- 旧系统：Web `5173`、API `8000`、MySQL 库 `meta`（5 / 24 / 2 / 2）、ES 索引 `value_index`（75 docs）、Qdrant `column_info_collection` 与 `metric_info_collection`（1024 维）。
- rebuild：Vite `5273`（容器内 nginx `8080`）、FastAPI `8100`、MySQL `meta_rebuild`（5 / 24 / 6 / 9）、ES `value_index_rebuild`（76 docs）、Qdrant `column_info_rebuild` / `metric_info_rebuild`（256 维）。
- 共用存储进程：如果本机已经在 `3306 / 9200 / 6333` 上跑着旧系统的存储，rebuild 直接探活复用，不重复 `up`；此时隔离靠**名字**而不是端口。
- 目标入口：`REBUILD_META_DB`、`REBUILD_ES_INDEX`、`REBUILD_COLUMN_COLLECTION`、`REBUILD_METRIC_COLLECTION`，默认值全部带 `_rebuild`。
- 红线：绝对不要把目标指到 `meta` / `value_index` / `*_collection`；S2 的 `--fresh` 会重建目标。

**证据**：
- `backend/app/build/config.py` 的默认值（`meta_rebuild` / `value_index_rebuild` / `column_info_rebuild` / `metric_info_rebuild`，见 `docs/SETUP-FROM-SCRATCH.md` §4 表）。
- `docs/SETUP-FROM-SCRATCH.md` §5：旧系统与 rebuild 的计数对照，以及「执行 `make stage2` / `make stage3` 后旧系统计数没有变化」（✅ 本机 2026-10-25）。
- `docs/SETUP-FROM-SCRATCH.md` §4「自定义目标时，S2 和 S3 必须用同一组变量」L918–L962。
- `README.md` L247–L248、L254–L255：只动 `*_rebuild`；端口隔离与旧系统 `8000/5173` 可同时运行。
- `docs/DOCKER-DEPLOY.md` §5：Compose 卷名带项目名前缀，`down -v` 只影响 rebuild 项目。

**边界**：名字与默认值是文件事实（✅）；「旧系统计数未变」是他机/前一轮本机记录（🟡，本次未复跑）。`3306` 不是隔离出来的：完整 Docker 部署把 MySQL 发布到 `127.0.0.1:3306`，与旧系统 MySQL 同端口时只能二选一；能共存的是 `8100 / 5273` 与旧系统 `8000 / 5173`。
