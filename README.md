# dq_framework

Unified Databricks data-quality framework, DQX-backed, callable from pipeline
notebooks and scheduled jobs. One engine, one config schema, one results table
covering three check kinds:

| kind       | use case                                   | typical trigger        |
|------------|--------------------------------------------|------------------------|
| `rowlevel` | data products & pipelines (DQX rules)      | inline `pipeline`      |
| `endpoint` | stored procs consumed by downstream apps   | `schedule`             |
| `kpi`      | ground-truth asserts on KPI values         | `schedule` / `ondemand`|

## Call site

```python
from dq_framework import run_row_checks

res = run_row_checks(df, config="configs/products/orgstrc.yaml", trigger="pipeline")
res.raise_if_gated()      # error-severity failures stop the job
df = res.valid_df         # continue with clean rows
```

`run_endpoint_checks(config=...)` and `run_kpi_asserts(config=...)` follow the
same shape. All three append to `prod_auto.gold_virtual.dq_results` for one
place to alert and dashboard.

## How-to guide

- **[docs/GUIDE.md](docs/GUIDE.md)** — installing in a notebook, testing it,
  and defining checks (row-level / endpoint / KPI).
- **[docs/MONITORING.md](docs/MONITORING.md)** — dashboards, SQL alerts, and job
  notifications over the `dq_results` table.
- **[docs/NOTIFICATIONS.md](docs/NOTIFICATIONS.md)** — routing failures to email,
  Teams, and Jira, and configuring who gets notified.

## Business glossary

- **[glossary/funnel_2_0/](glossary/funnel_2_0/)** — the steward-owned business
  glossary for **Funnel 2.0**: the funnel KPIs (Leads → Invoices) plus the
  open-reservation bank metric, with definitions, pseudo-code, and supporting
  terms. All definitions are **under approval**. `glossary.yaml` is the source
  of truth; the markdown is generated and drift-guarded in CI.

## Layout

```
dq_framework/
  core/     pure logic (no pyspark) — gating, asserts, config, results, ops   [unit-tested]
  spark/    runtime adapters — store, rowlevel(DQX), endpoint, kpi
  facade.py public API + DQResult
configs/    products/ endpoints/ kpis/   (YAML rules, version-controlled)
sql/ddl.sql results + ground-truth tables
notebooks/  example pipeline call site
tests/      pure-core unit tests
```

## Design notes

- **Severity-driven gating:** `criticality/severity: error` fails the job and
  blocks downstream; `warn` records + alerts only.
- **Ground truth in Unity Catalog:** `dq_kpi_ground_truth` holds expected values,
  tolerances, and effective dates so stewards update targets without code changes.
- **Pure core / thin adapters:** all decision logic (gating, tolerance, schema
  diff, config validation) is pyspark-free and unit-tested; the Spark layer is
  glue. Run tests with `pytest` (no cluster needed).

## Dev

```bash
pip install pyyaml pytest
pytest          # 41 pure-core tests, no Spark required
```

Package as a wheel (`python -m build`) and attach to the job cluster, or point
`sys.path` at the Repo for dev.
