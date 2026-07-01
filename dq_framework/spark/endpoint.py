"""Endpoint checks: execute a stored procedure and validate its result set.

Runtime-only. Supported result-check types:
  - count     : compare row_count with {op, value}
  - schema    : assert expected `columns` are present
  - freshness : assert max(`column`) is within `max_age_hours` of now
"""
from datetime import datetime, timedelta, timezone

from pyspark.sql import SparkSession, functions as F

from dq_framework.core.config import Config
from dq_framework.core.ops import compare_op, schema_matches
from dq_framework.core.results import build_result_row


def _evaluate(check: dict, result_df) -> tuple[str, float | None, float | None, dict | None]:
    """Return (status, expected, actual, details) for one result check."""
    ctype = check["type"]

    if ctype == "count":
        actual = result_df.count()
        ok = compare_op(actual, check["op"], check["value"])
        return ("pass" if ok else "fail"), float(check["value"]), float(actual), None

    if ctype == "schema":
        ok, missing, extra = schema_matches(result_df.columns, check["columns"])
        details = None if ok else {"missing": missing, "extra": extra}
        return ("pass" if ok else "fail"), None, None, details

    if ctype == "freshness":
        col = check["column"]
        max_ts = result_df.agg(F.max(col).alias("m")).collect()[0]["m"]
        cutoff = datetime.now(timezone.utc) - timedelta(hours=check["max_age_hours"])
        if max_ts is None:
            return "fail", None, None, {"reason": "no rows / null timestamp"}
        if max_ts.tzinfo is None:
            max_ts = max_ts.replace(tzinfo=timezone.utc)
        ok = max_ts >= cutoff
        return ("pass" if ok else "fail"), None, None, {"max_ts": str(max_ts)}

    raise ValueError(f"unknown endpoint result-check type: {ctype!r}")


def run(spark: SparkSession, cfg: Config, *, run_id, run_ts: datetime, trigger):
    """Execute the endpoint and return (result_rows,)."""
    result_df = spark.sql(cfg.raw["execute"]).cache()

    rows = []
    for check in cfg.raw["result_checks"]:
        status, expected, actual, details = _evaluate(check, result_df)
        rows.append(build_result_row(
            run_id=run_id, run_ts=run_ts, trigger=trigger, target=cfg.target,
            check_type="endpoint", check_name=check["name"],
            severity=check.get("severity", "error"),
            status=status, expected=expected, actual=actual, details=details,
        ))
    return rows
