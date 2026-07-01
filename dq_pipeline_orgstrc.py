# Databricks notebook source
# MAGIC %md
# MAGIC # Data Quality Pipeline — DQX (org_key uniqueness)
# MAGIC
# MAGIC Validates `prod_auto.gold_virtual.eudu_mdata_dtac_orgstrc` using the
# MAGIC **Databricks Labs DQX** framework.
# MAGIC
# MAGIC - Config driven by an inline YAML string (no external files).
# MAGIC - Splits data into **valid** and **quarantine** Unity Catalog tables.
# MAGIC - Emits **summary metrics** (input / valid / quarantine / per-check) to a metrics table.
# MAGIC
# MAGIC > Requires the `databricks-labs-dqx` library installed on the cluster.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Cell 1 — Install dependency (skip if already on the cluster)

# COMMAND ----------

# MAGIC %pip install databricks-labs-dqx
# dbutils.library.restartPython()  # uncomment on first install to reload the interpreter

# COMMAND ----------

# MAGIC %md
# MAGIC ## Cell 2 — Step A: Imports

# COMMAND ----------

import uuid
import yaml
from datetime import datetime, timezone

from pyspark.sql import DataFrame, functions as F

from databricks.sdk import WorkspaceClient
from databricks.labs.dqx.engine import DQEngine

# COMMAND ----------

# MAGIC %md
# MAGIC ## Cell 3 — Configuration (YAML defined as a Python variable)
# MAGIC
# MAGIC Everything the pipeline touches is declared here — no hardcoded table names
# MAGIC live in the executable steps below.

# COMMAND ----------

CONFIG_YAML = """
# ------------------------------------------------------------------
# Data Quality pipeline configuration
# ------------------------------------------------------------------
input:
  table: prod_auto.gold_virtual.eudu_mdata_dtac_orgstrc

output:
  valid_table:      prod_auto.gold_virtual.eudu_mdata_dtac_orgstrc_valid
  quarantine_table: prod_auto.gold_virtual.eudu_mdata_dtac_orgstrc_quarantine
  metrics_table:    prod_auto.gold_virtual.dq_metrics

# DQX checks in metadata (dict) format
checks:
  - name: org_key_is_unique
    criticality: error          # error -> quarantine, warn -> kept in valid set but flagged
    check:
      function: is_unique
      arguments:
        columns:
          - org_key
"""

# COMMAND ----------

# MAGIC %md
# MAGIC ## Cell 4 — Step B: Parse YAML from the variable

# COMMAND ----------

config = yaml.safe_load(CONFIG_YAML)

input_table       = config["input"]["table"]
valid_table       = config["output"]["valid_table"]
quarantine_table  = config["output"]["quarantine_table"]
metrics_table     = config["output"]["metrics_table"]
checks            = config["checks"]

print(f"Input table      : {input_table}")
print(f"Valid table      : {valid_table}")
print(f"Quarantine table : {quarantine_table}")
print(f"Metrics table    : {metrics_table}")
print(f"Checks           : {[c['name'] for c in checks]}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Cell 5 — Step C: Load the input DataFrame dynamically from config

# COMMAND ----------

input_df: DataFrame = spark.read.table(input_table)

# Cache: the input is read once but scanned by both the split and the metrics.
input_df = input_df.cache()
total_input_rows = input_df.count()
print(f"Loaded {total_input_rows:,} rows from {input_table}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Cell 6 — Step D: Initialize the DQX engine

# COMMAND ----------

dq_engine = DQEngine(WorkspaceClient())

# COMMAND ----------

# MAGIC %md
# MAGIC ## Cell 7 — Step E: Run DQ checks and split the data
# MAGIC
# MAGIC `apply_checks_by_metadata_and_split` returns two DataFrames:
# MAGIC - **valid_df**   — rows that passed all `error`-level checks
# MAGIC - **quarantine_df** — rows that failed at least one check (with `_errors` / `_warnings`)

# COMMAND ----------

valid_df, quarantine_df = dq_engine.apply_checks_by_metadata_and_split(input_df, checks)

# Materialize once so downstream writes + metrics don't recompute the checks.
valid_df = valid_df.cache()
quarantine_df = quarantine_df.cache()

valid_rows      = valid_df.count()
quarantine_rows = quarantine_df.count()

print(f"Valid rows      : {valid_rows:,}")
print(f"Quarantine rows : {quarantine_rows:,}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Cell 8 — Step F: Write valid and quarantine datasets

# COMMAND ----------

(
    valid_df.write
    .mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable(valid_table)
)

(
    quarantine_df.write
    .mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable(quarantine_table)
)

print(f"Wrote valid      -> {valid_table}")
print(f"Wrote quarantine -> {quarantine_table}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Cell 9 — Step G: Build summary + per-check metrics
# MAGIC
# MAGIC DQX writes failures into the `_errors` and `_warnings` result columns of the
# MAGIC quarantine set. We derive per-check failure counts from those columns so the
# MAGIC metrics stay accurate regardless of how many checks are declared in the YAML.

# COMMAND ----------

# Shared metadata for this run.
run_id       = str(uuid.uuid4())
run_ts       = datetime.now(timezone.utc)

# DQX result columns (defaults). Present only when at least one check produced output.
RESULT_COLS = ["_errors", "_warnings"]


def per_check_failure_counts(df: DataFrame, check_names: list[str]) -> dict[str, int]:
    """Count how many rows failed each named check, reading DQX result columns.

    The `_errors` / `_warnings` columns are maps keyed by check name. We test key
    presence per column and aggregate a single count per check.
    """
    present = [c for c in RESULT_COLS if c in df.columns]
    counts = {name: 0 for name in check_names}
    if not present or df.rdd.isEmpty():
        return counts

    for name in check_names:
        # A row failed `name` if the key exists in either result map column.
        conds = [F.col(c).getItem(name).isNotNull() for c in present]
        predicate = conds[0]
        for extra in conds[1:]:
            predicate = predicate | extra
        counts[name] = df.filter(predicate).count()
    return counts


check_names = [c["name"] for c in checks]
failure_counts = per_check_failure_counts(quarantine_df, check_names)
print("Per-check failures:", failure_counts)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Cell 10 — Step G (cont.): Assemble and write the metrics table (append)

# COMMAND ----------

# One summary row per run + one row per check, unioned into a long/tidy shape
# so the metrics table stays stable as checks are added or removed.
summary_metrics = [
    ("total_input_rows", None, float(total_input_rows)),
    ("valid_rows",       None, float(valid_rows)),
    ("quarantine_rows",  None, float(quarantine_rows)),
]

check_metrics = [
    ("check_failure_count", name, float(count))
    for name, count in failure_counts.items()
]

metrics_rows = [
    (run_id, run_ts, input_table, metric, check, value)
    for metric, check, value in (summary_metrics + check_metrics)
]

metrics_df = spark.createDataFrame(
    metrics_rows,
    schema="run_id string, run_ts timestamp, input_table string, "
           "metric_name string, check_name string, metric_value double",
)

(
    metrics_df.write
    .mode("append")            # accumulate history across runs
    .option("mergeSchema", "true")
    .saveAsTable(metrics_table)
)

print(f"Wrote {metrics_df.count()} metric rows -> {metrics_table} (run_id={run_id})")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Cell 11 — Run summary

# COMMAND ----------

display(metrics_df.orderBy("metric_name", "check_name"))

# Release cached frames.
input_df.unpersist()
valid_df.unpersist()
quarantine_df.unpersist()
