"""KPI asserts: compute each KPI and compare to UC ground-truth. Runtime-only.

Each KPI in the config has a `query` returning a single scalar value. Expected
values + tolerances come from the ground-truth reference table, so stewards can
update targets without a code change.
"""
from datetime import datetime
from typing import Optional

from pyspark.sql import SparkSession

from dq_framework.core.config import Config
from dq_framework.core.asserts import evaluate_kpi
from dq_framework.core.results import build_result_row
from dq_framework.spark.store import load_ground_truth


def _scalar(spark: SparkSession, query: str) -> Optional[float]:
    rows = spark.sql(query).collect()
    if not rows or rows[0][0] is None:
        return None
    return float(rows[0][0])


def run(spark: SparkSession, cfg: Config, *, run_id, run_ts: datetime, trigger):
    """Return (result_rows,)."""
    truth = load_ground_truth(spark, cfg.raw["ground_truth_table"], as_of=run_ts)

    rows = []
    for kpi in cfg.raw["kpis"]:
        name = kpi["name"]
        gt = truth.get(name)
        if gt is None:
            # No active ground truth defined -> surface as an error, don't skip.
            rows.append(build_result_row(
                run_id=run_id, run_ts=run_ts, trigger=trigger, target=cfg.target,
                check_type="kpi", check_name=name, severity="error",
                status="fail", details={"reason": "no active ground-truth row"},
            ))
            continue

        actual = _scalar(spark, kpi["query"])
        res = evaluate_kpi(
            actual=actual,
            expected=gt["expected_value"],
            tolerance_pct=gt.get("tolerance_pct"),
            tolerance_abs=gt.get("tolerance_abs"),
        )
        rows.append(build_result_row(
            run_id=run_id, run_ts=run_ts, trigger=trigger, target=cfg.target,
            check_type="kpi", check_name=name,
            severity=kpi.get("severity", "error"),
            status=res.status, expected=res.expected, actual=res.actual,
            details={"diff": res.diff, "allowed": res.allowed},
        ))
    return rows
