"""Row-level checks via Databricks Labs DQX. Runtime-only.

Runs DQX metadata checks, splits into valid/quarantine, and turns each check
into a common result row (actual = number of rows that failed that check).
"""
from datetime import datetime
from typing import Optional

from pyspark.sql import DataFrame, SparkSession, functions as F

from databricks.sdk import WorkspaceClient
from databricks.labs.dqx.engine import DQEngine

from dq_framework.core.config import Config
from dq_framework.core.results import build_result_row

# DQX writes failures into these result columns (maps keyed by check name).
_RESULT_COLS = ["_errors", "_warnings"]


def _failed_row_count(quarantine: DataFrame, check_name: str) -> int:
    present = [c for c in _RESULT_COLS if c in quarantine.columns]
    if not present:
        return 0
    predicate = None
    for c in present:
        cond = F.col(c).getItem(check_name).isNotNull()
        predicate = cond if predicate is None else (predicate | cond)
    return quarantine.filter(predicate).count()


def run(
    spark: SparkSession,
    cfg: Config,
    *,
    run_id: str,
    run_ts: datetime,
    trigger: str,
    df: Optional[DataFrame] = None,
):
    """Return (valid_df, quarantine_df, result_rows).

    `df` is supplied when called inline from a pipeline notebook; otherwise the
    input is read from the config's `input.table` (falling back to `target`).
    """
    if df is None:
        source = cfg.raw.get("input", {}).get("table", cfg.target)
        df = spark.read.table(source)

    checks = cfg.raw["checks"]
    engine = DQEngine(WorkspaceClient())
    valid_df, quarantine_df = engine.apply_checks_by_metadata_and_split(df, checks)
    quarantine_df = quarantine_df.cache()

    rows = []
    for chk in checks:
        failed = _failed_row_count(quarantine_df, chk["name"])
        rows.append(build_result_row(
            run_id=run_id, run_ts=run_ts, trigger=trigger, target=cfg.target,
            check_type="rowlevel", check_name=chk["name"],
            severity=chk.get("criticality", "error"),
            status="fail" if failed > 0 else "pass",
            actual=failed, expected=0,
            details={"failed_rows": failed} if failed else None,
        ))
    return valid_df, quarantine_df, rows
