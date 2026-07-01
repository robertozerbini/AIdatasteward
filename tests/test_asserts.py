import pytest

from dq_framework.core.asserts import evaluate_kpi


def test_exact_match_passes_with_no_tolerance():
    assert evaluate_kpi(actual=100.0, expected=100.0).status == "pass"


def test_mismatch_fails_with_no_tolerance():
    assert evaluate_kpi(actual=101.0, expected=100.0).status == "fail"


def test_within_percent_tolerance_passes():
    # 2% of 100 = 2.0 allowed; diff of 1.5 is within
    assert evaluate_kpi(actual=101.5, expected=100.0, tolerance_pct=2.0).status == "pass"


def test_outside_percent_tolerance_fails():
    assert evaluate_kpi(actual=103.0, expected=100.0, tolerance_pct=2.0).status == "fail"


def test_within_absolute_tolerance_passes():
    assert evaluate_kpi(actual=104.0, expected=100.0, tolerance_abs=5.0).status == "pass"


def test_boundary_is_inclusive():
    assert evaluate_kpi(actual=102.0, expected=100.0, tolerance_pct=2.0).status == "pass"


def test_result_reports_actual_expected_and_diff():
    r = evaluate_kpi(actual=103.0, expected=100.0, tolerance_pct=2.0)
    assert r.actual == 103.0
    assert r.expected == 100.0
    assert r.diff == pytest.approx(3.0)


def test_none_actual_fails_rather_than_raising():
    # a KPI query that returned no row -> actual is None -> must fail, not crash
    r = evaluate_kpi(actual=None, expected=100.0)
    assert r.status == "fail"
