"""S6 · 校正闭环。

路线图 S6 的验收：

    > 校正后 SQL 必须再次过 S5 策略

所以这里最要紧的一条是：**校正不是绕过安全检查的后门**。校正器返回一条
带写操作的 SQL，闭环必须把它挡下来。

另外三条不变式：

    - 最多 1 次重试；
    - 保留原始 SQL；
    - 校正成功 → 旧 error 被清空。
"""

from __future__ import annotations

from app.agent.correct import (
    FixtureCorrector,
    LlmCorrector,
    build_correct_slots,
    propose_correction,
)
from app.agent.errors import build_error
from app.generate.prompts import get_prompt, render_prompt

from conftest import BROKEN_SQL, GOOD_SQL, UNKNOWN_COLUMN_SQL


def _syntax_error():
    return build_error("SQL_SYNTAX", "SQL 无法被解析", step="validate_sql")


# ---------------------------------------------------------------------------
# 槽位
# ---------------------------------------------------------------------------


def test_slots_match_the_prompt_contract(context) -> None:
    """槽位必须与 `correct_sql.prompt` 声明的完全一致。"""
    slots = build_correct_slots(context, BROKEN_SQL, "炸了")
    declared = set(get_prompt("correct_sql").slots)
    assert set(slots) == declared


def test_prompt_renders_with_the_slots(context) -> None:
    slots = build_correct_slots(context, BROKEN_SQL, "炸了")
    rendered = render_prompt("correct_sql", slots)
    assert BROKEN_SQL in rendered
    assert "炸了" in rendered


def test_prompt_exposes_allowed_columns(context) -> None:
    """校正器必须看得到可用字段，否则只能凭猜改列名。

    v2 的「哪个商品品类卖得最好」就是因为校正提示词没有字段列表，
    模型只能拒答（它不知道 order_quantity 到底在不在契约里）。
    """
    slots = build_correct_slots(context, UNKNOWN_COLUMN_SQL, "列不存在")
    rendered = render_prompt("correct_sql", slots)
    assert "fact_order.order_amount" in rendered


def test_prompt_requires_a_legal_equivalent_instead_of_refusing(context) -> None:
    """静态校验报未知列/表时，有等价字段就必须替换，不能只因为原名未知拒答。"""
    slots = build_correct_slots(context, UNKNOWN_COLUMN_SQL, "列不存在")
    rendered = render_prompt("correct_sql", slots)
    assert "SQL_UNKNOWN_COLUMN" in rendered
    assert "SQL_UNKNOWN_TABLE" in rendered
    assert "语义等价" in rendered
    assert "不得仅因为原名不在上下文里就拒答" in rendered


def test_correct_sql_prompt_is_runtime_enabled() -> None:
    """S6 起 `correct_sql` 真正进入运行时——它是闭环的一半。"""
    assert get_prompt("correct_sql").runtime is True


# ---------------------------------------------------------------------------
# 校正
# ---------------------------------------------------------------------------


def test_correction_proposes_a_new_sql(context) -> None:
    proposal = propose_correction(
        context,
        BROKEN_SQL,
        _syntax_error(),
        corrector=FixtureCorrector({"sql": GOOD_SQL}),
    )
    assert proposal.attempted is True
    assert proposal.ok is True
    assert proposal.sql == GOOD_SQL


def test_no_corrector_means_no_correction(context) -> None:
    proposal = propose_correction(
        context, BROKEN_SQL, _syntax_error(), corrector=None
    )
    assert proposal.attempted is False
    assert proposal.ok is False
    assert proposal.error is not None


def test_non_retryable_error_is_not_corrected(context) -> None:
    """策略拒绝不进闭环——拿被拒的 SQL 去问模型等于给注入开口子。"""
    rejected = build_error("SQL_REJECTED", "被拒了", reason_code="SQL_NOT_READ_ONLY")
    proposal = propose_correction(
        context,
        UNKNOWN_COLUMN_SQL,
        rejected,
        corrector=FixtureCorrector({"sql": GOOD_SQL}),
    )
    assert proposal.attempted is False
    assert proposal.error is rejected


def test_corrector_refusal_keeps_the_original_error(context) -> None:
    """校正失败 → 根因没变，错误也不该变。"""
    error = _syntax_error()
    proposal = propose_correction(
        context,
        BROKEN_SQL,
        error,
        corrector=FixtureCorrector(
            {"refusal": {"code": "INVALID_OUTPUT", "reason": "不会改"}}
        ),
    )
    assert proposal.ok is False
    assert proposal.error is error
    assert "不会改" in proposal.note


def test_corrector_crash_keeps_the_original_error(context) -> None:
    class Boom:
        name = "boom"

        def correct(self, context, prompt, sql, error):
            raise RuntimeError("炸了")

    error = _syntax_error()
    proposal = propose_correction(context, BROKEN_SQL, error, corrector=Boom())
    assert proposal.ok is False
    assert proposal.error is error
    assert "炸了" in proposal.note


def test_corrector_with_invalid_payload_keeps_the_original_error(context) -> None:
    error = _syntax_error()
    proposal = propose_correction(
        context, BROKEN_SQL, error, corrector=FixtureCorrector({"sql": 123})
    )
    assert proposal.ok is False
    assert proposal.error is error


def test_llm_corrector_reuses_the_generator_interface(context) -> None:
    """校正器与生成器共用一个接口——差别只是提示词。"""
    calls: list[str] = []

    class Fake:
        name = "fake"

        def generate(self, ctx, prompt):
            calls.append(prompt)
            return {"sql": GOOD_SQL}

    corrector = LlmCorrector(Fake())
    payload = corrector.correct(context, "PROMPT", BROKEN_SQL, "炸了")
    assert payload == {"sql": GOOD_SQL}
    assert calls == ["PROMPT"]


# ---------------------------------------------------------------------------
# 商品级问数的校正闭环
# ---------------------------------------------------------------------------

PRODUCT_QUERY = "查询销售额最高的前5个商品"

#: 引用了上下文里不存在的商品编码列。
PRODUCT_UNKNOWN_COLUMN_SQL = (
    "SELECT dim_product.product_code AS `商品编码`, "
    "SUM(fact_order.order_amount) AS `销售额` "
    "FROM fact_order "
    "JOIN dim_product ON fact_order.product_id = dim_product.product_id "
    "GROUP BY dim_product.product_code "
    "ORDER BY `销售额` DESC LIMIT 5"
)

#: 用上下文里的合法列替换后的 SQL。
PRODUCT_FIXED_SQL = (
    "SELECT dim_product.product_name AS `商品名称`, "
    "SUM(fact_order.order_amount) AS `销售额` "
    "FROM fact_order "
    "JOIN dim_product ON fact_order.product_id = dim_product.product_id "
    "GROUP BY dim_product.product_name "
    "ORDER BY `销售额` DESC LIMIT 5"
)


def test_product_unknown_column_is_corrected_and_revalidated() -> None:
    """上下文有合法替代字段时，校正结果必须能重新过校验。"""
    from app.agent.validate import validate_sql
    from app.generate.context import build_offline_context

    context = build_offline_context(PRODUCT_QUERY)
    assert "dim_product.product_name" in {
        column.id for column in context.columns
    }

    error = validate_sql(PRODUCT_UNKNOWN_COLUMN_SQL, context, PRODUCT_QUERY)
    assert error is not None
    assert error.code == "SQL_UNKNOWN_COLUMN"

    proposal = propose_correction(
        context,
        PRODUCT_UNKNOWN_COLUMN_SQL,
        error,
        corrector=FixtureCorrector({"sql": PRODUCT_FIXED_SQL}),
    )
    assert proposal.ok is True
    # 编排器在 validate_sql 步骤重跑 guard + policy；这里直接证明闭环。
    assert validate_sql(proposal.sql or "", context, PRODUCT_QUERY) is None


def test_refusal_without_a_legal_alternative_keeps_the_original_error(context) -> None:
    """上下文里没有可替换的字段时，拒答不能掩盖原始错误。"""
    from app.agent.validate import validate_sql

    broken = (
        "SELECT dim_product.product_name AS `商品名称`, "
        "SUM(fact_order.order_amount) AS `销售额` "
        "FROM fact_order "
        "JOIN dim_product ON fact_order.product_id = dim_product.product_id "
        "GROUP BY dim_product.product_name "
        "ORDER BY `销售额` DESC LIMIT 5"
    )
    error = validate_sql(broken, context, "华北销售额")
    assert error is not None
    assert error.code == "SQL_UNKNOWN_TABLE"

    proposal = propose_correction(
        context,
        broken,
        error,
        corrector=FixtureCorrector(
            {
                "refusal": {
                    "code": "UNKNOWN_TABLE",
                    "reason": "可用表里没有 dim_product，无法补 JOIN。",
                }
            }
        ),
    )
    assert proposal.ok is False
    assert proposal.error is error
    assert "UNKNOWN_TABLE" in proposal.note
    assert "无法补 JOIN" in proposal.note
