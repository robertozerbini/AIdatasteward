from datetime import datetime, timezone

from dq_framework.core.results import build_result_row, RESULT_COLUMNS


def _row(**over):
    base = dict(
        run_id="r1",
        run_ts=datetime(2026, 7, 1, tzinfo=timezone.utc),
        trigger="pipeline",
        target="prod.gold.orgstrc",
        check_type="rowlevel",
        check_name="org_key_unique",
        severity="error",
        status="pass",
    )
    base.update(over)
    return build_result_row(**base)


def test_row_has_exactly_the_schema_columns():
    assert set(_row().keys()) == set(RESULT_COLUMNS)


def test_numeric_fields_coerced_to_float():
    r = _row(status="fail", expected=100, actual=103)
    assert r["expected"] == 100.0 and isinstance(r["expected"], float)
    assert r["actual"] == 103.0 and isinstance(r["actual"], float)


def test_missing_numeric_fields_are_none():
    r = _row()
    assert r["expected"] is None
    assert r["actual"] is None


def test_error_failure_is_flagged_gated():
    assert _row(status="fail", severity="error")["gated"] is True


def test_warn_failure_is_not_gated():
    assert _row(status="fail", severity="warn")["gated"] is False


def test_pass_is_not_gated():
    assert _row(status="pass", severity="error")["gated"] is False


def test_details_is_stringified():
    r = _row(details={"failed_rows": 5})
    assert isinstance(r["details"], str)
    assert "failed_rows" in r["details"]
