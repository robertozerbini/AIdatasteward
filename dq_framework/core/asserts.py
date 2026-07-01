"""KPI ground-truth assertion logic — pure, no Spark.

Compares an actual (measured) KPI value against an expected ground-truth value,
optionally within a percentage and/or absolute tolerance. The largest of the
provided tolerances wins; with no tolerance the match must be exact.
"""
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class AssertResult:
    status: str  # "pass" | "fail"
    actual: Optional[float]
    expected: float
    diff: Optional[float]
    allowed: float


def evaluate_kpi(
    *,
    actual: Optional[float],
    expected: float,
    tolerance_pct: Optional[float] = None,
    tolerance_abs: Optional[float] = None,
) -> AssertResult:
    allowed = 0.0
    if tolerance_pct is not None:
        allowed = max(allowed, abs(expected) * tolerance_pct / 100.0)
    if tolerance_abs is not None:
        allowed = max(allowed, abs(tolerance_abs))

    # A missing measurement (e.g. KPI query returned no row) can never pass.
    if actual is None:
        return AssertResult("fail", None, expected, None, allowed)

    diff = abs(actual - expected)
    status = "pass" if diff <= allowed else "fail"
    return AssertResult(status, actual, expected, diff, allowed)
