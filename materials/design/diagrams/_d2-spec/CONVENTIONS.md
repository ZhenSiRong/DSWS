# A 类设计图 D2 图源规范（v3，2026-11-27 用户拍板）

渲染：`export PATH="$HOME/.local/bin:$PATH" && d2 --layout=elk <name>.d2 <name>.svg`（输出路径与既有 .svg 同名同目录，覆盖 mermaid 产物；.mmd 保留为历史源）。
语法注意：`style.stroke-width` 只收整数 2–3；`style.stroke-dash` 只收数值（如 3）。

## 共用暖色板（classes，逐图复制）
- gate/关卡: fill #f3ece0 · stroke #a8926a · font #4a3f2c
- pass/放行: fill #e7efe8 · stroke #2f5d46 · font #244636
- danger/拒绝: fill #f6e8e6 · stroke #a9362a · font #7c2a22
- store/存储: fill #e8eef0 · stroke #3d6270 · font #24414c（配 shape: cylinder）
- note/注释: fill #f7f4ee · stroke #b9ab93 · font #6f6557
- plain/中性: fill #fdfbf7 · stroke #6b5d49 · font #211b15

## 图形类型强区分（每图必须按类型选形，禁止全是方框+箭头）
| 类型 | 图 | 形态语汇 |
|---|---|---|
| 状态机 | 12 | 圆角框（border-radius 14）+ ●起点 + ◉双圈终态（circle 内 ◉ 字符）+ 粗箭头(2) + 唯一回退边橙虚线 stroke #c2410c dash 3 |
| 判定流程 | 22 | 六边形判定关(shape: hexagon) + 直角框 + 圆柱存储 + 绿粗(3)=通过/红细(2)=拒绝 |
| 失败矩阵 | 31 | grid 矩阵（容器 grid-rows/grid-columns，格子=小方块按结果着色） |
| 权限对照 | 23 | 左右双栏对照 + 底部结论条（danger 负例 vs pass 正例） |
| 分类树 | 24 | 树形：根→3 类容器→码芯片（chips 用小方块流式排） |
| 契约模型(ER) | 15 | shape: sql_table 实体 + 引用箭头 |
| 派生映射 | 16 | 三列管道：契约→BuildPlan→三存储，粗箭头+逐列标注写什么/不写什么 |
| 决策树 | 19 | shape: diamond 判定 + 叶子圆角框 |
| 启动时序 | 27 | 阶段泳道容器（phase 容器）+ 闸门条件箭头 + 失败停点红色支路 |
| 旅程图 | journey-map | 横向时间线 chips + 箭头 + 每步文件:符号小字 |

## 图例（每图必带）
右上角独立 cluster：`legend: "图例 · <图名>怎么读" { style.fill #faf7f0 · stroke #b9ab93 · radius 8 · direction: right }`，内含该图用到的每个形状/颜色/线型样本 + 一句用途。

## 内容纪律
- 图内容以同名 .md 与 .mmd 为准，信息只增不减（图注要点、数字、标注）；
- 文字中文，术语与 GLOSSARY 一致；完成后 grep SVG 确认关键标签在场、文件 >5KB。
