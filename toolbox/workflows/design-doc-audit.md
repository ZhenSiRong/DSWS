# 设计文档审计工作流（design-doc-audit）

> 触发方式：**主动触发**；不设长期定时任务（用户明确：这两天过后可能不用）。
> 目标：检查已有设计生长产物的 claim 是否还成立、证据是否过期、是否出现“行业答案”。
> 产出：一份 stale/broken/unknown 清单；不重画图。

## 1. 触发

- 用户说“审计设计文档 / 查设计 claim”时；
- 或某条链完成、准备合入 30 页设计文档前；
- 不自动定时跑。

## 2. 输入

```text
materials/design/decision-growth/*/claims.yaml
materials/design/decision-growth/*/spread.png
system/ 相关源码与契约
tutorial/ 相关页面与证据截图
```

## 3. 步骤

1. **来源漂移**：对每条 claim 的 source 检查文件是否存在、行号/哈希是否变化；
2. **probe 重跑**：只跑 claim 声明的 probe；失败即 stale；
3. **ablation 抽查**：每条 A 类链至少抽 1 条 ablation，确认“拆掉会红”仍成立；
4. **参数误标**：扫描“1 次/固定 N”等当前值是否仍被写成设计原则；
5. **行业答案扫描**：标出无本地文件/数字/失败/被放弃选项的段落；
6. **产物检查**：PNG 文件存在、尺寸/文字未变空、链接可达；
7. 输出 `audit-brief.md`：按 `stale / broken / unknown / wording` 分组，每组一条一句话 + 路径。

## 4. 检查点

- 默认无 checkpoint；产出的 brief 直接给用户。
- 只有当发现 **安全相关 claim 失效**（只读账号、策略拒绝、重试边界）时，立即停并升级给用户，不等批量审计结束。

## 5. Definition of done

- [ ] 每条 claim 都被检查过，或明确 skipped + 原因；
- [ ] 所有 stale/broken 都带路径与复现命令；
- [ ] 没有自动改文件；只给清单；
- [ ] `audit-brief.md` 落盘。

## 6. 明确不做

- 不重画 PNG；
- 不自动改 claims 状态；
- 不把“这个图看起来还行”当验证。
