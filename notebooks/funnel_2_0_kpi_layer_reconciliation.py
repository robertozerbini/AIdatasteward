# Databricks notebook source
# MAGIC %md
# MAGIC # Funnel 2.0 — KPI reconciliation across Silver / Gold / Gold-Serve
# MAGIC
# MAGIC Standalone check (no DQ framework) that counts each headline KPI at every medallion
# MAGIC layer and reports the differences, so you can see where volume is lost between layers.
# MAGIC
# MAGIC | KPI | Silver source | Gold product | Gold-Serve (funnel) |
# MAGIC |-----|---------------|--------------|---------------------|
# MAGIC | Leads / Hot Leads | `sap_c4c_leads` | `customer_leads_long` | `prsls_ldmg_actv_dy.leads / hot_leads` |
# MAGIC | Visits | `sap_c4c_opportunity_header` | `customer_enquiries_long` | `…opportunities` |
# MAGIC | Test Drives | `sap_c4c_follow_up_activities` | `customer_enquiries_long` | `…test_drives_booked` |
# MAGIC | Orders | — | `sales_ordr_vn_d` * | `…orders` |
# MAGIC | Invoices | — | `sales_newu_usud_sals_vn_d_view` * | `…invoices` |
# MAGIC
# MAGIC \* Orders and Invoices have no separate curated Gold product — the serving fact tables
# MAGIC are their upstream, so they populate the "Gold" column here.
# MAGIC
# MAGIC **Expected divergence:** Silver → Gold naturally shrinks (dedup to latest row per key,
# MAGIC `sales_organisation <> '5000'`, date filters). Gold → Gold-Serve should reconcile closely;
# MAGIC a gap there is the signal worth investigating.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Parameters
# MAGIC Pick the environment (drives the Gold-Serve schema) and the reporting window.

# COMMAND ----------

# --- widgets -----------------------------------------------------------------
dbutils.widgets.dropdown("env", "uat", ["dev", "uat", "prod"], "Environment")
dbutils.widgets.text("start_date", "2024-01-01", "Start date (inclusive)")
dbutils.widgets.text("end_date", "2100-01-01", "End date (inclusive)")

# Schema overrides (leave defaults unless your deployment differs)
dbutils.widgets.text("silver_gold_schema", "prod_auto.gold_virtual", "Silver + Gold schema")
dbutils.widgets.text("sales_fact_schema", "prod_auto.gold_serve_virtual", "Gold-Serve fact schema")
dbutils.widgets.text("funnel_schema_override", "", "Funnel schema override (blank = by env)")

env = dbutils.widgets.get("env")
start_date = dbutils.widgets.get("start_date")
end_date = dbutils.widgets.get("end_date")

SILVER_GOLD = dbutils.widgets.get("silver_gold_schema").strip()
FACT = dbutils.widgets.get("sales_fact_schema").strip()

# Gold-Serve schema by environment (where prsls_ldmg_actv_dy lives)
FUNNEL_BY_ENV = {
    "dev":  "discovery_auto.auto_dev",
    "uat":  "discovery_auto.auto_analytics",
    "prod": "prod_auto.gold_serve",
}
FUNNEL = dbutils.widgets.get("funnel_schema_override").strip() or FUNNEL_BY_ENV[env]

# Silver and Gold share one schema in this pipeline
SILVER = SILVER_GOLD
GOLD = SILVER_GOLD

FUNNEL_TABLE = f"{FUNNEL}.prsls_ldmg_actv_dy"

print(f"Environment      : {env}")
print(f"Window           : {start_date} .. {end_date}")
print(f"Silver schema    : {SILVER}")
print(f"Gold schema      : {GOLD}")
print(f"Gold-Serve facts : {FACT}")
print(f"Funnel table     : {FUNNEL_TABLE}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Assumptions to verify against your Silver schema
# MAGIC The Silver counts mirror the Gold business key / date logic as closely as possible.
# MAGIC A few raw columns are timestamp-strings, so where a reliable business date is not
# MAGIC available the load date `audit_dfd_created_date` is used. Adjust the expressions in the
# MAGIC registry below if your raw column names differ.
# MAGIC
# MAGIC - **Leads key** = `LPAD(COALESCE(C4CLEADID, REPLACE(LEAD_ID,'C4C-','')), 10, '0')`
# MAGIC - **Hot Leads (Silver)** = `QUALIFICATION = 'HOT'` only (no `pass_to_branch` signal at Silver — expected to differ from Gold)
# MAGIC - **Visits (Silver)** = distinct opportunity `ID`
# MAGIC - **Test Drives (Silver)** = distinct `OPPORTUNITYID` where `SUBJECT_TYPE LIKE 'Test Drive%'`

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Reconciliation registry
# MAGIC One entry per (KPI, layer). Each produces monthly rows `(period, value)`; totals are
# MAGIC derived by summing. `layer` is one of `silver`, `gold`, `gold_serve`.

# COMMAND ----------

# Each tuple: (kpi, layer, object, date_expr, value_expr, extra_where)
REGISTRY = [
    # ---------------- Leads ----------------
    ("Leads", "silver", f"{SILVER}.sap_c4c_leads",
        "DATE(COALESCE(CREATION_DATE, audit_dfd_created_date))",
        "COUNT(DISTINCT LPAD(COALESCE(C4CLEADID, REPLACE(LEAD_ID,'C4C-','')), 10, '0'))",
        ""),
    ("Leads", "gold", f"{GOLD}.customer_leads_long",
        "DATE(LEAD_CREATION_DATE)",
        "COUNT(DISTINCT LEAD_ID)",
        "AND SALES_ORGANISATION_CODE <> '5000'"),
    ("Leads", "gold_serve", FUNNEL_TABLE,
        "reporting_date",
        "SUM(leads)",
        ""),

    # ---------------- Hot Leads ----------------
    ("Hot Leads", "silver", f"{SILVER}.sap_c4c_leads",
        "DATE(COALESCE(CREATION_DATE, audit_dfd_created_date))",
        "COUNT(DISTINCT CASE WHEN UPPER(QUALIFICATION) = 'HOT' "
        "THEN LPAD(COALESCE(C4CLEADID, REPLACE(LEAD_ID,'C4C-','')), 10, '0') END)",
        ""),
    ("Hot Leads", "gold", f"{GOLD}.customer_leads_long",
        "DATE(LEAD_CREATION_DATE)",
        "SUM(CASE WHEN LEAD_QUALIFICATION = 'Hot' OR PASS_TO_BRANCH_TIME IS NOT NULL THEN 1 ELSE 0 END)",
        "AND SALES_ORGANISATION_CODE <> '5000'"),
    ("Hot Leads", "gold_serve", FUNNEL_TABLE,
        "reporting_date",
        "SUM(hot_leads)",
        ""),

    # ---------------- Visits (opportunities) ----------------
    ("Visits", "silver", f"{SILVER}.sap_c4c_opportunity_header",
        "DATE(COALESCE(creationDate, audit_dfd_created_date))",
        "COUNT(DISTINCT ID)",
        ""),
    ("Visits", "gold", f"{GOLD}.customer_enquiries_long",
        "DATE(ENQUIRY_CREATED_TIME)",
        "COUNT(DISTINCT ENQUIRY_ID)",
        "AND SALES_ORGANISATION_CODE <> '5000'"),
    ("Visits", "gold_serve", FUNNEL_TABLE,
        "reporting_date",
        "SUM(opportunities)",
        ""),

    # ---------------- Test Drives (booked) ----------------
    ("Test Drives", "silver", f"{SILVER}.sap_c4c_follow_up_activities",
        "DATE(audit_dfd_created_date)",
        "COUNT(DISTINCT CASE WHEN SUBJECT_TYPE LIKE 'Test Drive%' THEN OPPORTUNITYID END)",
        ""),
    ("Test Drives", "gold", f"{GOLD}.customer_enquiries_long",
        "DATE(COALESCE(TESTDRIVE_TIME, TESTDRIVE_CANCELLED_TIME, TESTDRIVE_OPEN_TIME))",
        "COUNT(DISTINCT CASE WHEN COALESCE(TESTDRIVE_OPEN_TIME, TESTDRIVE_TIME, TESTDRIVE_CANCELLED_TIME) "
        "IS NOT NULL THEN ENQUIRY_ID END)",
        "AND SALES_ORGANISATION_CODE <> '5000'"),
    ("Test Drives", "gold_serve", FUNNEL_TABLE,
        "reporting_date",
        "SUM(test_drives_booked)",
        ""),

    # ---------------- Orders (no separate Gold product; fact = upstream) ----------------
    ("Orders", "gold", f"{FACT}.sales_ordr_vn_d",
        "DATE(sales_item_creation_date)",
        "COUNT(DISTINCT sales_document)",
        "AND UPPER(order_type) IN ('ZOR','YOR','TA')"),
    ("Orders", "gold_serve", FUNNEL_TABLE,
        "reporting_date",
        "SUM(orders)",
        ""),

    # ---------------- Invoices (no separate Gold product; fact = upstream) ----------------
    ("Invoices", "gold", f"{FACT}.sales_newu_usud_sals_vn_d_view",
        "DATE(day)",
        "SUM(invoices)",
        ""),
    ("Invoices", "gold_serve", FUNNEL_TABLE,
        "reporting_date",
        "SUM(invoices)",
        ""),
]

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Run the counts (monthly grain)

# COMMAND ----------

from pyspark.sql import Row

def monthly_sql(obj, date_expr, value_expr, extra_where):
    return f"""
        SELECT DATE_TRUNC('MONTH', {date_expr}) AS period,
               {value_expr}                     AS value
        FROM {obj}
        WHERE {date_expr} BETWEEN DATE('{start_date}') AND DATE('{end_date}')
              {extra_where}
        GROUP BY 1
    """

rows = []            # long: kpi, layer, object, period, value
errors = []          # (kpi, layer, object, message)

for kpi, layer, obj, date_expr, value_expr, extra_where in REGISTRY:
    sql = monthly_sql(obj, date_expr, value_expr, extra_where)
    try:
        for r in spark.sql(sql).collect():
            val = r["value"] if r["value"] is not None else 0
            rows.append(Row(kpi=kpi, layer=layer, object=obj,
                            period=r["period"], value=float(val)))
    except Exception as e:
        errors.append((kpi, layer, obj, str(e).splitlines()[0]))
        print(f"[FAILED] {kpi:<12} {layer:<10} {obj}\n         {str(e).splitlines()[0]}")

monthly_df = spark.createDataFrame(rows) if rows else None
if errors:
    print(f"\n{len(errors)} query(ies) failed — check object/column names for that layer above.")
else:
    print("All layer queries executed.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Summary — totals & differences per KPI
# MAGIC `silver → gold` = expected transformation shrinkage. `gold → gold_serve` = the integrity
# MAGIC check; a non-zero delta (or non-100% match) is what to investigate.

# COMMAND ----------

import pandas as pd

KPI_ORDER = ["Leads", "Hot Leads", "Visits", "Test Drives", "Orders", "Invoices"]
LAYERS = ["silver", "gold", "gold_serve"]

if monthly_df is not None:
    totals = (monthly_df.groupBy("kpi", "layer")
              .sum("value").toPandas()
              .rename(columns={"sum(value)": "value"}))
    pivot = totals.pivot(index="kpi", columns="layer", values="value")
    for lyr in LAYERS:
        if lyr not in pivot.columns:
            pivot[lyr] = pd.NA
    pivot = pivot.reindex([k for k in KPI_ORDER if k in pivot.index])

    def diff(a, b):
        return None if pd.isna(a) or pd.isna(b) else round(a - b, 2)

    def pct(part, whole):
        if pd.isna(part) or pd.isna(whole) or whole in (0, None):
            return None
        return round(100.0 * part / whole, 1)

    summary = pd.DataFrame({
        "kpi":                 pivot.index,
        "silver":              pivot["silver"].values,
        "gold":                pivot["gold"].values,
        "gold_serve":          pivot["gold_serve"].values,
        "silver_to_gold_diff": [diff(g, s) for s, g in zip(pivot["silver"], pivot["gold"])],
        "gold_to_serve_diff":  [diff(gs, g) for g, gs in zip(pivot["gold"], pivot["gold_serve"])],
        "gold_serve_match_pct":[pct(gs, g) for g, gs in zip(pivot["gold"], pivot["gold_serve"])],
    }).reset_index(drop=True)

    summary["status"] = summary["gold_to_serve_diff"].apply(
        lambda d: "n/a" if d is None else ("OK" if d == 0 else "CHECK"))

    display(spark.createDataFrame(summary))
else:
    print("No results to summarise.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. Monthly breakdown (locate where a gap appears)
# MAGIC Wide by layer, per KPI and month. Scan for the months where `gold` and `gold_serve`
# MAGIC diverge.

# COMMAND ----------

if monthly_df is not None:
    monthly_pd = monthly_df.toPandas()
    wide = (monthly_pd
            .pivot_table(index=["kpi", "period"], columns="layer",
                         values="value", aggfunc="sum")
            .reset_index())
    for lyr in LAYERS:
        if lyr not in wide.columns:
            wide[lyr] = pd.NA
    wide["gold_to_serve_diff"] = [
        None if pd.isna(g) or pd.isna(gs) else round(gs - g, 2)
        for g, gs in zip(wide["gold"], wide["gold_serve"])
    ]
    wide["kpi"] = pd.Categorical(wide["kpi"], categories=KPI_ORDER, ordered=True)
    wide = wide.sort_values(["kpi", "period"])
    display(spark.createDataFrame(wide[["kpi", "period", "silver", "gold",
                                        "gold_serve", "gold_to_serve_diff"]]))
else:
    print("No results to break down.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 7. Object / layer reference
# MAGIC What each column above was counted from, for the selected environment.

# COMMAND ----------

ref = [(kpi, layer, obj, value_expr)
       for kpi, layer, obj, _d, value_expr, _w in REGISTRY]
ref_df = spark.createDataFrame(
    [Row(kpi=k, layer=l, object=o, measure=m) for k, l, o, m in ref])
display(ref_df.orderBy("kpi", "layer"))
