# 去 AI 味改造交接（开发文档 + 设计文档）

## 1. 目标与规则

目标是把 `README.md`、`docs/*.md`、`design/book/chapters/*.md`、`design/diagrams/*/*.md` 的叙述文字改得更像人写的技术文档，同时不改事实、命令、计数、证据和边界。

规则落在 `design/skills/de-ai-writing.md`，来源是 `humanizer` v3.1（MIT）的结构规则，加上中文技术写作里的高频 AI 腔清单。没有安装第三方仓库，也没有把外部 skill 直接塞进项目。

规则删掉四种东西：

- 没有新信息的开场、总结和金句；
- 「不是 X 而是 Y」这种先立靶子再抬后半句的句式；
- 「首先 / 其次 / 最后」式的机械路标；
- 装饰性加粗、空泛动词和伪深刻判断。

硬边界写在规则文件里：代码块、行内代码、命令、路径、表名、列名、错误码、计数、图号、证据标记不动；不新增事实；不删安全警告和边界说明。

## 2. 分工与产出

| 工作 | 执行者 | 范围 | 结果 |
|---|---|---|---|
| 开发文档 | qoder | `README.md` + `docs/*.md`（6 个文件） | 35 行增删，事实与代码零漂移 |
| 设计书稿 | codebuddy | `design/book/chapters/*.md`（6 个文件） | 86 行增、92 行删，「不是 X 而是 Y」53 → 9 |
| 图说明 | codebuddy | `design/diagrams/*/*.md`（32 个文件） | 改 16 篇、25 处，`.mmd` / `.svg` 零改动 |
| 书稿复核 | qoder（只读） | 书稿 diff | 通过，无事实错误 |
| 文档复核 | codebuddy（只读） | 开发文档 diff | 发现 2 处措辞问题，已修 |

协调与终审由 opencode 终端完成，没有把改写任务派给 opencode agent。

## 3. 改动规模

### 开发文档

```text
 README.md                  |  4 ++--
 docs/DOCKER-DEPLOY.md      | 18 +++++++++---------
 docs/DOCKER-HANDOFF.md     |  8 ++++----
 docs/S7-HANDOFF.md         | 12 ++++++------
 docs/SCHEMA-CONTRACT.md    |  2 +-
 docs/SETUP-FROM-SCRATCH.md | 26 +++++++++++++-------------
 6 files changed, 35 insertions(+), 35 deletions(-)
```

### 设计书稿

| 文件 | 增 / 删 | 代码围栏 | 「不是 X 而是 Y」 |
|---|---:|---:|---:|
| `00-front.md` | 13 / 17 | 2 → 2 | 4 → 1 |
| `10-s0-s4.md` | 23 / 23 | 52 → 52 | 15 → 2 |
| `20-s5-s8.md` | 25 / 25 | 56 → 56 | 19 → 3 |
| `30-atlas.md` | 7 / 7 | 0 → 0 | 3 → 0 |
| `40-ops.md` | 13 / 13 | 4 → 4 | 9 → 2 |
| `90-appendix.md` | 5 / 5 | 0 → 0 | 3 → 1 |
| **合计** | **86 / 92** | **114 → 114** | **53 → 9** |

### 图说明

改了 16 篇，共 25 处，都是单句级轻改。`.mmd` 和 `.svg` 没有改动，图号、标题、证据行号、计数、表名、错误码保持原样。

## 4. 验收结果

### 开发文档

逐文件对照 `/tmp/opencode/baseline`：

| 检查项 | 结果 |
|---|---|
| 代码块内容 | 6 个文件逐块逐字相同 |
| 代码围栏数 | 16 / 24 / 26 / 18 / 2 / 96，与改前相同 |
| 行内代码集合 | 6 个文件相同 |
| 数字集合 | 6 个文件相同 |
| 标题与表格行数 | 相同 |
| ✅ / 🟡 / ⚪ | 计数相同，含标记的行文本未变 |
| 总行数 | 256 / 297 / 354 / 484 / 164 / 1131，与改前相同 |

### 设计书稿

| 检查项 | 结果 |
|---|---|
| 代码块 | 26 块逐字相同 |
| 标题 | 6 个文件的标题列表完全一致 |
| 数字 | 数字多重集完全一致 |
| 行内代码 | 多重集完全一致 |
| 表格行数 | 相同 |
| 图片链接 | 32 条全部指向存在的文件 |

### 图说明

| 检查项 | 结果 |
|---|---|
| 模板字段 | 16 篇被改文件仍保留原有字段 |
| `.mmd` / `.svg` | 没有文件在运行期间被修改 |
| 图号 / 证据行号 | 未变 |

## 5. 复核发现与修复

文档复核发现 2 处措辞问题，已修：

1. `docs/DOCKER-HANDOFF.md`：初稿把「容器化改造本身没有功能性缺陷」删成「容器化改造没有功能性缺陷」，并把「问题集中在两处」改成「9 类问题都在两处」。这是论断强化。已补回「本身」，把「都在两处」改回「集中在两处」。
2. `docs/S7-HANDOFF.md`：初稿删掉了「记录设计决定」这一内容承诺。已补回「记录设计决定，也记录已经做完什么、为什么这么做」。

书稿复核判定通过。复核只指出少量限定词强弱变化，没有事实错误、证据标记误标或图号漂移。

## 6. 未做与边界

- `design/` 在当前工作树是未跟踪目录，`git diff` 看不到其中的改动。所有书稿与图说明的对照都使用 `/tmp/opencode/baseline/` 快照，不用 `git diff` 判断。
- 没有跑全量后端 / 前端测试。这次只改 Markdown 叙述，没有动源码、契约、命令和 `.mmd` / `.svg`；代码块与数字的多重集比对已经覆盖了主要风险。
- `design/STYLEGUIDE.md`、`design/WBS.md`、`design/inventory/facts.md` 没有改。它们是规范与事实底稿，不属于这次「去 AI 味」的改写对象。
- `design/diagrams/02-runtime/` 的 7 篇时序说明原本就用「参与者 / 主线 / 证据 / 边界」长版结构，没有强行套六段模板；`24-error-taxonomy.md` 原本就少一个「关键元素」字段。两者都是改前状态，不是这次引入的问题。
- `design/diagrams/00-overview/` 下没有 `.md`，只有 `test.mmd` / `test.svg`，所以图说明实际覆盖 01–06 共 32 篇。

## 7. 复跑检查

```bash
cd /home/zhensirong/VM-Share/DSWS-design

# 开发文档：代码块 / 数字 / 标题 / 行内代码与基线一致
python3 - <<'PY'
from pathlib import Path
import re, collections
base = Path('/tmp/opencode/baseline')
files = ['README.md'] + [f'docs/{p.name}' for p in sorted((base / 'docs').glob('*.md'))]
for f in files:
    b = (base / f).read_text(encoding='utf-8')
    c = Path(f).read_text(encoding='utf-8')
    assert re.findall(r'```.*?```', b, re.S) == re.findall(r'```.*?```', c, re.S), f
    assert collections.Counter(re.findall(r'(?<![\w.])\d+(?:\.\d+)?(?![\w.])', b)) == collections.Counter(re.findall(r'(?<![\w.])\d+(?:\.\d+)?(?![\w.])', c)), f
print('docs invariants ok')
PY

# 书稿：图片链接都存在
python3 - <<'PY'
from pathlib import Path
import re
for f in sorted(Path('design/book/chapters').glob('*.md')):
    for m in re.finditer(r'!\[[^\]]*\]\(([^)]+)\)', f.read_text(encoding='utf-8')):
        assert (f.parent / m.group(1)).resolve().exists(), (f, m.group(1))
print('image links ok')
PY
```

## 8. 相关文件

- 规则：`design/skills/de-ai-writing.md`
- 本交接：`design/inventory/handoff-de-ai.md`
- 基线快照：`/tmp/opencode/baseline/`（临时目录，不随仓库提交）
