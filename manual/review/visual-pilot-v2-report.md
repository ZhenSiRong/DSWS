# p00–p02 页首图 v2：实体 / 喻体对照（待用户确认）

> 用户反馈 v1「没用图像生成、太草率」；改为：**左实体（真实对象+职能+命令）/ 右喻体（AI 插画场景+对应职能映射）**，文字全部 HTML 实时可编辑，插画由 Seedream 生成、可重生成。

## 每页结构

| 页 | 左栏（实体） | 右栏（喻体） | 映射 |
| - | - | - | - |
| p00 | Docker / uv / Node+npm / GNU Make / curl / Git 六张工具卡（职责 + 命令） | 装修前验房插画（Seedream，无文字） | ①逐件检查=六件工具各司其职 ②看齐不齐=make doctor ③检查完=12/12 再开工 |
| p01 | lab-mysql 容器 / 宿主机 / 127.0.0.1 三张卡 | 集装箱 vs 笔记本电脑上的房子 | ①集装箱门牌=容器自己的 127.0.0.1 ②房子在电脑上=宿主机 ③箱门只对码头开=3307 只绑本机 |
| p02 | fixtures/dw.sql / 5 张表 / 115 行 三张卡 | 仓库五排货架 + 叉车入库 | ①货架分区=5 张表 ②叉车搬货=一条命令灌 dw.sql ③入库盘点=5 表/115 行/华北 19 |

## 产物

- `manual/designs/page-00…02/index.html`（实体/喻体两栏 + 实时文本）
- `manual/designs/page-00…02/editor.html`（可拖拽/改字/导出）
- `manual/designs/page-00…02/art/metaphor.jpeg` + `art-prompt.md`（Seedream 端点/尺寸/prompt 留档）
- `manual/images/page-00…02-visual.webp`（1600×1000，渲染产物）
- `manual/designs/data/page-00…02.json`（文案/卡片/映射数据）

## 图像生成说明（诚实）

- 生成端点：`ep-20261109172906-d7fr4`（doubao-seedream-5-0-flash-260915），1536×1024；
- 本机 `--input @本地参考图` 做图生图会报 `tos pre-sign requires SSO login`，**本版未用旧图做参考**，是纯 prompt 新生成；旧 AI 漫画仍在 `manual/images/archive/comics-v1/`；
- 若要「加工旧图」而不是重新生成，需要先登录 SSO（或换可用的图生图工具），这一点请你定。

## 闸门

```
audit_book 24/24；verify --fast T0 PASS；make verify T1 PASS；make audit 5/5
render_read 00 01 02 已重生成
```

## 待确认

1. 左实体 / 右喻体 + ①②③ 映射的结构行不行？
2. 插画风格（黑白线稿 + 单橙）是否够"教材插图"质感？
3. 若无 SSO，是否接受"新生成"而非"加工旧图"？
4. 通过后，剩余 21 页按同结构铺：每页要一个喻体场景 + 3–5 条映射（工作量主要在喻体选择与生图）。
