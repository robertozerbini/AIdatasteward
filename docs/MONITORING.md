# dq_framework — Monitoring & Reporting

Because every check kind (rowlevel / endpoint / kpi) writes to one table —
`prod_auto.gold_virtual.dq_results` — monitoring is just querying and alerting on
that table. There are three complementary layers.

| Layer | Answers | Tool |
|-------|---------|------|
| **Dashboard** | "What is the state of DQ across all targets?" | Databricks SQL / Lakeview dashboard |
| **Alerts** | "Tell me when a check fails" | Databricks SQL Alerts → email/Slack/webhook |
| **Job notifications** | "Tell me when a run was *gated* (blocked a pipeline)" | Databricks Jobs notifications |

Run [`sql/monitoring.sql`](../sql/monitoring.sql) once to create the helper views
(`v_dq_latest`, `v_dq_runs`); the reporting queries are in there too.

---

## 1. Dashboard (reporting)

Create a **Databricks SQL dashboard** (or Lakeview) with tiles backed by the
queries in `sql/monitoring.sql`:

- **Current health per target** — counts of failing checks (query #1).
- **Failures last 24h** — the detail table (query #2).
- **Gated runs last 7d** — pipeline-blocking failures (query #3).
- **Per-check failure trend** — daily time series (query #4).
- **KPI drift** — actual vs expected over time (query #5).

`v_dq_latest` gives you "state right now" (latest result per check); the raw
`dq_results` table gives you history for trends.

---

## 2. Alerts (get notified on failure)

Databricks **SQL Alerts** fire when a query returns rows. Use the alert query at
the bottom of `sql/monitoring.sql` (failures in the last hour):

1. Save that query in Databricks SQL.
2. Create an **Alert** on it:
   - Condition: **result is not empty** (row count `> 0`).
   - Schedule: every 15–60 min (match your run cadence).
   - Destination: email, Slack, PagerDuty, or a webhook.
3. Optionally split into two alerts by severity:
   - `severity = 'error'` → page / high-priority channel.
   - `severity = 'warn'` → low-priority digest channel.

> Keep the alert window aligned with the check schedule so you notify once per
> failure, not repeatedly on the same stale rows.

---

## 3. Job notifications (gating)

When an **error**-severity check fails, `raise_if_gated()` fails the Databricks
task. Wire notifications so a gated run pages the owner even before the alert
query runs. Add to each job in `resources/dq_jobs.yml`:

```yaml
    dq_scheduled_checks:
      name: "[DQ] scheduled checks"
      email_notifications:
        on_failure:
          - data-quality-oncall@yourco.com
      # or Slack/Teams/PagerDuty via a notification destination:
      # webhook_notifications:
      #   on_failure:
      #     - id: <notification-destination-id>
      ...
```

This covers the two failure surfaces:
- **Gated (error):** the task fails → job `on_failure` notification.
- **Warn / recorded:** the task succeeds → picked up by the SQL Alert instead.

---

## What to watch

- **Freshness of `dq_results` itself** — if a scheduled job stops running, no new
  rows arrive. Add an alert on "no rows in the last N hours for target X" so a
  silent pipeline doesn't look healthy.
- **Gated rate** — a rising share of gated runs in `v_dq_runs` signals upstream
  data degradation.
- **KPI drift direction** — query #5; a steady drift toward the tolerance edge is
  an early warning before it flips to `fail`.
