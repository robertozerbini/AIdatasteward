# dq_framework — How-To Guide

Practical guide to installing the framework in a Databricks notebook, testing it,
and defining data quality checks. For architecture and layout see the
[README](../README.md).

- [1. Install in a notebook](#1-install-in-a-notebook)
- [2. Test it](#2-test-it)
- [3. Define data quality checks](#3-define-data-quality-checks)
  - [Row-level checks (DQX)](#row-level-checks-dqx)
  - [Endpoint checks](#endpoint-checks)
  - [KPI ground-truth asserts](#kpi-ground-truth-asserts)

---

## 1. Install in a notebook

Two things must be installed: the **framework** and its **DQX runtime dependency**.

### 1a. Install the framework — pick one

**Option A — Repos / Workspace Files (fastest for dev, no rebuild loop)**
```python
import sys
sys.path.append("/Workspace/Repos/<you>/AIdatasteward")
```

**Option B — build + install the wheel (stable / job install)**
```python
# %sh cd /Workspace/Repos/<you>/AIdatasteward && python -m build --wheel
# %pip install /Workspace/Repos/<you>/AIdatasteward/dist/dq_framework-0.1.0-py3-none-any.whl
```

### 1b. Install the DQX runtime dependency
```python
# %pip install databricks-labs-dqx
# %pip install pyyaml        # usually already on DBR
dbutils.library.restartPython()   # REQUIRED after %pip, before importing dq_framework
```

> Run `restartPython()` **before** `import dq_framework`, or the freshly installed
> packages won't be visible.

---

## 2. Test it

### 2a. Fast confidence — unit tests (no cluster/UC needed)
```python
# %sh cd /Workspace/Repos/<you>/AIdatasteward && python -m pytest tests/ -q
```
Expect `41 passed`. This proves the decision logic (gating, tolerance, config
validation, schema diff) is intact.

### 2b. End-to-end smoke test (real DQX split + results write)

Build a tiny table with a deliberate duplicate `org_key`, run with an inline dict
config, and check the split:
```python
from dq_framework import run_row_checks

df = spark.createDataFrame(
    [(1, "A"), (2, "B"), (2, "C")],   # org_key=2 duplicated
    "org_key int, name string",
)

cfg = {
    "kind": "rowlevel",
    "target": "smoke_orgstrc",
    "results_table": "main.default.dq_results_smoke",   # a schema you can write to
    "checks": [
        {"name": "org_key_is_unique", "criticality": "error",
         "check": {"function": "is_unique", "arguments": {"columns": ["org_key"]}}},
    ],
}

res = run_row_checks(df, config=cfg, trigger="ondemand")

print("passed:", res.passed, "| gated:", res.gated)   # -> False, True
print("valid:", res.valid_df.count())                  # -> 1
print("quarantine:", res.quarantine_df.count())        # -> 2
display(res.results_df)                                 # one fail row, actual=2, gated=true
```

Confirm gating actually stops a pipeline, and that results persisted:
```python
try:
    res.raise_if_gated()
except Exception as e:
    print("Correctly gated:", e)     # DataQualityGateError

display(spark.table("main.default.dq_results_smoke"))
```

**First-run gotchas**
- Point `results_table` at a schema you can write to.
- `import databricks.labs.dqx` fails → the `%pip` cell didn't run before
  `restartPython()`; re-run the install cells.
- Quarantine count reads 0 → your DQX version may not use `_errors`/`_warnings`
  result columns; note the version and adjust `dq_framework/spark/rowlevel.py`.

---

## 3. Define data quality checks

Checks live as **YAML files** under `configs/` (one per target) or as an inline
`dict` passed to the facade. There are three kinds; every check — whatever the
kind — lands in `dq_results` with the same `severity → gating` behaviour:
`error` gates/quarantines, `warn` only records and alerts.

### Row-level checks (DQX)

Anatomy of one check:
```yaml
kind: rowlevel
target: prod_auto.gold_virtual.eudu_mdata_dtac_orgstrc
results_table: prod_auto.gold_virtual.dq_results   # optional; this is the default
checks:
  - name: org_key_is_unique      # -> dq_results.check_name
    criticality: error           # error | warn
    check:
      function: is_unique        # a DQX check function
      arguments:                 # arguments depend on the function
        columns: [org_key]
    filter: "region = 'EU'"      # OPTIONAL: apply the check only to matching rows
```

Common functions and their arguments:
```yaml
# not null
- name: name_not_null
  criticality: error
  check: { function: is_not_null, arguments: { col_name: name } }

# uniqueness (single or composite key)
- name: pk_unique
  criticality: error
  check: { function: is_unique, arguments: { columns: [org_key, valid_from] } }

# allowed values
- name: status_in_set
  criticality: warn
  check: { function: is_in_list, arguments: { col_name: status, allowed: [ACTIVE, CLOSED] } }

# numeric range
- name: amount_in_range
  criticality: error
  check: { function: is_in_range, arguments: { col_name: amount, min_limit: 0, max_limit: 1000000 } }

# pattern / regex
- name: email_format
  criticality: warn
  check: { function: regex_match, arguments: { col_name: email, regex: "^[^@]+@[^@]+$" } }

# arbitrary cross-field rule (SQL that must be TRUE per row)
- name: end_after_start
  criticality: error
  check:
    function: sql_expression
    arguments:
      expression: "valid_to > valid_from"
      msg: "valid_to must be after valid_from"
```

> Exact function names track your **installed DQX version**. List them in a notebook:
> ```python
> from databricks.labs.dqx import check_funcs
> print([f for f in dir(check_funcs) if not f.startswith("_")])
> ```

### Endpoint checks

Execute a stored procedure and validate its result set:
```yaml
kind: endpoint
target: sp_customer_360
execute: "CALL prod_auto.gold_virtual.sp_customer_360()"
result_checks:
  - { name: non_empty, type: count,     severity: error, op: ">", value: 0 }
  - { name: contract,  type: schema,    severity: error, columns: [customer_id, ltv, segment] }
  - { name: fresh_24h, type: freshness, severity: warn,  column: load_ts, max_age_hours: 24 }
```
Supported `type`s:
- `count` — compare row count; `op` ∈ `> >= < <= == !=`, against `value`.
- `schema` — assert the listed `columns` are present (extra columns allowed).
- `freshness` — assert `max(column)` is within `max_age_hours` of now.

### KPI ground-truth asserts

The check is a `query` returning one scalar; the expected value and tolerance
live in the **ground-truth reference table**, so stewards update targets without
a code change:
```yaml
kind: kpi
target: revenue_kpis
ground_truth_table: prod_auto.gold_virtual.dq_kpi_ground_truth
kpis:
  - name: total_revenue_2026q2
    severity: error
    query: "SELECT sum(amount) FROM prod_auto.gold_virtual.fact_sales WHERE fiscal_quarter='2026Q2'"
```
Steward sets the target in the reference table:
```sql
INSERT INTO prod_auto.gold_virtual.dq_kpi_ground_truth VALUES
-- kpi_name, target, expected_value, tolerance_pct, tolerance_abs, effective_from, effective_to, active
('total_revenue_2026q2','revenue_kpis', 1250000.0, 1.0, NULL, timestamp('2026-04-01'), NULL, true);
```
Passes when `|actual − expected|` ≤ the larger of `tolerance_pct` / `tolerance_abs`.

### Applying a new check

1. Edit the relevant `configs/**/*.yaml` (or pass a dict for ad-hoc runs).
2. Call it: `run_row_checks(df, config="configs/products/orgstrc.yaml", trigger="pipeline")`
   (or `run_endpoint_checks` / `run_kpi_asserts`).
3. For scheduled jobs, commit and redeploy the bundle (`databricks bundle deploy`).
