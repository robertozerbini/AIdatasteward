"""Common result-row assembly — pure, no Spark.

Every check kind (rowlevel / endpoint / kpi) emits rows in this single shape so
they can share one `dq_results` Delta table, one dashboard, and one alert.
"""
import json
from datetime import datetime
from typing import Any, Optional

RESULT_COLUMNS = [
    "run_id",
    "run_ts",
    "trigger",
    "target",
    "check_type",
    "check_name",
    "severity",
    "status",
    "expected",
    "actual",
    "details",
    "gated",
]

# Spark DDL for the results table, kept next to the columns it describes.
RESULT_TABLE_DDL = (
    "run_id string, run_ts timestamp, trigger string, target string, "
    "check_type string, check_name string, severity string, status string, "
    "expected double, actual double, details string, gated boolean"
)


def _as_float(v: Optional[Any]) -> Optional[float]:
    return None if v is None else float(v)


def build_result_row(
    *,
    run_id: str,
    run_ts: datetime,
    trigger: str,
    target: str,
    check_type: str,
    check_name: str,
    severity: str,
    status: str,
    expected: Optional[Any] = None,
    actual: Optional[Any] = None,
    details: Optional[Any] = None,
) -> dict:
    return {
        "run_id": run_id,
        "run_ts": run_ts,
        "trigger": trigger,
        "target": target,
        "check_type": check_type,
        "check_name": check_name,
        "severity": severity,
        "status": status,
        "expected": _as_float(expected),
        "actual": _as_float(actual),
        # A row gates only when it is an error-severity failure.
        "details": None if details is None else json.dumps(details, default=str),
        "gated": status == "fail" and severity == "error",
    }
