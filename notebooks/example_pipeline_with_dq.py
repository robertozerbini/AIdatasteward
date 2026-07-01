# Databricks notebook source
# MAGIC %md
# MAGIC # Example pipeline notebook — calling DQ inline
# MAGIC
# MAGIC Shows how a data-product pipeline invokes the shared `dq_framework`.
# MAGIC Three lines: run row-level checks, gate on error-severity failures,
# MAGIC continue downstream with only the valid rows.

# COMMAND ----------

# Install the framework wheel (prod: attach to the job cluster instead).
# MAGIC %pip install dq_framework
# For dev against Repos/Workspace Files instead of a wheel:
# import sys; sys.path.append("/Workspace/Repos/<you>/AIdatasteward")

# COMMAND ----------

from dq_framework import run_row_checks

# COMMAND ----------

# ---- your pipeline logic produces a DataFrame ----
df = spark.read.table("prod_auto.gold_virtual.eudu_mdata_dtac_orgstrc")
# ... transforms ...

# COMMAND ----------

# ---- data quality gate ----
res = run_row_checks(
    df,
    config="/Workspace/Repos/<you>/AIdatasteward/configs/products/orgstrc.yaml",
    trigger="pipeline",   # tags every row written to dq_results
)

res.raise_if_gated()      # stops the job if any error-severity check failed
df = res.valid_df         # continue with clean rows only

print(f"passed={res.passed} gated={res.gated} "
      f"quarantined={res.quarantine_df.count()}")

# COMMAND ----------

# ---- continue the pipeline with validated data ----
(
    df.write.mode("overwrite")
    .saveAsTable("prod_auto.gold_virtual.eudu_mdata_dtac_orgstrc_curated")
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Scheduled endpoint / KPI checks (separate job tasks)
# MAGIC
# MAGIC ```python
# MAGIC from dq_framework import run_endpoint_checks, run_kpi_asserts
# MAGIC
# MAGIC run_endpoint_checks(config=".../configs/endpoints/customer_360.yaml",
# MAGIC                     trigger="schedule").raise_if_gated()
# MAGIC
# MAGIC run_kpi_asserts(config=".../configs/kpis/revenue.yaml",
# MAGIC                 trigger="schedule").raise_if_gated()
# MAGIC ```
# MAGIC Same engine, same `dq_results` table, different trigger tag.
