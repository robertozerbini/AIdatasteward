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
# MAGIC | Total Reservation | — | `sales_ordr_vn_d` * | `…total_order_items` |
# MAGIC | Invoices | — | `sales_newu_usud_sals_vn_d_view` * | `…invoices` |
# MAGIC
# MAGIC \* Total Reservation and Invoices have no separate curated Gold product — the serving fact tables
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
# MAGIC ## 1b. Output formatting helper
# MAGIC Every result below is preceded by a printed banner — **a title, how to read the table,
# MAGIC and the action to take** — so each output cell explains itself without scrolling back to
# MAGIC the markdown.

# COMMAND ----------

def banner(title, how_to_read=None, actions=None):
    """Print a self-describing header above an output: title, how-to-read, actions.

    how_to_read / actions are lists of short strings. Rendered as bullets so the
    display() table (or print) that follows is readable on its own.
    """
    rule = "=" * 84
    print(rule)
    print(f"  {title}")
    print(rule)
    if how_to_read:
        print("HOW TO READ")
        for b in how_to_read:
            print(f"  - {b}")
    if actions:
        print("WHAT TO DO")
        for b in actions:
            print(f"  > {b}")
    print()


# Shared legend for the reconciliation columns (reused across sections 5-7).
COLUMN_LEGEND = [
    "silver / gold / gold_serve = the KPI counted at each medallion layer.",
    "gold_walkin = walk-in enquiries the funnel injects (Leads / Hot Leads only).",
    "gold_incl_walkin = gold + gold_walkin (what the funnel should equal).",
    "silver_to_gold_diff = gold - silver (informational; expected to shrink).",
    "serve_diff = gold_serve - gold_incl_walkin (the integrity gap that matters).",
    "final_status = OK when the funnel matches gold (incl. walk-ins), CHECK when it does not.",
    "note = anything to verify without failing the row (chiefly silver<->gold differences).",
]

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Assumptions to verify against your Silver schema
# MAGIC Silver counts mirror the Gold business key / date logic as closely as possible. Silver
# MAGIC **org / division are raw and approximate** — the Gold products derive them (from
# MAGIC `brand_code`, nested structs, lookups), so Silver-vs-Gold splits by org/division will
# MAGIC not tie out exactly. The reliable integrity check is **Gold → Gold-Serve**.
# MAGIC
# MAGIC **Timezone:** all Silver C4C timestamps are **UTC**; Gold shifts them to Dubai (GST,
# MAGIC UTC+4) via `TIMESTAMPADD(HOUR, 4, …)`. Every Silver date expression below applies the
# MAGIC same +4h so the reporting window lines up with Gold / Gold-Serve. (Gold-Serve fact dates
# MAGIC — `sales_item_creation_date`, `day` — are already business-local and are used as-is.)
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
        # +4h to match gold's LEAD_CREATION_DATE = TIMESTAMPADD(HOUR,4,...) (UTC->GST),
        # so window boundaries line up and edge-of-day leads aren't false positives.
        "DATE(TIMESTAMPADD(HOUR, 4, COALESCE(CREATION_DATE, audit_dfd_created_date)))",
        "SALES_ORGANIZATION", "DIVISION",
        "COUNT(DISTINCT LPAD(COALESCE(C4CLEADID, REPLACE(LEAD_ID,'C4C-','')), 10, '0'))",
        ""),
    ("Leads", "gold", f"{GOLD}.customer_leads_long",
        "DATE(LEAD_CREATION_DATE)",
        "SALES_ORGANISATION_CODE", "DIVISION",
        "COUNT(DISTINCT LEAD_ID)",
        "AND SALES_ORGANISATION_CODE <> '5000'"),
    # Walk-in leads injected by the CUSTOMER_ENQUIRIES stream (President Dashboard change):
    #   funnel.leads = customer_leads_long leads + walk-in enquiries with no lead_id.
    # Captured as its own `gold_walkin` layer so silver->gold stays a clean lead-path check;
    # the summary compares (gold + gold_walkin) against gold_serve.
    ("Leads", "gold_walkin", f"{GOLD}.customer_enquiries_long",
        "DATE(ENQUIRY_CREATED_TIME)",
        "SALES_ORGANISATION_CODE", "DIVISION_CODE",
        "SUM(CASE WHEN LEAD_ID IS NULL AND UPPER(ENQUIRY_SOURCE) = 'WALK-IN' THEN 1 ELSE 0 END)",
        ""),
    ("Leads", "gold_serve", FUNNEL_TABLE,
        "reporting_date",
        "sales_organization_code", "division_code",
        "SUM(leads)",
        ""),

    # ---------------- Hot Leads ----------------
    ("Hot Leads", "silver", f"{SILVER}.sap_c4c_leads",
        # +4h to match gold's LEAD_CREATION_DATE = TIMESTAMPADD(HOUR,4,...) (UTC->GST),
        # so window boundaries line up and edge-of-day leads aren't false positives.
        "DATE(TIMESTAMPADD(HOUR, 4, COALESCE(CREATION_DATE, audit_dfd_created_date)))",
        "SALES_ORGANIZATION", "DIVISION",
        "COUNT(DISTINCT CASE WHEN UPPER(QUALIFICATION) = 'HOT' "
        "THEN LPAD(COALESCE(C4CLEADID, REPLACE(LEAD_ID,'C4C-','')), 10, '0') END)",
        ""),
    ("Hot Leads", "gold", f"{GOLD}.customer_leads_long",
        "DATE(LEAD_CREATION_DATE)",
        "SALES_ORGANISATION_CODE", "DIVISION",
        "SUM(CASE WHEN LEAD_QUALIFICATION = 'Hot' OR PASS_TO_BRANCH_TIME IS NOT NULL THEN 1 ELSE 0 END)",
        "AND SALES_ORGANISATION_CODE <> '5000'"),
    # Same walk-in expression feeds hot_leads too (identical CASE in the funnel), which is why
    # the Leads and Hot Leads gold->serve gaps were identical.
    ("Hot Leads", "gold_walkin", f"{GOLD}.customer_enquiries_long",
        "DATE(ENQUIRY_CREATED_TIME)",
        "SALES_ORGANISATION_CODE", "DIVISION_CODE",
        "SUM(CASE WHEN LEAD_ID IS NULL AND UPPER(ENQUIRY_SOURCE) = 'WALK-IN' THEN 1 ELSE 0 END)",
        ""),
    ("Hot Leads", "gold_serve", FUNNEL_TABLE,
        "reporting_date",
        "sales_organization_code", "division_code",
        "SUM(hot_leads)",
        ""),

    # ---------------- Visits (opportunities) ----------------
    ("Visits", "silver", f"{SILVER}.sap_c4c_opportunity_header",
        # Silver C4C timestamps are UTC -> +4h to Dubai (GST), matching gold.
        "DATE(TIMESTAMPADD(HOUR, 4, COALESCE(creationDate, audit_dfd_created_date)))",
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
        # Silver C4C timestamps are UTC -> +4h to Dubai (GST), matching gold.
        "DATE(TIMESTAMPADD(HOUR, 4, audit_dfd_created_date))",
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

    # ---------------- Total Reservation (SUM of reservation item quantities) ----------------
    # SAP def: SUM(item_quantity) where sales_item_creation_date is in the period and
    # order_type IN ('ZOR','YOR','TA') = Standard Order / Fleet Order / AFM Corporate Order.
    # In the funnel this is the additive `total_order_items` column.
    ("Total Reservation", "gold", f"{FACT}.sales_ordr_vn_d",
        "DATE(sales_item_creation_date)",
        "sales_organization", "division",
        "SUM(item_quantity)",
        "AND UPPER(order_type) IN ('ZOR','YOR','TA')"),
    ("Total Reservation", "gold_serve", FUNNEL_TABLE,
        "reporting_date",
        "sales_organization_code", "division_code",
        "SUM(total_order_items)",
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
# MAGIC **`final_status`** is the single verdict: does all the KPI's information land in
# MAGIC **Gold-Serve** (the funnel)? `OK` = the funnel matches Gold (incl. walk-ins); `CHECK` =
# MAGIC it doesn't and needs investigation; `n/a` = nothing to compare.
# MAGIC
# MAGIC **`note`** flags anything to verify without failing the row — chiefly silver↔gold
# MAGIC differences, which are usually *expected* (dedup, +4h UTC→GST edge, division
# MAGIC reclassification, refresh latency, or Hot-Leads' `pass_to_branch` rule that Silver can't
# MAGIC reproduce). A silver↔gold gap does **not** by itself mean data is missing — confirm with
# MAGIC the key-level drill-down at the bottom (e.g. Leads `source_only = 0`).
# MAGIC
# MAGIC Supporting columns: `gold_walkin` (walk-ins the funnel adds, Leads/Hot Leads only),
# MAGIC `gold_incl_walkin` = `gold + gold_walkin`, `serve_diff` = `gold_serve − gold_incl_walkin`.

# COMMAND ----------

import pandas as pd

KPI_ORDER = ["Leads", "Hot Leads", "Visits", "Test Drives", "Total Reservation", "Invoices"]
LAYERS = ["silver", "gold", "gold_walkin", "gold_serve"]
GROUP_KEYS = ["kpi", "sales_organization", "division"]


def _num(x):
    return 0.0 if pd.isna(x) else x


def _diff(a, b):
    return None if pd.isna(a) or pd.isna(b) else round(b - a, 2)


def _status(d):
    # None becomes NaN once placed in a float column, so test with pd.isna, not `is None`.
    return "n/a" if pd.isna(d) else ("OK" if d == 0 else "CHECK")


def _pct(part, whole):
    if pd.isna(part) or pd.isna(whole) or whole in (0, None):
        return None
    return round(100.0 * part / whole, 1)


def _incl_walkin(g, w):
    return pd.NA if (pd.isna(g) and pd.isna(w)) else round(_num(g) + _num(w), 2)


def _row_note(row):
    """Warnings / things to verify for a row. Empty string when nothing to flag."""
    parts = []
    sd = row.get("serve_diff")
    s2g = row.get("silver_to_gold_diff")
    silver, gold = row.get("silver"), row.get("gold")
    if not pd.isna(sd) and sd != 0:
        parts.append(f"VERIFY: funnel differs from gold by {sd:+.0f}")
    if not pd.isna(s2g) and s2g != 0:
        if not pd.isna(silver) and silver == 0 and not pd.isna(gold) and gold > 0:
            parts.append("silver cannot reproduce this KPI (informational)")
        else:
            parts.append(f"silver vs gold off by {s2g:+.0f} "
                         "(informational: dedup / division reclassification / refresh latency)")
    return "; ".join(parts)


def build_summary(pdf):
    piv = pdf.pivot_table(index=GROUP_KEYS, columns="layer",
                          values="value", aggfunc="sum").reset_index()
    for lyr in LAYERS:
        if lyr not in piv.columns:
            piv[lyr] = pd.NA

    piv["gold_incl_walkin"] = [_incl_walkin(g, w)
                               for g, w in zip(piv["gold"], piv["gold_walkin"])]
    piv["silver_to_gold_diff"] = [_diff(s, g) for s, g in zip(piv["silver"], piv["gold"])]
    piv["serve_diff"] = [_diff(e, gs) for e, gs in zip(piv["gold_incl_walkin"], piv["gold_serve"])]
    piv["serve_match_pct"] = [_pct(gs, e) for e, gs in zip(piv["gold_incl_walkin"], piv["gold_serve"])]
    # final_status = does all the information land in Gold-Serve (the funnel)? This is the
    # single headline verdict. Silver<->Gold differences are surfaced as `note`, not a fail.
    piv["final_status"] = piv["serve_diff"].apply(_status)
    piv["note"] = piv.apply(_row_note, axis=1)
    piv["kpi"] = pd.Categorical(piv["kpi"], categories=KPI_ORDER, ordered=True)
    return piv.sort_values(["kpi", "sales_organization", "division"])

if monthly_df is not None:
    totals_pd = monthly_df.toPandas()
    summary = build_summary(totals_pd)
    cols = GROUP_KEYS + ["silver", "gold", "gold_walkin", "gold_incl_walkin", "gold_serve",
                         "silver_to_gold_diff", "serve_diff", "serve_match_pct",
                         "final_status", "note"]
    checks = summary[summary["final_status"] == "CHECK"]
    warns = summary[(summary["final_status"] != "CHECK") & (summary["note"] != "")]

    banner(
        "5. RECONCILIATION SUMMARY  -  per KPI x sales_organization x division",
        how_to_read=COLUMN_LEGEND + [
            "One row per KPI / org / division. final_status is the headline verdict."],
        actions=[
            f"{len(checks)} row(s) are CHECK -> filter final_status = 'CHECK' and investigate "
            "with the drill-down at the bottom.",
            f"{len(warns)} row(s) are OK but carry a note -> read the note column to confirm the "
            "silver<->gold difference is expected (dedup / timezone edge / refresh latency).",
            "If final_status is OK and note is blank, the KPI reconciles - no action."])
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
    rp["gold_incl_walkin"] = [_incl_walkin(g, w) for g, w in zip(rp["gold"], rp["gold_walkin"])]
    rp["silver_to_gold_diff"] = [_diff(s, g) for s, g in zip(rp["silver"], rp["gold"])]
    rp["serve_diff"] = [_diff(e, gs) for e, gs in zip(rp["gold_incl_walkin"], rp["gold_serve"])]
    rp["final_status"] = rp["serve_diff"].apply(_status)
    rp["note"] = rp.apply(_row_note, axis=1)
    rp["kpi"] = pd.Categorical(rp["kpi"], categories=KPI_ORDER, ordered=True)
    rp = rp.sort_values("kpi")
    banner(
        "6. KPI ROLL-UP  -  all org / division combined",
        how_to_read=[
            "One row per KPI, org/division summed away. Same columns as section 5.",
            "This is the top-line: does each KPI reconcile in aggregate?"],
        actions=[
            "Read final_status per KPI. OK = the KPI ties out overall.",
            "A KPI that is OK here but has CHECK rows in section 5 means the gaps net to zero "
            "across groups - still worth a look, but not a total loss.",
            "A KPI that is CHECK here has a genuine aggregate gap -> start with this KPI."])
    display(spark.createDataFrame(rp[["kpi", "silver", "gold", "gold_walkin",
                                      "gold_incl_walkin", "gold_serve",
                                      "silver_to_gold_diff", "serve_diff",
                                      "final_status", "note"]]))
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
    wide["gold_incl_walkin"] = [_incl_walkin(g, w)
                                for g, w in zip(wide["gold"], wide["gold_walkin"])]
    wide["serve_diff"] = [_diff(e, gs)
                          for e, gs in zip(wide["gold_incl_walkin"], wide["gold_serve"])]
    wide["kpi"] = pd.Categorical(wide["kpi"], categories=KPI_ORDER, ordered=True)
    wide = wide.sort_values(["kpi", "sales_organization", "division", "period"])
    banner(
        "7. MONTHLY BREAKDOWN  -  KPI x org x division x month",
        how_to_read=[
            "The section-5 summary exploded to one row per month.",
            "serve_diff = gold_serve - gold_incl_walkin for that single month."],
        actions=[
            "Sort / scan serve_diff for the non-zero months - that pinpoints WHEN a CHECK row "
            "in section 5 went wrong.",
            "A one-off month spike usually means a late refresh or a timezone edge on that "
            "month boundary; a persistent monthly gap is a real pipeline issue."])
    display(spark.createDataFrame(wide[["kpi", "sales_organization", "division", "period",
                                        "silver", "gold", "gold_walkin", "gold_incl_walkin",
                                        "gold_serve", "serve_diff"]]))
else:
    print("No results to break down.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 8. Object / layer reference
# MAGIC What each column above was counted from, for the selected environment.

# COMMAND ----------

banner(
    "8. OBJECT / LAYER REFERENCE  -  what each number was counted from",
    how_to_read=[
        "One row per (KPI, layer): the exact table, org/division expression and measure used.",
        "This is the provenance for every figure in sections 5-7."],
    actions=[
        "When a row looks wrong, check its measure/org/division expression here first - a "
        "mismatch is often a column-mapping assumption, not a data loss.",
        "Cross-check these against your Silver schema (see the section-2 assumptions table)."])
ref_df = spark.createDataFrame([
    Row(kpi=kpi, layer=layer, object=obj,
        sales_organization=org_expr, division=div_expr, measure=value_expr)
    for kpi, layer, obj, _d, org_expr, div_expr, value_expr, _w in REGISTRY])
display(ref_df.orderBy("kpi", "layer"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 9. Total Reservation — monthly validation
# MAGIC `SUM(item_quantity)` for reservation order types (`ZOR`/`YOR`/`TA` = Standard / Fleet /
# MAGIC AFM Corporate Order) by `sales_item_creation_date`, at the fact vs the funnel
# MAGIC (`total_order_items`). Use this to tie out against the SAP figure — e.g. **May 2026 = 3620**
# MAGIC for the selected org. `distinct_orders` is shown only as context (order headers, not the KPI).

# COMMAND ----------

_fact_org, _fact_div = as_str("sales_organization"), as_str("division")
_fun_org, _fun_div = as_str("sales_organization_code"), as_str("division_code")
_fof = f"AND {_fact_org} = '{filter_org}'" if filter_org else ""
_fdf = f"AND {_fact_div} = '{filter_div}'" if filter_div else ""
_uof = f"AND {_fun_org} = '{filter_org}'" if filter_org else ""
_udf = f"AND {_fun_div} = '{filter_div}'" if filter_div else ""

reservation_sql = f"""
WITH fact AS (
  SELECT DATE_TRUNC('MONTH', DATE(sales_item_creation_date)) AS period,
         SUM(item_quantity)             AS fact_reservation,
         COUNT(DISTINCT sales_document) AS distinct_orders
  FROM {FACT}.sales_ordr_vn_d
  WHERE UPPER(order_type) IN ('ZOR','YOR','TA')
    AND DATE(sales_item_creation_date) BETWEEN DATE('{start_date}') AND DATE('{end_date}')
    {_fof} {_fdf}
  GROUP BY 1
),
funnel AS (
  SELECT DATE_TRUNC('MONTH', reporting_date) AS period,
         SUM(total_order_items) AS funnel_reservation
  FROM {FUNNEL_TABLE}
  WHERE reporting_date BETWEEN DATE('{start_date}') AND DATE('{end_date}')
    {_uof} {_udf}
  GROUP BY 1
)
SELECT COALESCE(f.period, u.period) AS period,
       f.fact_reservation,
       u.funnel_reservation,
       u.funnel_reservation - f.fact_reservation AS diff,
       f.distinct_orders
FROM fact f
FULL OUTER JOIN funnel u ON f.period = u.period
ORDER BY period
"""
banner(
    "9. TOTAL RESERVATION  -  monthly validation (fact vs funnel)",
    how_to_read=[
        "fact_reservation = SUM(item_quantity) on sales_ordr_vn_d for order types ZOR/YOR/TA.",
        "funnel_reservation = SUM(total_order_items) on the funnel for the same month.",
        "diff = funnel - fact. distinct_orders is context only (order headers, not the KPI)."],
    actions=[
        "diff should be 0 each month -> tie fact_reservation to the SAP figure "
        "(e.g. May 2026 = 3620 for the selected org).",
        "A non-zero diff means the funnel's total_order_items disagrees with the fact -> "
        "check the enquiry_id attribution in sections 9b / 9c."])
try:
    display(spark.sql(reservation_sql))
except Exception as e:
    print("Total Reservation validation FAILED —", str(e).splitlines()[0])

# COMMAND ----------

# MAGIC %md
# MAGIC ## 9b. Total Reservation — attribution & channel breakdown
# MAGIC Total Reservation counts **all** reservation order types with no `sales_group` filter, so
# MAGIC it includes retail, fleet and corporate. This splits the item-quantity by:
# MAGIC - **attribution** — whether the order links to a C4C enquiry (`SO.enquiry_id` found in
# MAGIC   `customer_enquiries_long`). Unattributed = fleet / corporate / direct, expected because
# MAGIC   C4C is retail-focused (the `209226Y211`-style `enquiry_id` is a constructed token).
# MAGIC - **channel_group** — retail/ecom (`sales_group IN ('001','040')`) vs other. The funnel's
# MAGIC   `web_attributed_*` metrics only apply to retail/ecom leads, so non-retail and
# MAGIC   unattributed reservations carry **no** web attribution by design.

# COMMAND ----------

_ro, _rd = as_str("sales_organization"), as_str("division")
_rof = f"AND {_ro} = '{filter_org}'" if filter_org else ""
_rdf = f"AND {_rd} = '{filter_div}'" if filter_div else ""

reservation_attr_sql = f"""
SELECT DATE_TRUNC('MONTH', DATE(so.sales_item_creation_date)) AS period,
       CASE WHEN so.sales_group IN ('001','040') THEN 'retail/ecom'
            ELSE 'fleet/corporate/other' END AS channel_group,
       CASE WHEN ce.enquiry_id IS NOT NULL THEN 'attributed (C4C enquiry)'
            ELSE 'unattributed (no enquiry)' END AS attribution,
       SUM(so.item_quantity)             AS reservation_items,
       COUNT(DISTINCT so.sales_document) AS orders
FROM {FACT}.sales_ordr_vn_d so
LEFT JOIN (
    SELECT DISTINCT enquiry_id
    FROM {GOLD}.customer_enquiries_long
    WHERE NULLIF(enquiry_id, '') IS NOT NULL
) ce ON so.enquiry_id = ce.enquiry_id
WHERE UPPER(so.order_type) IN ('ZOR','YOR','TA')
  AND DATE(so.sales_item_creation_date) BETWEEN DATE('{start_date}') AND DATE('{end_date}')
  {_rof} {_rdf}
GROUP BY 1, 2, 3
ORDER BY period, channel_group, attribution
"""
banner(
    "9b. TOTAL RESERVATION  -  attribution x channel breakdown",
    how_to_read=[
        "Each month's item-quantity split two ways at once:",
        "channel_group = retail/ecom (sales_group 001/040) vs fleet/corporate/other.",
        "attribution = whether the order's enquiry_id is found in customer_enquiries_long.",
        "reservation_items = SUM(item_quantity); orders = distinct sales_document."],
    actions=[
        "Expect fleet/corporate/other to be largely 'unattributed' - that is by design "
        "(C4C is retail-focused), not a defect.",
        "Watch the retail/ecom + unattributed cell: retail orders SHOULD attribute, so a large "
        "figure there is real attribution loss -> drill into it in section 9c."])
try:
    display(spark.sql(reservation_attr_sql))
except Exception as e:
    print("Total Reservation attribution breakdown FAILED —", str(e).splitlines()[0])

# COMMAND ----------

# MAGIC %md
# MAGIC ## 9c. Unattributed reservations — root-cause split
# MAGIC Reservations whose `enquiry_id` finds no match in `customer_enquiries_long` (the funnel's
# MAGIC `LEFT JOIN` returns null), classified by **root cause**:
# MAGIC - **`enquiry_id` present but not in gold → opportunity-id leakage.** The order references an
# MAGIC   opportunity/enquiry that never landed in `customer_enquiries_long` (a gap in the enquiries
# MAGIC   pipeline). `enquiry_id_shape` further flags whether it is `numeric` (a real opportunity id
# MAGIC   that leaked) or a `non-numeric token` (a constructed `org+office` placeholder like
# MAGIC   `209226Y211`).
# MAGIC - **`enquiry_id` null → missing mapping in SAP.** The order was never linked to an
# MAGIC   opportunity at source (typical for fleet / corporate / direct, since C4C is retail).
# MAGIC
# MAGIC Counts distinct **`sales_document`** (real orders) and `item_quantity`, and **includes**
# MAGIC null-enquiry_id orders — so it ties to a manual
# MAGIC `... LEFT JOIN customer_enquiries_long CE ON SO.enquiry_id = CE.enquiry_id WHERE CE.enquiry_id IS NULL`.
# MAGIC (The earlier drill's `191 keys / 229 rows` was misleading: it counted **distinct enquiry_id
# MAGIC tokens** — which saturate ~191 because unattributed orders reuse a small set of constructed
# MAGIC tokens — and excluded null-enquiry_id orders.)

# COMMAND ----------

_ro2, _rd2 = as_str("sales_organization"), as_str("division")
_rof2 = f"AND {_ro2} = '{filter_org}'" if filter_org else ""
_rdf2 = f"AND {_rd2} = '{filter_div}'" if filter_div else ""

unattributed_base = f"""
FROM {FACT}.sales_ordr_vn_d so
LEFT JOIN (
    SELECT DISTINCT enquiry_id
    FROM {GOLD}.customer_enquiries_long
    WHERE NULLIF(enquiry_id, '') IS NOT NULL
) ce ON so.enquiry_id = ce.enquiry_id
WHERE UPPER(so.order_type) IN ('ZOR','YOR','TA')
  AND DATE(so.sales_item_creation_date) BETWEEN DATE('{start_date}') AND DATE('{end_date}')
  AND ce.enquiry_id IS NULL
  {_rof2} {_rdf2}
"""

unattributed_rootcause_sql = f"""
SELECT
  CASE WHEN NULLIF(so.enquiry_id, '') IS NULL
       THEN 'Missing mapping in SAP (null enquiry_id)'
       ELSE 'Opportunity-id leakage (enquiry_id present, not in gold)' END AS root_cause,
  CASE WHEN NULLIF(so.enquiry_id, '') IS NULL THEN 'n/a'
       WHEN so.enquiry_id RLIKE '^[0-9]+$' THEN 'numeric (real opportunity id that leaked)'
       ELSE 'non-numeric token (constructed org+office placeholder)' END AS enquiry_id_shape,
  COUNT(DISTINCT so.sales_document) AS unattributed_orders,
  COUNT(*)                         AS order_line_rows,
  SUM(so.item_quantity)            AS unattributed_item_qty,
  COUNT(DISTINCT so.enquiry_id)    AS distinct_enquiry_ids
{unattributed_base}
GROUP BY 1, 2
ORDER BY 1, 2
"""
banner(
    "9c. UNATTRIBUTED RESERVATIONS  -  root-cause split",
    how_to_read=[
        "Only reservations whose enquiry_id has no match in customer_enquiries_long.",
        "root_cause = 'Opportunity-id leakage' (enquiry_id present, missing from gold) vs "
        "'Missing mapping in SAP' (enquiry_id null).",
        "enquiry_id_shape splits leakage into numeric (a real opportunity id) vs non-numeric "
        "token (a constructed org+office placeholder like 209226Y211).",
        "unattributed_orders = distinct sales_document; unattributed_item_qty = SUM(item_quantity)."],
    actions=[
        "numeric leakage is the ACTIONABLE bucket -> chase the enquiries pipeline; those are real "
        "opportunities that failed to reach gold. If non-trivial, escalate it.",
        "null enquiry_id / non-numeric token = source-side SAP gap or expected fleet/direct -> "
        "no pipeline fix, note it as known.",
        "The 50-row sample below shows the raw orders for spot-checking individual documents."])
try:
    display(spark.sql(unattributed_rootcause_sql))
    print()
    banner("9c (detail). Sample of unattributed reservation orders (raw rows, max 50)",
           how_to_read=["Actual sales_ordr_vn_d rows behind the counts above, all attributes."],
           actions=["Spot-check enquiry_id / sales_group / order_type to confirm the root cause."])
    display(spark.sql(f"SELECT so.* {unattributed_base} LIMIT 50"))
except Exception as e:
    print("Unattributed reservations FAILED —", str(e).splitlines()[0])

# COMMAND ----------

# MAGIC %md
# MAGIC # Granular drill-down — which rows are missing between layers
# MAGIC For each KPI, sample the actual business keys (with **all attributes**) that exist in one
# MAGIC layer but not the next — e.g. `lead_id`s in Silver `sap_c4c_leads` that never reach Gold
# MAGIC `customer_leads_long`.
# MAGIC
# MAGIC **Scope of key-level anti-joins**
# MAGIC - **Silver ↔ Gold** — full key-level comparison (both carry the business key).
# MAGIC - **Invoices** — invoice rows whose order key isn't found in `sales_ordr_vn_d`.
# MAGIC   (Total Reservation attribution is order-keyed, not a token anti-join — see section 9c.)
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
    ["All", "Leads", "Hot Leads", "Visits", "Test Drives", "Total Reservation", "Invoices"],
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
# left/right = (label, object, key_expr, where_clause). gdate = the gold date column, used to
# window the gold (product) side symmetrically in product_only so historical rows outside the
# analysis window are not flagged as missing.
DRILL = [
    ("Leads",
     ("silver", f"{SILVER}.sap_c4c_leads",
      "LPAD(COALESCE(C4CLEADID, REPLACE(LEAD_ID,'C4C-','')), 10, '0')",
      _win("TIMESTAMPADD(HOUR, 4, COALESCE(CREATION_DATE, audit_dfd_created_date))")),
     ("gold", f"{GOLD}.customer_leads_long", "LEAD_ID", "1=1"),
     ("silver", "SALES_ORGANIZATION", "DIVISION"),
     ("gold", "SALES_ORGANISATION_CODE", "DIVISION"),
     "LEAD_CREATION_DATE",
     ["source_only", "product_only"]),

    ("Hot Leads",
     ("silver", f"{SILVER}.sap_c4c_leads",
      "LPAD(COALESCE(C4CLEADID, REPLACE(LEAD_ID,'C4C-','')), 10, '0')",
      _win("TIMESTAMPADD(HOUR, 4, COALESCE(CREATION_DATE, audit_dfd_created_date))") + " AND UPPER(QUALIFICATION) = 'HOT'"),
     ("gold", f"{GOLD}.customer_leads_long", "LEAD_ID",
      "(LEAD_QUALIFICATION = 'Hot' OR PASS_TO_BRANCH_TIME IS NOT NULL)"),
     ("silver", "SALES_ORGANIZATION", "DIVISION"),
     ("gold", "SALES_ORGANISATION_CODE", "DIVISION"),
     "LEAD_CREATION_DATE",
     ["source_only", "product_only"]),

    ("Visits",
     ("silver", f"{SILVER}.sap_c4c_opportunity_header", "LPAD(ID, 10, '0')",
      _win("TIMESTAMPADD(HOUR, 4, COALESCE(creationDate, audit_dfd_created_date))")),
     ("gold", f"{GOLD}.customer_enquiries_long", "ENQUIRY_ID", "1=1"),
     ("silver", "ORGID",
      "COALESCE(get_json_object(ENQUIRY_INFORMATION,'$.division'), "
      "get_json_object(ENQUIRY_INFORMATION,'$.DIVISION'))"),
     ("gold", "SALES_ORGANISATION_CODE", "DIVISION_CODE"),
     "ENQUIRY_CREATED_TIME",
     ["source_only", "product_only"]),

    ("Test Drives",
     ("silver", f"{SILVER}.sap_c4c_follow_up_activities", "LPAD(OPPORTUNITYID, 10, '0')",
      _win("TIMESTAMPADD(HOUR, 4, audit_dfd_created_date)") + " AND SUBJECT_TYPE LIKE 'Test Drive%' AND NULLIF(OPPORTUNITYID,'') IS NOT NULL"),
     ("gold", f"{GOLD}.customer_enquiries_long", "ENQUIRY_ID",
      "COALESCE(TESTDRIVE_OPEN_TIME, TESTDRIVE_TIME, TESTDRIVE_CANCELLED_TIME) IS NOT NULL"),
     ("silver", "SALES_ORGANIZATION", "DIVISION"),
     ("gold", "SALES_ORGANISATION_CODE", "DIVISION_CODE"),
     "COALESCE(TESTDRIVE_TIME, TESTDRIVE_CANCELLED_TIME, TESTDRIVE_OPEN_TIME)",
     ["source_only", "product_only"]),

    # NOTE: Total Reservation attribution is NOT a key-level anti-join — orders are keyed by
    # sales_document, not enquiry_id (unattributed orders share a small set of constructed
    # org+div+office enquiry_id tokens, and many have a null enquiry_id). See section 9c for the
    # correct order-level view (distinct sales_document + item_quantity, includes null enquiry_id).

    ("Invoices",
     ("gold_serve_fact", f"{FACT}.sales_newu_usud_sals_vn_d_view", "sales_order_number",
      _win("day") + " AND NULLIF(sales_order_number,'') IS NOT NULL"),
     ("orders", f"{FACT}.sales_ordr_vn_d", "sales_document", "1=1"),
     ("gold_serve_fact", "sales_organization_code", "division_key"),
     ("orders", "sales_organization", "division"),
     None,
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
        verdict = "OK - nothing missing" if c["c"] == 0 else f"CHECK - {c['k']} keys to explain"
        print(f"[{title}]  in {l_lbl} not in {r_lbl}: "
              f"{c['k']} distinct keys ({c['c']} rows)  ->  {verdict}")
        if c["c"]:
            display(spark.sql(f"SELECT L.* {base} LIMIT {n}"))
    except Exception as e:
        print(f"[{title}]  FAILED — {str(e).splitlines()[0]}")


banner(
    "DRILL-DOWN  -  which business keys are missing between layers",
    how_to_read=[
        "For each KPI, one line per direction, then a sample of the offending rows:",
        "source_only = key is upstream (silver) but missing downstream (gold) = the real drop-off.",
        "product_only = key is downstream but not upstream = key-derivation / join back-fill.",
        "'0 distinct keys' means that boundary is clean; a non-zero count prints a sample below it."],
    actions=[
        "source_only > 0 for Leads/Visits/Test Drives: expected only for org 5000 (excluded from "
        "gold) - if the sample shows other orgs, that is a genuine gold-load gap to fix.",
        "product_only > 0: usually benign (rows sourced via a different key) - confirm in the sample.",
        "Use the granular_sample_kpi / granular_sample_rows widgets to focus and enlarge samples."])

for kpi, left, right, ldim, rdim, gdate, directions in DRILL:
    if SAMPLE_KPI != "All" and SAMPLE_KPI != kpi:
        continue
    l_lbl, l_obj, l_key, l_where = left
    r_lbl, r_obj, r_key, r_where = right
    if "source_only" in directions:
        # sample windowed silver (+ its dim filters); existence = all-history gold (unbounded)
        left_f = (l_lbl, l_obj, l_key, l_where + _dim_filters(ldim[1], ldim[2]))
        anti_sample(f"{kpi} · source_only", left_f, right, SAMPLE_N)
    if "product_only" in directions:
        # sample gold windowed to the SAME analysis window (+ dim filters); existence = windowed
        # silver (all orgs). Symmetric window prevents historical gold rows being false positives.
        gold_where = r_where + (f" AND {_win(gdate)}" if gdate else "") + _dim_filters(rdim[1], rdim[2])
        prod_left = (r_lbl, r_obj, r_key, gold_where)
        src_right = (l_lbl, l_obj, l_key, l_where)
        anti_sample(f"{kpi} · product_only", prod_left, src_right, SAMPLE_N)
