"""S6 · 失败通道。

这一层把「一次问数」从一堆函数变成一条**有名字的失败通道**：

    app.agent.errors       错误码表 + 通道错误（唯一失败形状）
    app.agent.correct      校正闭环（最多 1 次，校正后重新校验）
    app.agent.graph        12 节点 LangGraph 工作流（真正被执行）
    app.agent.orchestrator 图执行 + SSE 事件映射

S4 的生成、S5 的策略与执行都是普通函数；`graph.py` 用 LangGraph 把它们
串成 `contracts/steps.yaml` 里的 12 个节点，`orchestrator.py` 只负责把
图节点的 progress 事件翻译成 SSE，并在图结束后给出 result / error。
"""
