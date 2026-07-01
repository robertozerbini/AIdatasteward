"""Unity Catalog I/O: the shared results store and the KPI ground-truth table.

Runtime-only (pyspark). All check kinds write results here so there is a single
place to alert and dashboard on.
"""
from datetime import datetime
from typing import Optional

from pyspark.sql import SparkSession

from dq_framework.core.results import RESULT_COLUMNS, RESULT_TABLE_DDL


def get_spark() -> SparkSession:
    spark = SparkSession.getActiveSession()
    if spark is None:  # pragma: no cover - runtime guard
        spark = SparkSession.builder.getOrCreate()
    return spark


def ensure_results_table(spark: SparkSession, table: str) -> None:
    spark.sql(f"CREATE TABLE IF NOT EXISTS {table} ({RESULT_TABLE_DDL}) USING DELTA")


def write_results(spark: SparkSession, table: str, rows: list[dict]) -> "DataFrame":
    """Append result rows (dicts in the common shape) to the results table."""
    ensure_results_table(spark, table)
    # Preserve column order / schema regardless of dict insertion order.
    ordered = [[r[c] for c in RESULT_COLUMNS] for r in rows]
    df = spark.createDataFrame(ordered, schema=RESULT_TABLE_DDL)
    df.write.mode("append").option("mergeSchema", "true").saveAsTable(table)
    return df


def load_ground_truth(
    spark: SparkSession, table: str, as_of: Optional[datetime] = None
) -> dict:
    """Return {kpi_name: {expected_value, tolerance_pct, tolerance_abs}} for the
    rows that are active and effective at `as_of` (defaults to now).

    Expected schema of the ground-truth table:
        kpi_name string, target string, expected_value double,
        tolerance_pct double, tolerance_abs double,
        effective_from timestamp, effective_to timestamp, active boolean
    """
    as_of = as_of or datetime.utcnow()
    df = spark.read.table(table)
    df = df.where(
        "active = true "
        f"AND effective_from <= timestamp('{as_of.isoformat()}') "
        f"AND (effective_to IS NULL OR effective_to > timestamp('{as_of.isoformat()}'))"
    )
    out = {}
    for r in df.collect():
        out[r["kpi_name"]] = {
            "expected_value": r["expected_value"],
            "tolerance_pct": r["tolerance_pct"] if "tolerance_pct" in r else None,
            "tolerance_abs": r["tolerance_abs"] if "tolerance_abs" in r else None,
        }
    return out
