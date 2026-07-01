"""Comparison + schema-matching helpers for endpoint result checks — pure.

Kept out of the Spark adapter so the (surprisingly bug-prone) comparison and
schema-diff logic is unit-tested in isolation.
"""
import operator

_OPS = {
    ">": operator.gt,
    ">=": operator.ge,
    "<": operator.lt,
    "<=": operator.le,
    "==": operator.eq,
    "!=": operator.ne,
}


def compare_op(actual, op: str, value) -> bool:
    if op not in _OPS:
        raise ValueError(f"unknown operator: {op!r} (expected one of {list(_OPS)})")
    return _OPS[op](actual, value)


def schema_matches(actual_cols, expected_cols):
    """Return (ok, missing, extra).

    ok is True when every expected column is present (extra columns are allowed
    but reported). Order-independent.
    """
    actual = list(actual_cols)
    missing = [c for c in expected_cols if c not in actual]
    extra = [c for c in actual if c not in expected_cols]
    return (len(missing) == 0, missing, extra)
