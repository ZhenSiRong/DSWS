# 基线测量发现（2026-11-09）

## 1. 参考基线

| 项 | 结果 |
|---|---|
| 干净树 | `95ab5f6`（`/tmp/opencode/ref-baseline`），脏工作树不参与 |
| C1 契约 | 12 节点，与 `contracts/steps.yaml` 完全一致 |
| C2b 生成基线 | 10/10（2 条拒答） |
| C2r 召回黄金集 | 通过 |
| C3a 校正闭环（脚本化） | 30 passed |
| C3d 检测判据 | 20/20，与真实 guard/policy 一致 |
| C4 `make stage5` | S5 PASS（36/36、11/11、8/8） |
| C5/C6 | 标题/资源 200、health 200 |

> 注意：主工作树当前是脏的（`docs/SCHEMA-CONTRACT.md` 等被改），`make stage5` 会因
> schema 文档新鲜度测试变红。**基线必须在干净 worktree 跑**，否则结论不可比。

## 2. 实模型校正（5051，8 条问题 × 3 次 = 24 次）

| 分类 | 次数 |
|---|---|
| 无需校正 | 19 |
| 校正机会（validate 先失败） | 5 |
| 校正成功（重校验 + 执行成功） | **5** |
| 校正失败 | 0 |

**校正成功率：5/5 = 100%（本次样本）。**

## 3. 两个必须写进教材的现象

### 3.1 校正不是“修好了/没修好”，是概率

同一条问题「查询销售额大于平均销售额的商品」：

- 第一次运行：`validate_sql error → correct_sql error → SQL_UNKNOWN_TABLE`
- 随后 3 次：全部 `error → correct success → validate success → run success`

单次演示会骗人。教材和验收都必须写“多次采样 + 成功率”，不能写“已修复”。

### 3.2 拒绝的层不固定，不能按问题背错误码

`UNION`、越界年份、城市粒度三条，模型直接 `LLM_REFUSAL`，根本没走到策略层，
所以对外码不是 `SQL_REJECTED`。

教材应写成：

> 同一条“危险问题”可能被三层中的任意一层拦下：模型拒答（`LLM_REFUSAL`）、
> 静态校验（`SQL_*`）、安全策略（`SQL_REJECTED`）。验收看的是**没有被执行**，
> 不是某个固定码。

这与当前书稿里“UNION → SQL_REJECTED”的单一叙事冲突，需要修。

## 4. 对一致性测试的调整

- C3 必须按 `trials >= 3` 统计，不采信单次。
- C2 的“期望码”要区分「行为期望」与「具体码期望」：安全类只断言“未执行 + 属于拒绝类”。
- C4 必须在干净树跑。

## 5. 产物

- `eval/golden.jsonl`（30 条）
- `eval/correction.jsonl`（20 条，判据已用真实 guard/policy 校验）
- `eval/correction_live.jsonl`（8 条实模型用例）
- `eval/conformance/run.py` + `reference-baseline.json`
- `eval/live-report.json`（24 次原始分类）
