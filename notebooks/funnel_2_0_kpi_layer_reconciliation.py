# Databricks notebook source
# MAGIC %md
# MAGIC # Funnel 2.0 — KPI reconciliation across Silver / Gold / Gold-Serve
# MAGIC
# MAGIC Standalone check (no DQ framework) that counts each headline KPI at every medallion
# MAGIC layer and reports the differences **grouped by `sales_organization` and `division`**,
# MAGIC so you can see where volume is lost between layers and for which org / brand.
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
# MAGIC a gap there — for a given org/division — is the signal worth investigating.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Parameters
# MAGIC Pick the environment (drives the Gold-Serve schema) and the reporting window. Optional
# MAGIC `sales_organization` / `division` filters let you drill into a single group.

# COMMAND ----------

# --- widgets -----------------------------------------------------------------
dbutils.widgets.dropdown("env", "uat", ["dev", "uat", "prod"], "Environment")
dbutils.widgets.text("start_date", "2024-01-01", "Start date (inclusive)")
dbutils.widgets.text("end_date", "2100-01-01", "End date (inclusive)")

# Optional drill-down filters (blank = all)
dbutils.widgets.text("filter_sales_org", "", "Filter sales_organization (blank = all)")
dbutils.widgets.text("filter_division", "", "Filter division (blank = all)")

# Schema overrides (leave defaults unless your deployment differs)
dbutils.widgets.text("silver_gold_schema", "prod_auto.gold_virtual", "Silver + Gold schema")
dbutils.widgets.text("sales_fact_schema", "prod_auto.gold_serve_virtual", "Gold-Serve fact schema")
dbutils.widgets.text("funnel_schema_override", "", "Funnel schema override (blank = by env)")

env = dbutils.widgets.get("env")
start_date = dbutils.widgets.get("start_date")
end_date = dbutils.widgets.get("end_date")
filter_org = dbutils.widgets.get("filter_sales_org").strip()
filter_div = dbutils.widgets.get("filter_division").strip()

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
print(f"Filter org       : {filter_org or '(all)'}")
print(f"Filter division  : {filter_div or '(all)'}")
print(f"Silver schema    : {SILVER}")
print(f"Gold schema      : {GOLD}")
print(f"Gold-Serve facts : {FACT}")
print(f"Funnel table     : {FUNNEL_TABLE}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Assumptions to verify against your Silver schema
# MAGIC Silver counts mirror the Gold business key / date logic as closely as possible. Silver
# MAGIC **org / division are raw and approximate** — the Gold products derive them (from
# MAGIC `brand_code`, nested structs, lookups), so Silver-vs-Gold splits by org/division will
# MAGIC not tie out exactly. The reliable integrity check is **Gold → Gold-Serve**.
# MAGIC
# MAGIC Per-object dimension columns used below:
# MAGIC
# MAGIC | Object | sales_organization | division |
# MAGIC |--------|--------------------|----------|
# MAGIC | `sap_c4c_leads` | `SALES_ORGANIZATION` | `DIVISION` |
# MAGIC | `sap_c4c_opportunity_header` | `ORGID` | `get_json_object(ENQUIRY_INFORMATION,'$.division')` (raw JSON string) |
# MAGIC | `sap_c4c_follow_up_activities` | `SALES_ORGANIZATION` | `DIVISION` |
# MAGIC | `customer_leads_long` | `SALES_ORGANISATION_CODE` | `DIVISION` |
# MAGIC | `customer_enquiries_long` | `SALES_ORGANISATION_CODE` | `DIVISION_CODE` |
# MAGIC | `sales_ordr_vn_d` | `sales_organization` | `division` |
# MAGIC | `sales_newu_usud_sals_vn_d_view` | `sales_organization_code` | `division_key` |
# MAGIC | `prsls_ldmg_actv_dy` | `sales_organization_code` | `division_code` |

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Reconciliation registry
# MAGIC One entry per (KPI, layer). Each produces rows grouped by
# MAGIC `(sales_organization, division, month)`; totals are derived by summing.
# MAGIC `layer` is one of `silver`, `gold`, `gold_serve`.

# COMMAND ----------

# Each tuple: (kpi, layer, object, date_expr, org_expr, div_expr, value_expr, extra_where)
REGISTRY = [
    # ---------------- Leads ----------------
    ("Leads", "silver", f"{SILVER}.sap_c4c_leads",
        "DATE(COALESCE(CREATION_DATE, audit_dfd_created_date))",
        "SALES_ORGANIZATION", "DIVISION",
        "COUNT(DISTINCT LPAD(COALESCE(C4CLEADID, REPLACE(LEAD_ID,'C4C-','')), 10, '0'))",
        ""),
    ("Leads", "gold", f"{GOLD}.customer_leads_long",
        "DATE(LEAD_CREATION_DATE)",
        "SALES_ORGANISATION_CODE", "DIVISION",
        "COUNT(DISTINCT LEAD_ID)",
        "AND SALES_ORGANISATION_CODE <> '5000'"),
    ("Leads", "gold_serve", FUNNEL_TABLE,
        "reporting_date",
        "sales_organization_code", "division_code",
        "SUM(leads)",
        ""),

    # ---------------- Hot Leads ----------------
    ("Hot Leads", "silver", f"{SILVER}.sap_c4c_leads",
        "DATE(COALESCE(CREATION_DATE, audit_dfd_created_date))",
        "SALES_ORGANIZATION", "DIVISION",
        "COUNT(DISTINCT CASE WHEN UPPER(QUALIFICATION) = 'HOT' "
        "THEN LPAD(COALESCE(C4CLEADID, REPLACE(LEAD_ID,'C4C-','')), 10, '0') END)",
        ""),
    ("Hot Leads", "gold", f"{GOLD}.customer_leads_long",
        "DATE(LEAD_CREATION_DATE)",
        "SALES_ORGANISATION_CODE", "DIVISION",
        "SUM(CASE WHEN LEAD_QUALIFICATION = 'Hot' OR PASS_TO_BRANCH_TIME IS NOT NULL THEN 1 ELSE 0 END)",
        "AND SALES_ORGANISATION_CODE <> '5000'"),
    ("Hot Leads", "gold_serve", FUNNEL_TABLE,
        "reporting_date",
        "sales_organization_code", "division_code",
        "SUM(hot_leads)",
        ""),

    # ---------------- Visits (opportunities) ----------------
    ("Visits", "silver", f"{SILVER}.sap_c4c_opportunity_header",
        "DATE(COALESCE(creationDate, audit_dfd_created_date))",
        "ORGID",
        # ENQUIRY_INFORMATION is a raw JSON string on Silver (struct only after from_json cast)
        "COALESCE(get_json_object(ENQUIRY_INFORMATION,'$.division'), "
        "get_json_object(ENQUIRY_INFORMATION,'$.DIVISION'))",
        "COUNT(DISTINCT ID)",
        ""),
    ("Visits", "gold", f"{GOLD}.customer_enquiries_long",
        "DATE(ENQUIRY_CREATED_TIME)",
        "SALES_ORGANISATION_CODE", "DIVISION_CODE",
        "COUNT(DISTINCT ENQUIRY_ID)",
        "AND SALES_ORGANISATION_CODE <> '5000'"),
    ("Visits", "gold_serve", FUNNEL_TABLE,
        "reporting_date",
        "sales_organization_code", "division_code",
        "SUM(opportunities)",
        ""),

    # ---------------- Test Drives (booked) ----------------
    ("Test Drives", "silver", f"{SILVER}.sap_c4c_follow_up_activities",
        "DATE(audit_dfd_created_date)",
        "SALES_ORGANIZATION", "DIVISION",
        "COUNT(DISTINCT CASE WHEN SUBJECT_TYPE LIKE 'Test Drive%' THEN OPPORTUNITYID END)",
        ""),
    ("Test Drives", "gold", f"{GOLD}.customer_enquiries_long",
        "DATE(COALESCE(TESTDRIVE_TIME, TESTDRIVE_CANCELLED_TIME, TESTDRIVE_OPEN_TIME))",
        "SALES_ORGANISATION_CODE", "DIVISION_CODE",
        "COUNT(DISTINCT CASE WHEN COALESCE(TESTDRIVE_OPEN_TIME, TESTDRIVE_TIME, TESTDRIVE_CANCELLED_TIME) "
        "IS NOT NULL THEN ENQUIRY_ID END)",
        "AND SALES_ORGANISATION_CODE <> '5000'"),
    ("Test Drives", "gold_serve", FUNNEL_TABLE,
        "reporting_date",
        "sales_organization_code", "division_code",
        "SUM(test_drives_booked)",
        ""),

    # ---------------- Orders (no separate Gold product; fact = upstream) ----------------
    ("Orders", "gold", f"{FACT}.sales_ordr_vn_d",
        "DATE(sales_item_creation_date)",
        "sales_organization", "division",
        "COUNT(DISTINCT sales_document)",
        "AND UPPER(order_type) IN ('ZOR','YOR','TA')"),
    ("Orders", "gold_serve", FUNNEL_TABLE,
        "reporting_date",
        "sales_organization_code", "division_code",
        "SUM(orders)",
        ""),

    # ---------------- Invoices (no separate Gold product; fact = upstream) ----------------
    ("Invoices", "gold", f"{FACT}.sales_newu_usud_sals_vn_d_view",
        "DATE(day)",
        "sales_organization_code", "division_key",
        "SUM(invoices)",
        ""),
    ("Invoices", "gold_serve", FUNNEL_TABLE,
        "reporting_date",
        "sales_organization_code", "division_code",
        "SUM(invoices)",
        ""),
]

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Run the counts (grouped by sales_organization × division × month)

# COMMAND ----------

from pyspark.sql import Row

def as_str(expr):
    """Normalise a dimension expression to a trimmed string, null-safe for grouping."""
    return f"COALESCE(NULLIF(TRIM(CAST({expr} AS STRING)), ''), '(null)')"

def grouped_sql(obj, date_expr, org_expr, div_expr, value_expr, extra_where):
    org_col, div_col = as_str(org_expr), as_str(div_expr)
    org_filter = f"AND {org_col} = '{filter_org}'" if filter_org else ""
    div_filter = f"AND {div_col} = '{filter_div}'" if filter_div else ""
    return f"""
        SELECT {org_col}                        AS sales_organization,
               {div_col}                        AS division,
               DATE_TRUNC('MONTH', {date_expr}) AS period,
               {value_expr}                     AS value
        FROM {obj}
        WHERE {date_expr} BETWEEN DATE('{start_date}') AND DATE('{end_date}')
              {org_filter} {div_filter} {extra_where}
        GROUP BY 1, 2, 3
    """

rows = []            # long: kpi, layer, object, sales_organization, division, period, value
errors = []          # (kpi, layer, object, message)

for kpi, layer, obj, date_expr, org_expr, div_expr, value_expr, extra_where in REGISTRY:
    sql = grouped_sql(obj, date_expr, org_expr, div_expr, value_expr, extra_where)
    try:
        for r in spark.sql(sql).collect():
            val = r["value"] if r["value"] is not None else 0
            rows.append(Row(kpi=kpi, layer=layer, object=obj,
                            sales_organization=r["sales_organization"],
                            division=r["division"], period=r["period"], value=float(val)))
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
# MAGIC ## 5. Summary — totals & differences per KPI × sales_organization × division
# MAGIC `silver → gold` = expected transformation shrinkage. `gold → gold_serve` = the integrity
# MAGIC check; rows flagged `CHECK` are where Gold and Gold-Serve disagree for that org/brand.

# COMMAND ----------

import pandas as pd

KPI_ORDER = ["Leads", "Hot Leads", "Visits", "Test Drives", "Orders", "Invoices"]
LAYERS = ["silver", "gold", "gold_serve"]
GROUP_KEYS = ["kpi", "sales_organization", "division"]

def build_summary(pdf):
    piv = pdf.pivot_table(index=GROUP_KEYS, columns="layer",
                          values="value", aggfunc="sum").reset_index()
    for lyr in LAYERS:
        if lyr not in piv.columns:
            piv[lyr] = pd.NA

    def diff(a, b):
        return None if pd.isna(a) or pd.isna(b) else round(b - a, 2)

    def pct(part, whole):
        if pd.isna(part) or pd.isna(whole) or whole in (0, None):
            return None
        return round(100.0 * part / whole, 1)

    piv["silver_to_gold_diff"] = [diff(s, g) for s, g in zip(piv["silver"], piv["gold"])]
    piv["gold_to_serve_diff"] = [diff(g, gs) for g, gs in zip(piv["gold"], piv["gold_serve"])]
    piv["gold_serve_match_pct"] = [pct(gs, g) for g, gs in zip(piv["gold"], piv["gold_serve"])]
    piv["status"] = piv["gold_to_serve_diff"].apply(
        lambda d: "n/a" if d is None else ("OK" if d == 0 else "CHECK"))
    piv["kpi"] = pd.Categorical(piv["kpi"], categories=KPI_ORDER, ordered=True)
    return piv.sort_values(["kpi", "sales_organization", "division"])

if monthly_df is not None:
    totals_pd = monthly_df.toPandas()
    summary = build_summary(totals_pd)
    cols = GROUP_KEYS + LAYERS + [
        "silver_to_gold_diff", "gold_to_serve_diff", "gold_serve_match_pct", "status"]
    display(spark.createDataFrame(summary[cols]))
else:
    print("No results to summarise.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. KPI roll-up (all org / division combined)
# MAGIC Quick top-line to confirm the totals still tie out once the group splits are summed.

# COMMAND ----------

if monthly_df is not None:
    rollup = (monthly_df.groupBy("kpi", "layer").sum("value").toPandas()
              .rename(columns={"sum(value)": "value"}))
    rp = rollup.pivot_table(index="kpi", columns="layer", values="value").reset_index()
    for lyr in LAYERS:
        if lyr not in rp.columns:
            rp[lyr] = pd.NA
    rp["silver_to_gold_diff"] = [
        None if pd.isna(s) or pd.isna(g) else round(g - s, 2)
        for s, g in zip(rp["silver"], rp["gold"])]
    rp["gold_to_serve_diff"] = [
        None if pd.isna(g) or pd.isna(gs) else round(gs - g, 2)
        for g, gs in zip(rp["gold"], rp["gold_serve"])]
    rp["kpi"] = pd.Categorical(rp["kpi"], categories=KPI_ORDER, ordered=True)
    rp = rp.sort_values("kpi")
    display(spark.createDataFrame(rp))
else:
    print("No results to roll up.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 7. Monthly breakdown (org × division × month)
# MAGIC Full detail — scan for the month/org/division where `gold` and `gold_serve` diverge.

# COMMAND ----------

if monthly_df is not None:
    wide = (monthly_df.toPandas()
            .pivot_table(index=["kpi", "sales_organization", "division", "period"],
                         columns="layer", values="value", aggfunc="sum")
            .reset_index())
    for lyr in LAYERS:
        if lyr not in wide.columns:
            wide[lyr] = pd.NA
    wide["gold_to_serve_diff"] = [
        None if pd.isna(g) or pd.isna(gs) else round(gs - g, 2)
        for g, gs in zip(wide["gold"], wide["gold_serve"])]
    wide["kpi"] = pd.Categorical(wide["kpi"], categories=KPI_ORDER, ordered=True)
    wide = wide.sort_values(["kpi", "sales_organization", "division", "period"])
    display(spark.createDataFrame(wide[["kpi", "sales_organization", "division", "period",
                                        "silver", "gold", "gold_serve", "gold_to_serve_diff"]]))
else:
    print("No results to break down.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 8. Object / layer reference
# MAGIC What each column above was counted from, for the selected environment.

# COMMAND ----------

ref_df = spark.createDataFrame([
    Row(kpi=kpi, layer=layer, object=obj,
        sales_organization=org_expr, division=div_expr, measure=value_expr)
    for kpi, layer, obj, _d, org_expr, div_expr, value_expr, _w in REGISTRY])
display(ref_df.orderBy("kpi", "layer"))

# COMMAND ----------

# MAGIC %md
# MAGIC # Granular drill-down — which rows are missing between layers
# MAGIC For each KPI, sample the actual business keys (with **all attributes**) that exist in one
# MAGIC layer but not the next — e.g. `lead_id`s in Silver `sap_c4c_leads` that never reach Gold
# MAGIC `customer_leads_long`.
# MAGIC
# MAGIC **Scope of key-level anti-joins**
# MAGIC - **Silver ↔ Gold** — full key-level comparison (both carry the business key).
# MAGIC - **Orders / Invoices** — fact rows that fail to attribute (fact key not found in the
# MAGIC   product it joins to).
# MAGIC - **Gold ↔ Gold-Serve** — *not available at key level*: `prsls_ldmg_actv_dy` is a
# MAGIC   pre-aggregated table with no `lead_id` / `enquiry_id`. Use the group-grain checks in
# MAGIC   sections 5–7 for that boundary.
# MAGIC
# MAGIC **How to read it**
# MAGIC - `source_only` = in the upstream layer, missing downstream (the drop-off you're chasing).
# MAGIC - `product_only` = in the downstream layer, absent upstream (usually key-derivation or
# MAGIC   join back-fill — e.g. leads sourced via a different key).
# MAGIC - The upstream population is bounded by the date window / filters; the downstream
# MAGIC   *existence* set is **not** date-bounded, so near-boundary date shifts don't create false
# MAGIC   positives. Org `5000` is physically excluded from the Gold products, so those rows will
# MAGIC   legitimately appear as `source_only` for Leads / Visits / Test Drives.

# COMMAND ----------

dbutils.widgets.text("granular_sample_rows", "20", "Drill-down: sample rows per anti-join")
dbutils.widgets.dropdown(
    "granular_sample_kpi", "All",
    ["All", "Leads", "Hot Leads", "Visits", "Test Drives", "Orders", "Invoices"],
    "Drill-down: KPI")

SAMPLE_N = int(dbutils.widgets.get("granular_sample_rows") or "20")
SAMPLE_KPI = dbutils.widgets.get("granular_sample_kpi")


def _win(date_expr):
    return f"DATE({date_expr}) BETWEEN DATE('{start_date}') AND DATE('{end_date}')"


def _dim_filters(org_expr, div_expr):
    f = ""
    if filter_org:
        f += f" AND {as_str(org_expr)} = '{filter_org}'"
    if filter_div:
        f += f" AND {as_str(div_expr)} = '{filter_div}'"
    return f

# Per KPI: the two key-bearing layers to compare and which directions to sample.
# left/right = (label, object, key_expr, where_clause). Date/dim filters are applied to the
# sampled side only; the existence side uses just its structural qualifier.
DRILL = [
    ("Leads",
     ("silver", f"{SILVER}.sap_c4c_leads",
      "LPAD(COALESCE(C4CLEADID, REPLACE(LEAD_ID,'C4C-','')), 10, '0')",
      _win("COALESCE(CREATION_DATE, audit_dfd_created_date)")),
     ("gold", f"{GOLD}.customer_leads_long", "LEAD_ID", "1=1"),
     ("silver", "SALES_ORGANIZATION", "DIVISION"),
     ("gold", "SALES_ORGANISATION_CODE", "DIVISION"),
     ["source_only", "product_only"]),

    ("Hot Leads",
     ("silver", f"{SILVER}.sap_c4c_leads",
      "LPAD(COALESCE(C4CLEADID, REPLACE(LEAD_ID,'C4C-','')), 10, '0')",
      _win("COALESCE(CREATION_DATE, audit_dfd_created_date)") + " AND UPPER(QUALIFICATION) = 'HOT'"),
     ("gold", f"{GOLD}.customer_leads_long", "LEAD_ID",
      "(LEAD_QUALIFICATION = 'Hot' OR PASS_TO_BRANCH_TIME IS NOT NULL)"),
     ("silver", "SALES_ORGANIZATION", "DIVISION"),
     ("gold", "SALES_ORGANISATION_CODE", "DIVISION"),
     ["source_only", "product_only"]),

    ("Visits",
     ("silver", f"{SILVER}.sap_c4c_opportunity_header", "LPAD(ID, 10, '0')",
      _win("COALESCE(creationDate, audit_dfd_created_date)")),
     ("gold", f"{GOLD}.customer_enquiries_long", "ENQUIRY_ID", "1=1"),
     ("silver", "ORGID",
      "COALESCE(get_json_object(ENQUIRY_INFORMATION,'$.division'), "
      "get_json_object(ENQUIRY_INFORMATION,'$.DIVISION'))"),
     ("gold", "SALES_ORGANISATION_CODE", "DIVISION_CODE"),
     ["source_only", "product_only"]),

    ("Test Drives",
     ("silver", f"{SILVER}.sap_c4c_follow_up_activities", "LPAD(OPPORTUNITYID, 10, '0')",
      _win("audit_dfd_created_date") + " AND SUBJECT_TYPE LIKE 'Test Drive%' AND NULLIF(OPPORTUNITYID,'') IS NOT NULL"),
     ("gold", f"{GOLD}.customer_enquiries_long", "ENQUIRY_ID",
      "COALESCE(TESTDRIVE_OPEN_TIME, TESTDRIVE_TIME, TESTDRIVE_CANCELLED_TIME) IS NOT NULL"),
     ("silver", "SALES_ORGANIZATION", "DIVISION"),
     ("gold", "SALES_ORGANISATION_CODE", "DIVISION_CODE"),
     ["source_only", "product_only"]),

    # Orders / Invoices: fact rows that fail to attribute to the product they join to.
    ("Orders",
     ("gold_serve_fact", f"{FACT}.sales_ordr_vn_d", "enquiry_id",
      _win("sales_item_creation_date") + " AND UPPER(order_type) IN ('ZOR','YOR','TA') AND NULLIF(enquiry_id,'') IS NOT NULL"),
     ("enquiries", f"{GOLD}.customer_enquiries_long", "ENQUIRY_ID", "1=1"),
     ("gold_serve_fact", "sales_organization", "division"),
     ("enquiries", "SALES_ORGANISATION_CODE", "DIVISION_CODE"),
     ["source_only"]),

    ("Invoices",
     ("gold_serve_fact", f"{FACT}.sales_newu_usud_sals_vn_d_view", "sales_order_number",
      _win("day") + " AND NULLIF(sales_order_number,'') IS NOT NULL"),
     ("orders", f"{FACT}.sales_ordr_vn_d", "sales_document", "1=1"),
     ("gold_serve_fact", "sales_organization_code", "division_key"),
     ("orders", "sales_organization", "division"),
     ["source_only"]),
]


def anti_sample(title, left, right, n):
    """left/right = (label, object, key_expr, where). Sample left rows whose key is absent in right."""
    l_lbl, l_obj, l_key, l_where = left
    r_lbl, r_obj, r_key, r_where = right
    left_sub = f"(SELECT *, {l_key} AS _key FROM {l_obj} WHERE {l_where}) L"
    right_sub = f"(SELECT DISTINCT {r_key} AS _key FROM {r_obj} WHERE {r_where}) R"
    base = f"FROM {left_sub} LEFT ANTI JOIN {right_sub} ON L._key = R._key"
    try:
        c = spark.sql(f"SELECT COUNT(*) AS c, COUNT(DISTINCT L._key) AS k {base}").first()
        print(f"[{title}]  in {l_lbl} not in {r_lbl}: {c['k']} distinct keys ({c['c']} rows)")
        if c["c"]:
            display(spark.sql(f"SELECT L.* {base} LIMIT {n}"))
    except Exception as e:
        print(f"[{title}]  FAILED — {str(e).splitlines()[0]}")


for kpi, left, right, ldim, rdim, directions in DRILL:
    if SAMPLE_KPI != "All" and SAMPLE_KPI != kpi:
        continue
    # apply the sampled side's dimension filters
    l_lbl, l_obj, l_key, l_where = left
    r_lbl, r_obj, r_key, r_where = right
    left_f = (l_lbl, l_obj, l_key, l_where + _dim_filters(ldim[1], ldim[2]))
    right_f = (r_lbl, r_obj, r_key, r_where + _dim_filters(rdim[1], rdim[2]))
    if "source_only" in directions:
        anti_sample(f"{kpi} · source_only", left_f, right, SAMPLE_N)
    if "product_only" in directions:
        # sample the product side, existence check against source (source keeps its qualifier only)
        prod_left = (r_lbl, r_obj, r_key, r_where + _dim_filters(rdim[1], rdim[2]))
        src_right = (l_lbl, l_obj, l_key, left[3])
        anti_sample(f"{kpi} · product_only", prod_left, src_right, SAMPLE_N)
