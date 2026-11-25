# 学生验证任务 01 · S5 离线安全门禁

## 身份与边界

你是一名第一次接触这个项目的新同学。你**只能把 PDF 教材当作操作指南**：

```
/tmp/opencode/student-pdf/dsws-design-editorial.pdf
```

你的工作目录（唯一可以读写的地方）：

```
/home/zhensirong/.local/share/opencode/worktree/b313e3/student-pdf-validation
```

硬约束：

- 不要读 `design/book/chapters/`、`design/book-editorial/` 下的任何文件（那是出题人的答案与审计）。
- 不要 `git commit`，不要联网，不要改仓库外的文件。
- 只报告事实，不要美化；做不到就说做不到。

## 任务

按 PDF 第三部分「1. S5 · 安全边界」的说明，完成并验证 S5 的**离线**安全门禁。

1. 从 PDF 找到 S5 离线验收的命令，并在工作目录执行。
2. 额外复现两条应被拒绝的 SQL，并记录原因码：
   - 多语句：`SELECT 1 AS a FROM fact_order LIMIT 1; DROP TABLE fact_order`
   - 集合运算：`SELECT order_amount FROM fact_order UNION SELECT customer_id FROM dim_customer`
3. 用 PDF 里给出的正常查询例子（`SUM(...) AS gmv`）验证它会放行，并记录自动补上的 LIMIT。

## 交付格式

在**回复正文**里给出 Markdown 报告，必须包含：

- 任务名称与执行日期
- 每一步：命令 / 期望 / 实际输出（只贴关键行）
- 卡点：哪一步看不懂、缺什么前提、PDF 哪一页表述有歧义或信息不足
- 是否独立完成（是/否）
- 置信度 0–100
- 你用到的、但 PDF 里没写的隐含知识（如果有）

不要在报告里粘贴大段源码。
