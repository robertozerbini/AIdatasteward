import pytest

from dq_framework.core.ops import compare_op, schema_matches


@pytest.mark.parametrize("actual,op,value,expected", [
    (5, ">", 0, True),
    (0, ">", 0, False),
    (0, ">=", 0, True),
    (3, "<", 5, True),
    (5, "<=", 5, True),
    (5, "==", 5, True),
    (5, "!=", 4, True),
    (5, "==", 4, False),
])
def test_compare_op(actual, op, value, expected):
    assert compare_op(actual, op, value) is expected


def test_compare_op_rejects_unknown_operator():
    with pytest.raises(ValueError, match="operator"):
        compare_op(1, "=>", 0)


def test_schema_matches_when_all_expected_present():
    ok, missing, extra = schema_matches(["a", "b", "c"], ["a", "b"])
    assert ok is True
    assert missing == []
    assert extra == ["c"]


def test_schema_reports_missing_columns():
    ok, missing, extra = schema_matches(["a"], ["a", "b"])
    assert ok is False
    assert missing == ["b"]


def test_schema_match_is_order_independent():
    ok, missing, extra = schema_matches(["b", "a"], ["a", "b"])
    assert ok is True
